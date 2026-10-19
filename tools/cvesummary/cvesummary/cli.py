"""Точка входа: xlsx таблицы процесса → HTML-сводка."""
import argparse
import datetime
import logging
import os
import sys
import tempfile
from typing import List, Optional

from . import __version__, page, table, xlsx

logger = logging.getLogger("cvesummary")

EXIT_OK = 0
EXIT_FATAL = 2


def _today() -> datetime.date:
    return datetime.date.today()


def _date(text: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError("дата нужна в виде ГГГГ-ММ-ДД: %r" % text)


def default_output(path: str) -> str:
    return os.path.splitext(path)[0] + ".html"


def _parse(argv):
    parser = argparse.ArgumentParser(
        prog="cvesummary",
        description="Сводка по CVE: xlsx таблицы процесса → одна HTML-страница.")
    parser.add_argument("table", help="xlsx таблицы процесса; читается первый лист")
    parser.add_argument("-o", "--output",
                        help="куда записать страницу; по умолчанию рядом с таблицей, <имя>.html")
    parser.add_argument("--as-of", type=_date,
                        help="дата отчёта ГГГГ-ММ-ДД; по умолчанию сегодня")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser.parse_args(argv)


def _setup_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse(argv)
    _setup_logging()
    as_of = args.as_of or _today()
    output = args.output or default_output(args.table)
    if (os.path.exists(output) and os.path.exists(args.table)
            and os.path.samefile(output, args.table)):
        logger.error("%s: страница записалась бы поверх таблицы — задайте другой -o", output)
        return EXIT_FATAL
    try:
        sheet = xlsx.read(args.table)
        found = table.build(sheet)
    except (xlsx.XlsxError, table.TableError) as exc:
        logger.error("%s: %s", args.table, exc)
        return EXIT_FATAL

    logger.info("лист «%s», шапка в строке %d", sheet.name, found.header_row)
    found_names = [name for key, name in table.FIELDS
                   if key not in table.REQUIRED and name not in found.missing]
    logger.info("колонки: %s", ", ".join(found_names))
    if found.missing:
        logger.info("нет колонок, читаются пустыми: %s", ", ".join(found.missing))
    for name in found.duplicates:
        logger.warning("колонка «%s» повторяется — взята первая", name)
    logger.info("строк: %d; без CVE ID пропущено: %d; дат не разобрано: %d",
                len(found.rows), found.skipped, found.bad_dates)
    if not found.rows:
        logger.warning("строк с CVE ID нет — страница будет пустой")
    logger.info("дата отчёта: %s", as_of.isoformat())

    data = {
        "meta": {"version": __version__, "source": os.path.basename(args.table),
                 "sheet": sheet.name, "header_row": found.header_row,
                 "as_of": as_of.isoformat(), "skipped": found.skipped,
                 "missing": found.missing, "bad_dates": found.bad_dates},
        "rows": found.rows,
    }
    existed = os.path.exists(output)
    try:
        _write(output, page.render(data))
    except OSError as exc:
        logger.error("%s: не записывается: %s", output, exc)
        return EXIT_FATAL
    if existed:
        logger.warning("%s: файл уже был — перезаписан", output)
    logger.info("записано: %s", output)
    return EXIT_OK


def _write(path: str, text: str) -> None:
    """Через временный файл рядом: оборванная запись не оставит полстраницы."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".cvesummary-", suffix=".html", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        # mkstemp создаёт файл 0600, а страницу пересылают людям
        os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask
