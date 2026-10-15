"""Точка входа: блоки задач и/или прежняя таблица → koji, VEX и GitLab → CSV."""
import argparse
import logging
import os
import stat
import sys
import tempfile
import time
from collections import Counter
from typing import List, NamedTuple, Optional

from . import (__version__, config, gitlabclient, httpclient, kojiclient, logs, merge,
               patches, ranges, report, table, vex)
from .tasks import parse

logger = logging.getLogger(__name__)

EXIT_OK = 0
# CSV записан, но есть отбраковка, ERROR koji, fetch error (в том числе там,
# где из-за сбоя оставлены прежние koji или VEX), компоненты, чьи патчи в
# GitLab проверить не удалось, строки таблицы, по которым нечего спрашивать,
# либо читатель оборвал stdout (broken pipe) — таблица дописана не до конца
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

    final_path — путь к файлу, который меняется (символическая ссылка
    разыменована: os.replace должен подменить её цель, а не саму ссылку).

    Возвращает (handle, tmp_path, final_path); tmp_path is None для stdout —
    там подменять нечего и закрывать сам поток не нужно.
    """
    if path == STDIO:
        return sys.stdout, None, None
    final_path = os.path.realpath(path)
    directory = os.path.dirname(final_path) or "."
    try:
        handle = tempfile.NamedTemporaryFile(
            "w", dir=directory, prefix=".vulnsheet-", suffix=".tmp",
            delete=False, newline="", encoding="utf-8")
    except OSError as exc:
        raise _Fatal("выход не пишется: %s" % exc)
    return handle, handle.name, final_path


def _match_permissions(tmp_path: str, final_path: str) -> None:
    """Права временника — как у файла, который он подменит: у уже
    существующего файла — его права, у нового — режим по умолчанию (umask).
    NamedTemporaryFile создаёт временник с правами 0600, поэтому подмена
    без этого поменяла бы права итогового файла на любой замене."""
    try:
        mode = stat.S_IMODE(os.stat(final_path).st_mode)
    except OSError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    try:
        os.chmod(tmp_path, mode)
    except OSError as exc:
        logger.warning("не удалось выставить права %s: %s", tmp_path, exc)


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


def _reasons(rejects, nvrs, failures, found, range_failed, outcome) -> List[str]:
    """Почему код возврата 1; пусто — код 0."""
    counts = (("битых блоков", len(rejects)),
              ("пакетов с ERROR от koji", sum(1 for nvr in nvrs.values() if nvr == kojiclient.ERROR)),
              ("CVE без документа VEX", len(failures)),
              ("компонентов с ошибкой проверки патчей", len(found.failed)),
              ("CVE без диапазонов из-за сбоя", len(range_failed)),
              ("строк без CVE-ID или компонента", len(outcome.skipped)))
    return ["%s %d" % item for item in counts if item[1]]


def _item(depth: int, text: str) -> None:
    """Пункт итога: отдельная строка журнала, вложенность — отступом."""
    logger.info("%s- %s", "  " * depth, text)


def _footer(args, cfg, rejects, found, outcome, reasons) -> None:
    """Итог прогона — последним блоком, списком, с теми же метками, что у
    шапки: что сделано и сколько чего найдено. Прочерки в колонках — строки,
    где спрашивать было нечего, они не считаются."""
    rows = outcome.rows
    logger.info("итог:")
    _item(1, "%s, строк %d" % ("выведено в stdout" if args.output == STDIO
                                else "написан %s" % args.output, len(rows)))
    if args.table is not None and args.blocks is not None:
        _item(2, "совпало %d" % outcome.matched)
        _item(2, "Missing %d" % outcome.missing)
        _item(2, "новых %d" % outcome.added)
        if outcome.repeated:
            _item(2, "повторов троек в блоках %d — действует первый блок" % outcome.repeated)

    marks = Counter(r[report.SL_NVR] if r[report.SL_NVR] in (kojiclient.NOT_FOUND, kojiclient.ERROR)
                    else "found" for r in rows if r[report.SL_NVR] != report.EMPTY)
    _item(1, "koji:")
    _item(2, "найдено %d" % marks["found"])
    _item(2, "NOT_FOUND %d" % marks[kojiclient.NOT_FOUND])
    _item(2, "ERROR %d" % marks[kojiclient.ERROR])
    if outcome.kept_koji:
        _item(2, "оставлен прежний SL NVR %d" % len(outcome.kept_koji))

    states = Counter(r[report.RHEL_STATE].split(" (", 1)[0] for r in rows
                     if r[report.RHEL_STATE] != report.EMPTY)
    _item(1, "VEX:")
    for state, count in sorted(states.items(), key=lambda kv: (-kv[1], kv[0])):
        _item(2, "%s %d" % (state, count))
    if not states:
        _item(2, "строк нет")
    if outcome.kept_vex:
        _item(2, "оставлены прежние данные VEX %d" % len(outcome.kept_vex))

    if cfg.gitlab is None:
        _item(1, "GitLab: не задан — патчи не проверялись")
    else:
        kinds, fates = outcome.patch_kinds, outcome.note_fates
        _item(1, "GitLab, строки:")
        for source in patches.SOURCES:
            _item(2, "%s: найден %d, убран из ветки %d, только в ветке %d" % (
                source, kinds.get((source, patches.FOUND), 0),
                kinds.get((source, patches.REMOVED), 0),
                kinds.get((source, patches.BRANCH_ONLY), 0)))
        _item(2, "пометка " + ", ".join("%s %d" % (fate, fates.get(fate, 0))
                                         for fate in merge.FATES))
        _item(1, "GitLab, компоненты:")
        for kind in patches.KINDS:
            _item(2, "%s %d" % (kind, found.kinds.get(kind, 0)))
        for kind in patches.SPEC_KINDS:
            _item(2, "%s %d" % (kind, found.spec_kinds.get(kind, 0)))
    if cfg.ranges is None:
        _item(1, "диапазоны версий: не заданы — не сверялись")
    else:
        kinds, sources = outcome.range_kinds, outcome.range_sources
        _item(1, "диапазоны версий:")
        _item(2, "в диапазоне %d" % kinds.get(True, 0))
        _item(2, "вне диапазона %d" % kinds.get(False, 0))
        _item(2, "неизвестен %d" % kinds.get(None, 0))
        _item(2, "источник: %s" % ", ".join("%s %d" % (source, sources.get(source, 0))
                                             for source in (ranges.NVD, ranges.CVEORG)))
    if rejects:
        _item(1, "отбраковано блоков %d → %s" % (len(rejects),
                                                 rejects_path(args.output, args.rejects)))
    if reasons:
        _item(1, "код возврата 1:")
        for reason in reasons:
            _item(2, reason)
    else:
        _item(1, "код возврата 0")


def _settings(args):
    """Конфиг и три обязательных значения: флаг > конфиг > значение в коде."""
    path = args.config or os.environ.get(config.ENV_VAR) or None
    cfg = config.load_config(path)
    rhel = args.rhel or cfg.rhel
    hub = args.koji_url or cfg.koji_hub
    tag = args.tag or cfg.koji_tag
    for value, flag, key in ((rhel, "--rhel", "rhel"),
                             (hub, "--koji-url", "koji.hub"),
                             (tag, "--tag", "koji.tag")):
        if not value:
            raise _Fatal("нужен %s или %s в конфиге" % (flag, key))
    return cfg, rhel, hub, tag


def _gitlab_token(settings) -> Optional[str]:
    """Токен GitLab из окружения; файл или копипаста приносят перевод строки —
    срезаем."""
    if settings is None:
        return None
    return (os.environ.get(settings.token_env) or "").strip() or None


def _patches(session, nvrs, settings, token):
    """Патчи под CVE по компонентам с найденным билдом; без секции gitlab —
    ничего не спрашивается."""
    if settings is None:
        return patches.Result({}, ())
    found = {name: nvr for name, nvr in nvrs.items()
             if nvr not in (kojiclient.NOT_FOUND, kojiclient.ERROR)}
    if not found:
        return patches.Result({}, ())
    infos = kojiclient.build_infos(session, found.values())
    client = gitlabclient.GitlabClient(
        settings.hosts, token=token, patch_dir=settings.patch_dir,
        transport=httpclient.UrllibTransport(timeout=settings.timeout),
        retries=settings.retries, default_host=settings.default_host)
    return patches.find({name: infos.get(nvr) for name, nvr in found.items()}, client,
                        settings.jobs)


def _place(path: str, stream: str) -> str:
    return stream if path == STDIO else path


def _header(args, cfg, run) -> None:
    """Шапка прогона — до первого запроса в сеть: что прочитано, куда пишем,
    какие источники с какими настройками и сколько будет спрашиваться.

    Десятиминутный прогон должен сразу показать, что он сделает: иначе о
    забытой секции конфига узнаёшь только в его конце."""
    logger.info("vulnsheet %s", __version__)
    path = args.config or os.environ.get(config.ENV_VAR)
    logger.info("конфиг: %s" % path if path else "без конфига")
    inputs = []
    if run.records is not None:
        inputs.append("таблица %s (строк %d)" % (args.table, len(run.records)))
    if run.tasks is not None:
        inputs.append("блоки %s" % _place(args.blocks, "stdin"))
    logger.info("режим: %s — %s → %s", MODES[(args.blocks is not None, args.table is not None)],
                " + ".join(inputs), _place(args.output, "stdout"))
    if run.tasks is not None:
        rejected = len(run.rejects)
        logger.info("вход: блоков %d, отбраковано %d%s", len(run.tasks) + rejected, rejected,
                    " → %s" % rejects_path(args.output, args.rejects) if rejected else "")
    logger.info("koji: хаб %s, тег %s", run.hub, run.tag)
    cache = "%s (%s)" % (cfg.vex.cache_dir or _cache_dir(),
                         "живёт %d с" % cfg.vex.cache_ttl if cfg.vex.cache_ttl
                         else "не читается")
    logger.info("VEX: RHEL %s, кэш %s, потоков %d", run.rhel, cache, cfg.vex.jobs)
    applied = Counter(name for _, name in run.wanted if run.streams[name])
    if applied:
        logger.info("стримы VEX для RHEL %s: %s", run.rhel, ", ".join(
            "%s → %s (%d)" % (name, run.streams[name], count) for name, count in applied.items()))
    renamed = Counter(name for _, name in run.wanted if run.aliases[name])
    if renamed:
        logger.info("имена VEX: %s", ", ".join(
            "%s → %s (%d)" % (name, ", ".join(run.aliases[name]), count)
            for name, count in renamed.items()))
    gitlab = cfg.gitlab
    if gitlab is None:
        logger.info("GitLab: не задан в конфиге — патчи не проверяются")
    else:
        hosts = ", ".join("%s (по умолчанию)" % host if host == gitlab.default_host else host
                          for host in gitlab.hosts)
        token = ("токен из $%s" % gitlab.token_env if run.token else
                 "без токена ($%s пуст) — видны только публичные проекты" % gitlab.token_env)
        logger.info("GitLab: %s, каталог %s, %s, потоков %d", hosts, gitlab.patch_dir, token,
                    gitlab.jobs)
    if cfg.ranges is None:
        logger.info("диапазоны: не заданы в конфиге — версии не сверяются")
    else:
        env = cfg.ranges.nvd_key_env
        key = ("NVD с ключом из $%s" % env if run.nvd_key else
               "NVD без ключа ($%s пуст, запрос раз в %g с)" % (env, ranges.PAUSE))
        logger.info("диапазоны: %s, CVE.org, кэш %s (живёт %d с), потоков %d", key,
                    _ranges_cache(cfg), cfg.ranges.cache_ttl, cfg.ranges.jobs)
    if not run.packages:
        logger.info("план: спрашивать нечего — в сеть не идём")
        return
    plan = "koji — пакетов %d, VEX — CVE %d" % (len(run.packages), len(run.cves))
    if gitlab is not None:
        plan += ", GitLab — патчи по билдам из koji (до %d)" % len(run.packages)
    if cfg.ranges is not None:
        plan += ", диапазоны — CVE %d" % len(run.cves)
    logger.info("план: %s", plan)


def _ranges_cache(cfg) -> str:
    return os.path.join(cfg.vex.cache_dir or _cache_dir(), "ranges")


def _range_notes(cfg, unique, nvrs, nvd_key):
    """(CVE, компонент) → RangeNote и CVE, по которым диапазоны не известны
    из-за сбоя. Без секции ranges ничего не спрашивается."""
    settings = cfg.ranges
    if settings is None or not unique:
        return {}, set()
    docs, _ = ranges.fetch_all((cve for cve, _ in unique), ranges.RangeSettings(
        cache_dir=_ranges_cache(cfg), cache_ttl=settings.cache_ttl, jobs=settings.jobs,
        retries=settings.retries, timeout=settings.timeout, nvd_key=nvd_key))
    notes, failed = {}, set()
    for cve, name in unique:
        version = ranges.upstream_version(nvrs.get(name, ""))
        if version is None or cve not in docs:
            continue
        found, broken = ranges.ranges_for(docs[cve], settings.names_for(name))
        if broken:
            failed.add(cve)
            continue
        notes[(cve, name)] = ranges.judge(version, found)
    return notes, failed


def _warn_rejects(rejects) -> None:
    for reject in rejects:
        logger.warning("блок %d «%s» отбракован: %s", reject.number,
                       reject.text.split("\n", 1)[0].strip(), reject.reason)


class _Run(NamedTuple):
    """Что прочитано и что будет спрошено: общее для шапки и самой работы."""
    rhel: str
    hub: str
    tag: str
    records: Optional[list]
    tasks: Optional[list]
    rejects: list
    wanted: list            # пара (CVE, компонент) на строку выхода, с повторами
    cves: list
    packages: list
    streams: dict
    aliases: dict
    token: Optional[str]
    nvd_key: Optional[str]


def _merge(records, tasks, fresh):
    if records is None:
        return merge.build(tasks, fresh)
    if tasks is None:
        return merge.refresh(records, fresh)
    return merge.sync(records, tasks, fresh)


def _warn_outcome(outcome) -> None:
    """Строки, с которыми что-то не так, — по одной, до итога."""
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
    records = None
    if args.table is not None:
        records = _read_table(args.table)
    tasks, rejects = None, []
    if args.blocks is not None:
        tasks, rejects = parse(_read_input(args.blocks))
        # в режиме 3 пустые блоки иначе молча сделали бы все строки Missing
        if not tasks and not rejects:
            raise _Fatal("во входе нет ни одного блока")
        # режим 3: если из блоков не осталось ни одного годного, синхронизация
        # молча пометила бы Missing вообще все строки таблицы
        if args.table is not None and not tasks:
            _warn_rejects(rejects)
            raise _Fatal("в блоках нет ни одного годного блока — синхронизация "
                        "пометила бы все строки Missing")

    wanted = merge.pairs(records, tasks)  # пара на строку выхода, с повторами
    unique = list(dict.fromkeys(wanted))
    cves = list(dict.fromkeys(cve for cve, _ in unique))
    packages = list(dict.fromkeys(component for _, component in unique))
    streams = {name: cfg.stream_for(name, rhel) for name in packages}
    aliases = {name: cfg.names_for(name) for name in packages}
    token = _gitlab_token(cfg.gitlab)
    # ключ NVD, как и токен GitLab, срезаем: файл и копипаста приносят перевод строки
    nvd_key = ((os.environ.get(cfg.ranges.nvd_key_env) or "").strip() or None
               if cfg.ranges is not None else None)
    _header(args, cfg, _Run(rhel, hub, tag, records, tasks, rejects, wanted, cves, packages,
                            streams, aliases, token, nvd_key))
    _warn_rejects(rejects)

    # выход открываем до сети: неверный путь должен падать сразу, и не
    # затирать прежний отчёт — пишем во временник рядом, подменяем в конце;
    # таблица к этому моменту прочитана целиком, так что -o может быть ею
    out, tmp_path, final_path = _open_output(args.output)
    if args.rejects and args.blocks is not None:
        _check_rejects_dir(args.rejects)
    try:
        nvrs, indices, failures = {}, {}, {}
        found = patches.Result({}, ())
        range_notes, range_failed = {}, set()
        if unique:
            session = kojiclient.connect(hub)
            nvrs = kojiclient.latest_builds(session, tag, packages)
            settings = cfg.vex._replace(
                cache_dir=vex.prepare_cache(cfg.vex.cache_dir or _cache_dir()))
            indices, failures = vex.fetch_all(cves, settings)
            found = _patches(session, nvrs, cfg.gitlab, token)
            range_notes, range_failed = _range_notes(cfg, unique, nvrs, nvd_key)
        verdicts = {(cve, name): vex.Verdict(state=vex.FETCH_ERROR) if cve in failures
                    else vex.lookup(indices[cve], name, rhel, streams[name], aliases[name])
                    for cve, name in unique}
        outcome = _merge(records, tasks, merge.Fresh(nvrs, verdicts, found.notes, range_notes))
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
            _match_permissions(tmp_path, final_path)
            os.replace(tmp_path, final_path)
    # файл отбраковки — дело блоков: в режиме 2 его не трогаем
    if args.blocks is not None:
        _write_rejects(rejects_path(args.output, args.rejects), rejects)
    _warn_outcome(outcome)
    reasons = _reasons(rejects, nvrs, failures, found, range_failed, outcome)
    _footer(args, cfg, rejects, found, outcome, reasons)
    return EXIT_PARTIAL if reasons else EXIT_OK


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
