"""Точка входа: блоки задач и/или прежняя таблица → koji и VEX → CSV."""
import argparse
import logging
import os
import sys
import tempfile
import time
from collections import Counter
from typing import List, Optional

from . import __version__, config, kojiclient, logs, merge, report, table, vex
from .tasks import parse

logger = logging.getLogger(__name__)

EXIT_OK = 0
# CSV записан, но есть отбраковка, ERROR koji, fetch error (в том числе там,
# где из-за сбоя оставлены прежние koji или VEX), строки таблицы, по которым
# нечего спрашивать, либо читатель оборвал stdout (broken pipe) — таблица
# дописана не до конца
EXIT_PARTIAL = 1
EXIT_FATAL = 2

STDIO = "-"
REJECTS_SUFFIX = ".rejected.txt"
REJECTS_STDOUT = "vulnsheet" + REJECTS_SUFFIX

# режим по (есть --blocks, есть --table)
MODES = {
    (True, False): "новая таблица",
    (False, True): "обновление koji и VEX",
    (True, True): "синхронизация с блоками",
}


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
        description="Блоки задач из тасктрекера и/или прежняя таблица → CSV "
                    "с данными Red Hat VEX и koji.")
    parser.add_argument("--blocks", metavar="FILE",
                        help="файл с блоками задач; - — stdin")
    parser.add_argument("--table", metavar="FILE",
                        help="прежняя таблица vulnsheet: без --blocks — обновить в ней "
                             "koji и VEX, с --blocks — сверить с блоками")
    parser.add_argument("--config",
                        help="YAML-конфиг (по умолчанию — из $%s, иначе без конфига)"
                             % config.ENV_VAR)
    parser.add_argument("--rhel", type=_rhel,
                        help="версия RHEL: 9 — только 9, 9.2 — только 9.2 "
                             "(или rhel в конфиге)")
    parser.add_argument("--koji-url", help="URL kojihub (или koji.hub в конфиге)")
    parser.add_argument("--tag", help="koji-тег (или koji.tag в конфиге)")
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


def _read_table(path: str):
    try:
        return table.read(path)
    except table.TableError as exc:
        raise _Fatal("таблица %s" % exc)


def _open_output(path: str):
    """Дескриптор выхода: для файла — временник рядом, для замены атомарным
    os.replace после успешной записи; неверный путь падает сразу, до сети.

    Возвращает (handle, tmp_path, final_path); tmp_path is None для stdout —
    там подменять нечего и закрывать сам поток не нужно.
    """
    if path == STDIO:
        return sys.stdout, None, None
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", dir=directory, prefix=".vulnsheet-", suffix=".tmp",
            delete=False, newline="", encoding="utf-8")
    except OSError as exc:
        raise _Fatal("выход не пишется: %s" % exc)
    return handle, handle.name, path


