"""xlsx для тестов и примера: ровно те части книги, что читает cvesummary.

Ячейка в строке: str — строка (общая или inline), int/float — число,
Num(value, style) — число со стилем (индекс в cellXfs), Rich — общая строка
из нескольких кусков, Formula — результат формулы (t="str"), Bool, Error,
None — ячейки нет, её адрес пропущен. Строка None — пропущенный номер
строки. Content_Types и _rels/.rels пишутся, чтобы книгу открывали Excel и
LibreOffice; читателю они не нужны.
"""
import io
import zipfile
from typing import NamedTuple, Sequence
from xml.sax.saxutils import escape, quoteattr

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"


class Num(NamedTuple):
    value: float
    style: int = 0


class Rich(NamedTuple):
    runs: Sequence[str]


class Formula(NamedTuple):
    text: str


class Bool(NamedTuple):
    value: bool


class Error(NamedTuple):
    text: str


def column(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    name = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


def _t(text):
    return '<t xml:space="preserve">%s</t>' % escape(text)


def _cell(ref, value, strings, shared):
    if isinstance(value, Rich):
        strings.append("".join("<r>%s</r>" % _t(run) for run in value.runs))
        return '<c r="%s" t="s"><v>%d</v></c>' % (ref, len(strings) - 1)
    if isinstance(value, str):
        if shared:
            strings.append(_t(value))
            return '<c r="%s" t="s"><v>%d</v></c>' % (ref, len(strings) - 1)
        return '<c r="%s" t="inlineStr"><is>%s</is></c>' % (ref, _t(value))
    if isinstance(value, Formula):
        return '<c r="%s" t="str"><f>X</f><v>%s</v></c>' % (ref, escape(value.text))
    if isinstance(value, Bool):
        return '<c r="%s" t="b"><v>%d</v></c>' % (ref, int(value.value))
    if isinstance(value, Error):
        return '<c r="%s" t="e"><v>%s</v></c>' % (ref, escape(value.text))
    if isinstance(value, Num):
        return '<c r="%s" s="%d"><v>%r</v></c>' % (ref, value.style, value.value)
    return '<c r="%s"><v>%r</v></c>' % (ref, value)


def _sheet(rows, strings, shared):
    out = ['<worksheet xmlns="%s"><sheetData>' % MAIN]
    for number, row in enumerate(rows, 1):
        if row is None:
            continue
        cells = [_cell("%s%d" % (column(i), number), value, strings, shared)
                 for i, value in enumerate(row) if value is not None]
        out.append('<row r="%d">%s</row>' % (number, "".join(cells)))
    out.append("</sheetData></worksheet>")
    return "".join(out)


def make(rows, *, sheet="Лист1", shared=True, xfs=(0,), numfmts=None, date1904=False,
         second=None, absolute=False, swap=False) -> bytes:
    """Книга одним буфером.

    xfs — numFmtId для каждого стиля cellXfs; numfmts — {id: formatCode};
    second — строки второго листа «Второй»; absolute — Target в rels от
    корня пакета (/xl/…); swap — первый лист лежит в sheet2.xml, второй — в
    sheet1.xml: порядок листов задаёт <sheets>, а не имена файлов.
    """
    strings = []
    first_xml = _sheet(rows, strings, shared)
    second_xml = _sheet(second, strings, shared) if second is not None else None
    names = ("sheet2.xml", "sheet1.xml") if swap else ("sheet1.xml", "sheet2.xml")
    prefix = "/xl/worksheets/" if absolute else "worksheets/"
    sheets = ['<sheet name=%s sheetId="1" r:id="rId1"/>' % quoteattr(sheet)]
    rels = ['<Relationship Id="rId1" Type="%s/worksheet" Target="%s%s"/>'
            % (REL, prefix, names[0])]
    parts = [names[0]]
    if second_xml is not None:
        sheets.append('<sheet name="Второй" sheetId="2" r:id="rId2"/>')
        rels.append('<Relationship Id="rId2" Type="%s/worksheet" Target="%s%s"/>'
                    % (REL, prefix, names[1]))
        parts.append(names[1])
    pr = '<workbookPr date1904="1"/>' if date1904 else ""
    fmts = ""
    if numfmts:
        fmts = '<numFmts count="%d">%s</numFmts>' % (len(numfmts), "".join(
            '<numFmt numFmtId="%d" formatCode=%s/>' % (k, quoteattr(v))
            for k, v in numfmts.items()))
    styles = '<styleSheet xmlns="%s">%s<cellXfs count="%d">%s</cellXfs></styleSheet>' % (
        MAIN, fmts, len(xfs), "".join('<xf numFmtId="%d"/>' % x for x in xfs))
    types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
             + ('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                if strings else "")
             + "".join('<Override PartName="/xl/worksheets/%s" ContentType="%s"/>' % (p, _SHEET_TYPE)
                       for p in parts)
             + "</Types>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", '<Relationships xmlns="%s"><Relationship Id="rId1" '
                   'Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>'
                   % (PKG, REL))
        z.writestr("xl/workbook.xml", '<workbook xmlns="%s" xmlns:r="%s">%s<sheets>%s</sheets>'
                   '</workbook>' % (MAIN, REL, pr, "".join(sheets)))
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="%s">%s'
                   '<Relationship Id="rIdS" Type="%s/styles" Target="styles.xml"/>'
                   '</Relationships>' % (PKG, "".join(rels), REL))
        z.writestr("xl/styles.xml", styles)
        if strings:
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="%s">%s</sst>'
                       % (MAIN, "".join("<si>%s</si>" % s for s in strings)))
        z.writestr("xl/worksheets/" + names[0], first_xml)
        if second_xml is not None:
            z.writestr("xl/worksheets/" + names[1], second_xml)
    return buffer.getvalue()


def write(path, rows, **options):
    with open(path, "wb") as handle:
        handle.write(make(rows, **options))


def replace(path, name, text):
    """Подменить (или убрать при text=None) часть уже записанной книги."""
    with zipfile.ZipFile(path) as z:
        members = {info.filename: z.read(info) for info in z.infolist()}
    if text is None:
        members.pop(name, None)
    else:
        members[name] = text.encode("utf-8")
    with zipfile.ZipFile(path, "w") as z:
        for member, data in members.items():
            z.writestr(member, data)
