"""Первый лист xlsx: своим разбором, без openpyxl — в RHEL 9 его нет.

Читаются только книга (порядок листов), связи листа, общие строки и стили
— последние ради одного: отличить дату от числа. Ошибки — XlsxError без
пути к файлу; путь добавляет вызывающий.
"""
import datetime
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, NamedTuple, Optional

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# встроенные форматы дат и времени, ECMA-376 часть 1, 18.8.30
_DATE_IDS = frozenset(range(14, 23)) | {45, 46, 47}
# в коде формата не считаются: текст в кавычках, [цвет]/[$-локаль],
# экранированный символ и пробел/заполнитель под символ (_x, *x)
_NOT_CODE = re.compile(r'"[^"]*"|\[[^\]]*\]|\\.|[_*].')
_REF = re.compile(r"([A-Z]+)(\d+)$")
# Отсчёт системы 1900 — 30.12.1899: так серийные номера после 28.02.1900
# сходятся с Excel, который считает несуществующее 29.02.1900.
_EPOCH_1900 = datetime.date(1899, 12, 30)
_EPOCH_1904 = datetime.date(1904, 1, 1)


class XlsxError(Exception):
    """Файл не читается как xlsx."""


class Cell(NamedTuple):
    text: str                             # как показать
    number: Optional[float] = None        # число, если ячейка числовая
    date: Optional[datetime.date] = None  # дата, если число со стилем даты


class Row(NamedTuple):
    number: int        # номер строки листа, с 1
    cells: List[Cell]  # с колонки A; пропущенные ячейки — Cell("")


class Sheet(NamedTuple):
    name: str
    rows: List[Row]
    date1904: bool


def read(path: str) -> Sheet:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise XlsxError("не xlsx (не zip-архив): %s" % exc)
    except OSError as exc:
        raise XlsxError("не открывается: %s" % exc)
    with archive:
        try:
            return _read(archive)
        except KeyError as exc:
            raise XlsxError("в книге нет части: %s" % exc)
        except ET.ParseError as exc:
            raise XlsxError("битый XML: %s" % exc)
        except zipfile.BadZipFile as exc:
            raise XlsxError("битый архив: %s" % exc)


def serial_date(number: float, date1904: bool = False) -> datetime.date:
    """Серийный номер Excel → дата; время (дробная часть) отбрасывается."""
    epoch = _EPOCH_1904 if date1904 else _EPOCH_1900
    try:
        return epoch + datetime.timedelta(days=int(number))
    except (OverflowError, ValueError) as exc:
        raise ValueError("дата вне диапазона: %r (%s)" % (number, exc))


def is_date_format(code: str) -> bool:
    """Код формата числа — дата: d, m или y вне кавычек, […] и экранирования."""
    bare = _NOT_CODE.sub("", code).lower()
    return any(ch in bare for ch in "dmy")


def _read(archive) -> Sheet:
    book = _xml(archive, "xl/workbook.xml")
    pr = book.find(MAIN + "workbookPr")
    date1904 = pr is not None and pr.get("date1904") in ("1", "true")
    sheet = book.find(MAIN + "sheets/" + MAIN + "sheet")
    if sheet is None:
        raise XlsxError("в книге нет листов")
    target = _target(archive, sheet.get(REL + "id"))
    rows = _rows(_xml(archive, target), _shared(archive), _date_styles(archive), date1904)
    return Sheet(sheet.get("name", ""), rows, date1904)


def _xml(archive, name):
    with archive.open(name) as handle:
        return ET.parse(handle).getroot()


def _target(archive, rid) -> str:
    for rel in _xml(archive, "xl/_rels/workbook.xml.rels").iter(PKG + "Relationship"):
        if rel.get("Id") == rid:
            target = rel.get("Target", "")
            if target.startswith("/"):
                return target[1:]
            return posixpath.normpath(posixpath.join("xl", target))
    raise XlsxError("связь листа %s не найдена в xl/_rels/workbook.xml.rels" % rid)


def _shared(archive) -> List[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    return [_text(si) for si in _xml(archive, "xl/sharedStrings.xml").iter(MAIN + "si")]


def _text(node) -> str:
    """Текст <si>/<is>: простой <t> или куски <r><t>; фонетика <rPh> не в счёт."""
    parts = []
    for child in node:
        if child.tag == MAIN + "t":
            parts.append(child.text or "")
        elif child.tag == MAIN + "r":
            t = child.find(MAIN + "t")
            if t is not None:
                parts.append(t.text or "")
    return "".join(parts)


def _date_styles(archive) -> List[bool]:
    """Для каждого стиля cellXfs по порядку: дата ли это."""
    if "xl/styles.xml" not in archive.namelist():
        return []
    root = _xml(archive, "xl/styles.xml")
    custom = {}
    fmts = root.find(MAIN + "numFmts")
    if fmts is not None:
        for fmt in fmts.iter(MAIN + "numFmt"):
            custom[int(fmt.get("numFmtId", "0"))] = fmt.get("formatCode", "")
    xfs = root.find(MAIN + "cellXfs")
    if xfs is None:
        return []
    result = []
    for xf in xfs.iter(MAIN + "xf"):
        fid = int(xf.get("numFmtId", "0"))
        code = custom.get(fid)
        result.append(is_date_format(code) if code is not None else fid in _DATE_IDS)
    return result


def _column(ref: str) -> int:
    match = _REF.match(ref)
    if not match:
        raise XlsxError("неверный адрес ячейки %r" % ref)
    index = 0
    for ch in match.group(1):
        index = index * 26 + ord(ch) - 64
    return index - 1


def _rows(root, shared, date_styles, date1904) -> List[Row]:
    data = root.find(MAIN + "sheetData")
    if data is None:
        return []
    rows, last = [], 0
    for row in data.iter(MAIN + "row"):
        last = int(row.get("r") or last + 1)
        cells, nxt = [], 0
        for c in row.iter(MAIN + "c"):
            ref = c.get("r")
            index = _column(ref) if ref else nxt
            nxt = index + 1
            if index >= len(cells):
                cells.extend([Cell("")] * (index + 1 - len(cells)))
            cells[index] = _cell(c, shared, date_styles, date1904)
        rows.append(Row(last, cells))
    return rows


def _cell(c, shared, date_styles, date1904) -> Cell:
    kind = c.get("t", "n")
    value = c.find(MAIN + "v")
    raw = value.text if value is not None and value.text is not None else ""
    if kind == "s":
        if raw == "":
            return Cell("")
        try:
            return Cell(shared[int(raw)])
        except (ValueError, IndexError):
            raise XlsxError("ячейка %s: нет общей строки %r" % (c.get("r"), raw))
    if kind == "inlineStr":
        node = c.find(MAIN + "is")
        return Cell(_text(node) if node is not None else "")
    if kind in ("str", "e", "d"):
        return Cell(raw)
    if kind == "b":
        return Cell("TRUE" if raw == "1" else "FALSE")
    if raw == "":
        return Cell("")
    try:
        number = float(raw)
    except ValueError:
        raise XlsxError("ячейка %s: не число %r" % (c.get("r"), raw))
    style = int(c.get("s", "0"))
    if style < len(date_styles) and date_styles[style]:
        try:
            day = serial_date(number, date1904)
        except ValueError:
            pass  # «дата» вне календаря — показываем как число
        else:
            return Cell(day.strftime("%d.%m.%Y"), number, day)
    return Cell(_number_text(number), number)


def _number_text(number: float) -> str:
    """7.5 → «7.5», 46000.0 → «46000»: Excel хранит целые с точкой не всегда."""
    if number.is_integer():
        return str(int(number))
    return repr(number)
