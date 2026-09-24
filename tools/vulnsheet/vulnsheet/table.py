"""Чтение прежней таблицы vulnsheet — входа режимов обновления.

Таблица — ровно то, что пишет report.write: UTF-8 (BOM допускается), ';',
кавычки по правилам CSV, заголовок report.COLUMNS, в каждой записи 20
ячеек. Ячейки отдаются дословно: в них ручные данные людей. Любое
отклонение — TableError: выбросить «кривую» строку нельзя.
"""
import csv
from typing import List, NamedTuple

from .report import COLUMNS


class TableError(Exception):
    """Таблица не читается или не в формате vulnsheet."""


class Record(NamedTuple):
    """Строка таблицы: номер записи в файле (заголовок — 1) и ячейки."""
    number: int
    cells: List[str]


def read(path: str) -> List[Record]:
    """Строки данных без заголовка; полностью пустые записи пропускаются."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            raw = list(csv.reader(handle, delimiter=";", strict=True))
    except UnicodeDecodeError as exc:
        raise TableError("%s: не в UTF-8: %s" % (path, exc))
    except OSError as exc:
        raise TableError("%s: не читается: %s" % (path, exc))
    except csv.Error as exc:
        raise TableError("%s: ошибка CSV: %s" % (path, exc))

    records = [Record(number, cells) for number, cells in enumerate(raw, 1)
               if any(cell.strip() for cell in cells)]
    if not records:
        raise TableError("%s: пустой файл, нет заголовка" % path)
    header, rows = records[0], records[1:]
    if [cell.strip() for cell in header.cells] != COLUMNS:
        raise TableError("%s: запись %d: заголовок не как у vulnsheet"
                         % (path, header.number))
    for record in rows:
        if len(record.cells) != len(COLUMNS):
            raise TableError("%s: запись %d: ячеек %d, ожидается %d"
                             % (path, record.number, len(record.cells), len(COLUMNS)))
    return rows
