"""Точка входа: блоки задач → koji и VEX → CSV и файл отбраковки."""
import argparse
import logging
import os
import sys
import time
from collections import Counter
from typing import List, Optional

from . import __version__, kojiclient, logs, report, vex
from .tasks import parse

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_PARTIAL = 1  # CSV записан, но есть отбраковка, ERROR koji или fetch error
EXIT_FATAL = 2

STDIO = "-"
REJECTS_SUFFIX = ".rejected.txt"
REJECTS_STDOUT = "vulnsheet" + REJECTS_SUFFIX


class _Fatal(Exception):
    """Ошибка, после которой таблицу не построить."""


def _rhel(value):
    try:
        return vex.parse_rhel(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vulnsheet",
        description="Блоки задач из тасктрекера → CSV с данными Red Hat VEX и koji.")
    parser.add_argument("input", nargs="?", default=STDIO,
                        help="файл с блоками задач (по умолчанию stdin)")
    parser.add_argument("--rhel", required=True, type=_rhel,
                        help="версия RHEL: 9 — только 9, 9.2 — только 9.2")
    parser.add_argument("--koji-url", required=True, help="URL kojihub")
    parser.add_argument("--tag", required=True, help="koji-тег")
    parser.add_argument("-o", "--output", default=STDIO,
                        help="CSV (по умолчанию stdout)")
    parser.add_argument("--rejects",
                        help="файл для битых блоков (по умолчанию <выход>%s)"
                             % REJECTS_SUFFIX)
    parser.add_argument("--log-level", choices=list(logs.LEVELS),
                        default=logs.DEFAULT_LEVEL,
                        help="подробность журнала в stderr (по умолчанию %s)"
                             % logs.DEFAULT_LEVEL)
    parser.add_argument("--version", action="version",
                        version="vulnsheet " + __version__)
    return parser


def rejects_path(output: str, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if output == STDIO:
        return REJECTS_STDOUT
    return os.path.splitext(output)[0] + REJECTS_SUFFIX


def _cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "vulnsheet")


def _read_input(path: str) -> str:
    try:
        if path == STDIO:
            return sys.stdin.read()
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except UnicodeDecodeError as exc:
        raise _Fatal("вход не в UTF-8: %s" % exc)
    except OSError as exc:
        raise _Fatal("вход не читается: %s" % exc)


def _open_output(path: str):
    if path == STDIO:
        return sys.stdout
    try:
        return open(path, "w", newline="", encoding="utf-8")
    except OSError as exc:
        raise _Fatal("выход не пишется: %s" % exc)


def _write_rejects(path: str, rejects) -> None:
    if rejects:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n\n".join(r.text for r in rejects) + "\n")
        except OSError as exc:
            raise _Fatal("файл отбраковки не пишется: %s" % exc)
        logger.warning("битые блоки (%d) записаны в %s", len(rejects), path)
    elif os.path.exists(path):
        os.remove(path)
        logger.info("удалён %s от прошлого прогона: битых блоков нет", path)


def _summary(builds: List[str], verdicts) -> None:
    states = Counter(v.state.split(" (", 1)[0] for v in verdicts)
    if states:
        logger.info("RHEL state: %s", ", ".join(
            "%s %d" % item for item in sorted(states.items(), key=lambda kv: (-kv[1], kv[0]))))
    marks = Counter(b if b in (kojiclient.NOT_FOUND, kojiclient.ERROR) else "found"
                    for b in builds)
    logger.info("SL NVR: найдено %d, NOT_FOUND %d, ERROR %d", marks["found"],
                marks[kojiclient.NOT_FOUND], marks[kojiclient.ERROR])


def _run(args) -> int:
    tasks, rejects = parse(_read_input(args.input))
    if not tasks and not rejects:
        raise _Fatal("во входе нет ни одного блока")
    for reject in rejects:
        logger.warning("блок %d «%s» отбракован: %s", reject.number,
                       reject.text.split("\n", 1)[0].strip(), reject.reason)
    cves = list(dict.fromkeys(t.cve for t in tasks))
    packages = list(dict.fromkeys(t.component for t in tasks))
    logger.info("хаб %s, тег %s, RHEL %s", args.koji_url, args.tag, args.rhel)
    logger.info("блоков %d, отбраковано %d; CVE %d, пакетов %d",
                len(tasks) + len(rejects), len(rejects), len(cves), len(packages))

    # выход открываем до сети: неверный путь должен падать сразу
    out = _open_output(args.output)
    try:
        nvrs, indices, failures = {}, {}, {}
        if tasks:
            session = kojiclient.connect(args.koji_url)
            nvrs = kojiclient.latest_builds(session, args.tag, packages)
            indices, failures = vex.fetch_all(cves, vex.prepare_cache(_cache_dir()))
        builds = [nvrs[t.component] for t in tasks]
        verdicts = [vex.Verdict(state=vex.FETCH_ERROR) if t.cve in failures
                    else vex.lookup(indices[t.cve], t.component, args.rhel)
                    for t in tasks]
        report.write([report.row(t, b, v) for t, b, v in zip(tasks, builds, verdicts)], out)
    finally:
        if out is not sys.stdout:
            out.close()
    if args.output != STDIO:
        logger.info("написан %s", args.output)

    _write_rejects(rejects_path(args.output, args.rejects), rejects)
    _summary(builds, verdicts)
    partial = rejects or failures or kojiclient.ERROR in builds
    return EXIT_PARTIAL if partial else EXIT_OK


def _fatal(message: str) -> int:
    """Одна строка пользователю, трейсбек — только на debug."""
    logger.error("%s", message)
    logger.debug("трейсбек", exc_info=True)
    return EXIT_FATAL


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    logs.configure(args.log_level)
    started = time.monotonic()
    try:
        code = _run(args)
    except _Fatal as exc:
        return _fatal(str(exc))
    except kojiclient.KojiError as exc:
        return _fatal("koji: %s" % exc)
    except Exception as exc:  # непредвиденное не должно ронять CLI трейсбеком
        return _fatal("фатальная ошибка: %s" % exc)
    logger.info("всего за %.1f с", time.monotonic() - started)
    return code
