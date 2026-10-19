"""Чтение прежней таблицы vulnsheet — входа режимов обновления.

Таблица — ровно то, что пишет report.write: UTF-8 (BOM допускается), ';',
кавычки по правилам CSV, заголовок report.COLUMNS, в каждой записи 22
ячейки. Ячейки отдаются дословно: в них ручные данные людей. Любое
отклонение — TableError: выбросить «кривую» строку нельзя. Таблицу
vulnsheet 1.x (20 колонок, без P и D) не читаем: признаки в ней жили в
комментарии, и перенести их можно только руками.
"""
import csv
from typing import List, NamedTuple

from .report import COLUMNS

# заголовок vulnsheet 1.x: те же колонки, но без P и D
_COLUMNS_1 = [name for name in COLUMNS if name not in ("P", "D")]


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
    names = [cell.strip() for cell in header.cells]
    if names == _COLUMNS_1:
        raise TableError("%s: таблица vulnsheet 1.x — в ней нет колонок P и D; "
                         "добавьте их перед «SL NVR (latest build)» (значение «-»)"
                         % path)
    if names != COLUMNS:
        raise TableError("%s: запись %d: заголовок не как у vulnsheet "
                         "(разделитель ;, UTF-8?)" % (path, header.number))
    for record in rows:
        if len(record.cells) != len(COLUMNS):
            raise TableError("%s: запись %d: ячеек %d, ожидается %d"
                             % (path, record.number, len(record.cells), len(COLUMNS)))
    return rows
