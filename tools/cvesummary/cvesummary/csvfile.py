"""CSV таблицы процесса — в тот же Sheet, что и xlsx; все ячейки текстовые.

Кодировка — UTF-8 (с BOM или без), иначе cp1251: так CSV сохраняет русский
Excel. Разделитель — тот из «;», «,» и табуляции, которого больше всего в
строке шапки (первой строке с «CVE ID»); если там нет ни одного, «;», как
пишет vulnsheet. Номер строки — номер записи с 1: поле в кавычках с
переводом строки остаётся одной строкой, как в Excel. Ошибки — CsvError без
пути к файлу; путь добавляет вызывающий.
"""
import csv
import io
from typing import NamedTuple

from .xlsx import Cell, Row, Sheet

DELIMITERS = (";", ",", "\t")
DEFAULT_DELIMITER = ";"
_HEADER_KEY = "cve id"


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
    delimiter = _delimiter(text)
    try:
        records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    except csv.Error as exc:
        raise CsvError("не разбирается как CSV: %s" % exc)
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


def _delimiter(text: str) -> str:
    line = next((line for line in text.splitlines() if _HEADER_KEY in line.lower()), "")
    counts = {sep: line.count(sep) for sep in DELIMITERS}
    best = max(DELIMITERS, key=lambda sep: counts[sep])
    return best if counts[best] else DEFAULT_DELIMITER
