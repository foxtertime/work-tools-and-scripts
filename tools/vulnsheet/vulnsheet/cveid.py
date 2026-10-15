"""CVE-идентификаторы в именах файлов и в тексте."""
import re
from typing import List

# CVE-год-номер и, через дефис, другие номера того же года:
# cve-2026-12345-67890 — это CVE-2026-12345 и CVE-2026-67890. Номер — от 4
# до 7 цифр: восемь цифр подряд вернее дата, чем CVE. Граница у первого
# номера не нужна: \d{4,} жадный, и в CVE-2024-12345 найдётся CVE-2024-12345,
# которое с CVE-2024-1234 не совпадёт. CVE другого года пишется со своим
# префиксом: в cve-2025-1111-2026-2222 «2026» — номер, а не год.
_CVE_RE = re.compile(r"CVE-(\d{4})-(\d{4,})((?:-\d{4,7}(?!\d))*)", re.I)


def cves_of(text: str) -> List[str]:
    """CVE-идентификаторы из пути файла или строки текста, в верхнем
    регистре, без повторов, в порядке появления."""
    found = []
    for match in _CVE_RE.finditer(text):
        year = match.group(1)
        numbers = [match.group(2)] + [n for n in match.group(3).split("-") if n]
        for number in numbers:
            cve = "CVE-%s-%s" % (year, number)
            if cve not in found:
                found.append(cve)
    return found
