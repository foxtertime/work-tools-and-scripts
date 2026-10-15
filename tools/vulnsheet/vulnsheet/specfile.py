"""Упоминания CVE в spec-файле: строки PatchN и секция %changelog. Без сети."""
import re
from typing import Dict, List, NamedTuple, Optional

from .cveid import cves_of

# «Patch12: файл», «Patch: файл», регистр тега не важен; строки-комментарии
# (#) сюда не попадают — тег должен стоять первым в строке
_PATCH_RE = re.compile(r"^\s*(Patch\d*)\s*:\s*(.*?)\s*$", re.I)
# версия в заголовке записи: «* Mon Jan 05 2026 Имя <почта> - 1.26.3-2»
_VERSION_RE = re.compile(r"\s-\s*(\S*\d\S*)\s*$")


class Mention(NamedTuple):
    line: int             # номер строки в файле, с единицы — для ссылки #L
    label: Optional[str]  # «Patch12: файл» или версия записи %changelog


def patch_mentions(text: str) -> Dict[str, List[Mention]]:
    """CVE → строки PatchN, в значении которых она есть, по порядку."""
    found = {}
    for number, line in enumerate(text.splitlines(), 1):
        match = _PATCH_RE.match(line)
        if not match:
            continue
        # «; » в ячейке комментария разделяет фрагменты — в подпись его не пускаем
        label = ("%s: %s" % match.groups()).replace("; ", ", ")
        for cve in cves_of(match.group(2)):
            found.setdefault(cve, []).append(Mention(number, label))
    return found


def changelog_mentions(text: str) -> Dict[str, Mention]:
    """CVE → самое свежее упоминание в %changelog и версия его записи.

    Записи в %changelog идут от новых к старым, поэтому первое упоминание —
    самое свежее."""
    found, version, inside = {}, None, False
    for number, line in enumerate(text.splitlines(), 1):
        if not inside:
            inside = line.strip().lower().startswith("%changelog")
            continue
        if line.startswith("*"):
            match = _VERSION_RE.search(line)
            version = match.group(1) if match else None
        for cve in cves_of(line):
            found.setdefault(cve, Mention(number, version))
    return found
