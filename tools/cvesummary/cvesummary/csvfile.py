"""CSV таблицы процесса — в тот же Sheet, что и xlsx; все ячейки текстовые.

Кодировка — UTF-8 (с BOM или без), иначе cp1251: так CSV сохраняет русский
Excel. Разделитель — тот из «;», «,» и табуляции, при котором в разобранной
записи находится ячейка «CVE ID», а из таких — с самой длинной шапкой: так
не сбивают ни запятые в кавычках, ни строка-заголовок со словами «CVE ID»
над шапкой. Шапки нет ни при каком — «;», как пишет vulnsheet. Номер строки — номер записи с 1: поле в кавычках с
переводом строки остаётся одной строкой, как в Excel. Ошибки — CsvError без
пути к файлу; путь добавляет вызывающий.
"""
import csv
import io
from typing import List, NamedTuple, Optional

from .xlsx import Cell, Row, Sheet

DELIMITERS = (";", ",", "\t")
DEFAULT_DELIMITER = ";"
_HEADER_KEY = "cve id"
# у csv предел поля 128 КиБ — длинный комментарий в него не влезает
_FIELD_LIMIT = 2 ** 31 - 1


class CsvError(Exception):
    """Файл не читается как CSV."""


class CsvFile(NamedTuple):
    sheet: Sheet     # name пустое: листов у CSV нет
    delimiter: str
    encoding: str    # "utf-8" или "cp1251"


def read(path: str) -> CsvFile:
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise CsvError("не открывается: %s" % exc.strerror)
    if b"\0" in data:
        # csv на 3.11+ нулевые байты пропускает молча, а это не текст:
        # xlsx под именем .csv или «Юникод-текст» Excel в UTF-16
        raise CsvError("в файле нулевые байты — это не CSV в UTF-8 или cp1251 "
                       "(xlsx с расширением .csv? UTF-16?)")
    text, encoding = _decode(data)
    # предел поля в csv общий на процесс — возвращаем прежний
    limit = csv.field_size_limit(_FIELD_LIMIT)
    try:
        delimiter = _delimiter(text)
        records = list(_records(text, delimiter))
    except csv.Error as exc:
        raise CsvError("не разбирается как CSV: %s" % exc)
    finally:
        csv.field_size_limit(limit)
    rows = [Row(n, [Cell(value) for value in record]) for n, record in enumerate(records, 1)]
    return CsvFile(Sheet("", rows, False), delimiter, encoding)


def _decode(data: bytes):
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1251"), "cp1251"
    except UnicodeDecodeError as exc:
        raise CsvError("кодировка не UTF-8 и не cp1251: %s" % exc)


def _records(text: str, delimiter: str):
    return csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)


def _header(text: str, delimiter: str) -> Optional[List[str]]:
    for record in _records(text, delimiter):
        if any(" ".join(value.split()).lower() == _HEADER_KEY for value in record):
            return record
    return None


def _delimiter(text: str) -> str:
    best, width = DEFAULT_DELIMITER, 0
    for sep in DELIMITERS:
        header = _header(text, sep)
        if header is not None and len(header) > width:
            best, width = sep, len(header)
    return best