def _check_rejects_dir(path: str) -> None:
    """Каталог явного --rejects проверяем сразу, а не после koji и VEX."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    if not os.path.isdir(directory) or not os.access(directory, os.W_OK):
        raise _Fatal("файл отбраковки не пишется: %s" % path)


def _write_rejects(path: str, rejects) -> None:
    if rejects:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n\n".join(r.text for r in rejects) + "\n")
        except OSError as exc:
            raise _Fatal("файл отбраковки не пишется: %s" % exc)
        logger.warning("битые блоки (%d) записаны в %s", len(rejects), path)
    elif os.path.exists(path):
        try:
            os.remove(path)
        except OSError as exc:
            # старый файл — не повод ронять свежий прогон
            logger.warning("не удалось удалить %s от прошлого прогона: %s", path, exc)
        else:
            logger.info("удалён %s от прошлого прогона: битых блоков нет", path)


def _summary(rows) -> None:
    """Сводка по строкам выхода; прочерки — строки, где спрашивать было нечего."""
    states = Counter(r[report.RHEL_STATE].split(" (", 1)[0] for r in rows
                     if r[report.RHEL_STATE] != report.EMPTY)
    if states:
        logger.info("RHEL state: %s", ", ".join(
            "%s %d" % item for item in sorted(states.items(), key=lambda kv: (-kv[1], kv[0]))))
    marks = Counter(r[report.SL_NVR] if r[report.SL_NVR] in (kojiclient.NOT_FOUND, kojiclient.ERROR)
                    else "found" for r in rows if r[report.SL_NVR] != report.EMPTY)
    logger.info("SL NVR: найдено %d, NOT_FOUND %d, ERROR %d", marks["found"],
                marks[kojiclient.NOT_FOUND], marks[kojiclient.ERROR])


def _settings(args):
    """Конфиг и три обязательных значения: флаг > конфиг > значение в коде."""
    path = args.config or os.environ.get(config.ENV_VAR) or None
    cfg = config.load_config(path)
    if path:
        logger.info("конфиг: %s", path)
    else:
        logger.info("без конфига")
    rhel = args.rhel or cfg.rhel
    hub = args.koji_url or cfg.koji_hub
    tag = args.tag or cfg.koji_tag
    for value, flag, key in ((rhel, "--rhel", "rhel"),
                             (hub, "--koji-url", "koji.hub"),
                             (tag, "--tag", "koji.tag")):
        if not value:
            raise _Fatal("нужен %s или %s в конфиге" % (flag, key))
    return cfg, rhel, hub, tag


def _merge(records, tasks, fresh):
    if records is None:
        return merge.build(tasks, fresh)
    if tasks is None:
        return merge.refresh(records, fresh)
    return merge.sync(records, tasks, fresh)


def _report_outcome(outcome, synced: bool) -> None:
    if synced:
        logger.info("совпало %d, Missing %d, новых %d",
                    outcome.matched, outcome.missing, outcome.added)
        if outcome.repeated:
            logger.info("повторов троек в блоках %d — действует первый блок",
                        outcome.repeated)
    for note in outcome.kept_koji:
        logger.warning("запись %d (%s %s): koji не ответил — оставлен прежний SL NVR",
                       note.number, note.cve, note.component)
    for note in outcome.kept_vex:
        logger.warning("запись %d (%s %s): VEX не получен — оставлены прежние данные VEX",
                       note.number, note.cve, note.component)
    for note in outcome.skipped:
        logger.warning("запись %d (%s %s): нет CVE-ID или компонента — строка оставлена как есть",
                       note.number, note.cve, note.component)


def _run(args) -> int:
    cfg, rhel, hub, tag = _settings(args)
    logger.info("режим: %s", MODES[(args.blocks is not None, args.table is not None)])
    records = None
    if args.table is not None:
        records = _read_table(args.table)
        logger.info("таблица %s: строк %d", args.table, len(records))
    tasks, rejects = None, []
    if args.blocks is not None:
        tasks, rejects = parse(_read_input(args.blocks))
        # в режиме 3 пустые блоки иначе молча сделали бы все строки Missing
        if not tasks and not rejects:
            raise _Fatal("во входе нет ни одного блока")
        for reject in rejects:
            logger.warning("блок %d «%s» отбракован: %s", reject.number,
                           reject.text.split("\n", 1)[0].strip(), reject.reason)
        # режим 3: если из блоков не осталось ни одного годного, синхронизация
        # молча пометила бы Missing вообще все строки таблицы
        if args.table is not None and not tasks:
            raise _Fatal("в блоках нет ни одного годного блока — синхронизация "
                        "пометила бы все строки Missing")

    wanted = merge.pairs(records, tasks)  # пара на строку выхода, с повторами
    unique = list(dict.fromkeys(wanted))
    cves = list(dict.fromkeys(cve for cve, _ in unique))
    packages = list(dict.fromkeys(component for _, component in unique))
    logger.info("хаб %s, тег %s, RHEL %s", hub, tag, rhel)
    streams = {name: cfg.stream_for(name, rhel) for name in packages}
    applied = Counter(name for _, name in wanted if streams[name])
    if applied:
        logger.info("стримы VEX для RHEL %s: %s", rhel, ", ".join(
            "%s → %s (%d)" % (name, streams[name], count) for name, count in applied.items()))
    if tasks is not None:
        logger.info("блоков %d, отбраковано %d; CVE %d, пакетов %d",
                    len(tasks) + len(rejects), len(rejects), len(cves), len(packages))
    else:
        logger.info("CVE %d, пакетов %d", len(cves), len(packages))

    # выход открываем до сети: неверный путь должен падать сразу, и не
    # затирать прежний отчёт — пишем во временник рядом, подменяем в конце;
    # таблица к этому моменту прочитана целиком, так что -o может быть ею
    out, tmp_path, final_path = _open_output(args.output)
    if args.rejects and args.blocks is not None:
        _check_rejects_dir(args.rejects)
    try:
        nvrs, indices, failures = {}, {}, {}
        if unique:
            session = kojiclient.connect(hub)
            nvrs = kojiclient.latest_builds(session, tag, packages)
            settings = cfg.vex._replace(
                cache_dir=vex.prepare_cache(cfg.vex.cache_dir or _cache_dir()))
            indices, failures = vex.fetch_all(cves, settings)
        verdicts = {(cve, name): vex.Verdict(state=vex.FETCH_ERROR) if cve in failures
                    else vex.lookup(indices[cve], name, rhel, streams[name])
                    for cve, name in unique}
        outcome = _merge(records, tasks, merge.Fresh(nvrs, verdicts))
        report.write(outcome.rows, out)
    except BaseException:
        if tmp_path is not None:
            out.close()
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    else:
        if tmp_path is not None:
            out.close()
            os.replace(tmp_path, final_path)
    if args.output != STDIO:
        logger.info("написан %s", args.output)

    # файл отбраковки — дело блоков: в режиме 2 его не трогаем
    if args.blocks is not None:
        _write_rejects(rejects_path(args.output, args.rejects), rejects)
    _report_outcome(outcome, synced=records is not None and tasks is not None)
    _summary(outcome.rows)
    partial = (rejects or failures or kojiclient.ERROR in nvrs.values()
               or outcome.skipped)
    return EXIT_PARTIAL if partial else EXIT_OK


def _fatal(message: str) -> int:
    """Одна строка пользователю, трейсбек — только на debug."""
    logger.error("%s", message)
    logger.debug("трейсбек", exc_info=True)
    return EXIT_FATAL


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.blocks is None and args.table is None:
        parser.error("нужен --blocks или --table")
    if args.table == STDIO:
        parser.error("--table: таблица — только файл, не stdin")
    logs.configure(args.log_level)
    started = time.monotonic()
    try:
        code = _run(args)
    except _Fatal as exc:
        return _fatal(str(exc))
    except config.ConfigError as exc:
        return _fatal(str(exc))
    except kojiclient.KojiError as exc:
        return _fatal("koji: %s" % exc)
    except BrokenPipeError:
        # читатель (head и т.п.) закрыл трубу раньше нас — это не ошибка
        # программы; чтобы интерпретатор не напечатал при выходе
        # "Exception ignored" из-за непрочитанного stdout, перенаправляем
        # его в /dev/null
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except (AttributeError, OSError):
            pass
        return EXIT_PARTIAL
    except Exception as exc:  # непредвиденное не должно ронять CLI трейсбеком
        return _fatal("фатальная ошибка: %s" % exc)
    logger.info("всего за %.1f с", time.monotonic() - started)
    return code
