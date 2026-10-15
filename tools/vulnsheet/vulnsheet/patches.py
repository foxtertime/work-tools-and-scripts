"""Патчи под CVE в каталоге патчей GitLab: в билде и в его ветке сейчас.

По ответу koji getBuild находится коммит сборки, по нему читается каталог
PATCH, затем — тот же каталог на вершине ветки, с которой билд собран, и из
имён файлов берутся CVE-идентификаторы. Сравнение двух деревьев говорит,
остался ли патч билда в ветке и нет ли в ветке патча, ещё не попавшего в
билд. Выбор коммита перенесён из тулзы dashboard (collect.py): хеш — из
extra.source.original_url, иначе из верхнего поля source того же проекта;
если коммита в репозитории уже нет — с ветки, с предупреждением.
"""
import logging
import re
import types
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Mapping, NamedTuple, Optional, Tuple

from .sourceurl import SourceUrlError, parse_source_url

logger = logging.getLogger(__name__)

# CVE-год-номер и, через дефис, другие номера того же года:
# cve-2026-12345-67890 — это CVE-2026-12345 и CVE-2026-67890. Номер — от 4
# до 7 цифр: восемь цифр подряд вернее дата, чем CVE. Граница у первого
# номера не нужна: \d{4,} жадный, и в CVE-2024-12345 найдётся CVE-2024-12345,
# которое с CVE-2024-1234 не совпадёт. CVE другого года пишется со своим
# префиксом: в cve-2025-1111-2026-2222 «2026» — номер, а не год.
_CVE_RE = re.compile(r"CVE-(\d{4})-(\d{4,})((?:-\d{4,7}(?!\d))*)", re.I)

# Ответ дерева, по которому видно, что ref в репозитории нет (см.
# gitlabclient._resolve_missing_tree). Суффиксом — при подмене хоста впереди
# стоит заметка о ней.
_REF_GONE = "gitlab: ref not found"

# исходы проверки одного компонента, по дереву билда
READ = "прочитано"
NO_DIR = "без каталога патчей"
NO_SOURCE = "без источника"
SRPM = "из SRPM"
FAILED = "ошибок"
# порядок, в каком исходы перечисляет итог прогона
KINDS = (READ, NO_DIR, NO_SOURCE, SRPM, FAILED)

# что известно о патче под одну CVE
FOUND = "found"              # в билде и в ветке; или ветки нет / не прочитана
REMOVED = "removed"          # был в билде, из ветки убран
BRANCH_ONLY = "branch_only"  # в ветке есть, в билд ещё не попал


class PatchNote(NamedTuple):
    kind: str
    branch: Optional[str]    # ветка, с которой сравнивали; None — не сравнивали
    urls: Tuple[str, ...]    # ссылки на файлы: на ветку, у REMOVED — на коммит билда


class Result(NamedTuple):
    notes: Dict[str, Dict[str, PatchNote]]  # компонент → CVE → что известно о патче
    failed: Tuple[str, ...]                 # компоненты с ошибкой GitLab или koji
    kinds: Mapping[str, int] = types.MappingProxyType({})  # исход → компонентов


def cves_of(path: str) -> List[str]:
    """CVE-идентификаторы из пути файла, в верхнем регистре, без повторов."""
    found = []
    for match in _CVE_RE.finditer(path):
        year = match.group(1)
        numbers = [match.group(2)] + [n for n in match.group(3).split("-") if n]
        for number in numbers:
            cve = "CVE-%s-%s" % (year, number)
            if cve not in found:
                found.append(cve)
    return found


def find(builds: Mapping[str, Optional[dict]], client, jobs: int = 8) -> Result:
    """Патчи по компонентам: компонент → ответ getBuild (None — нет деталей)."""
    items = list(builds.items())
    if len(items) <= 1 or jobs <= 1:
        outcomes = [_check(name, info, client) for name, info in items]
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="gl") as pool:
            outcomes = list(pool.map(lambda item: _check(*item, client), items))

    notes, failed, kinds = {}, [], Counter()
    for (name, _), (kind, found) in zip(items, outcomes):
        kinds[kind] += 1
        if kind == FAILED:
            failed.append(name)
        if found:
            notes[name] = found
    return Result(notes, tuple(failed), kinds)


def _check(name: str, info: Optional[dict], client):
    """(исход, CVE → PatchNote или None)."""
    if info is None:
        logger.warning("%s: патчи не проверены — koji не дал деталей билда", name)
        return FAILED, None
    raw_url = ((info.get("extra") or {}).get("source") or {}).get("original_url")
    if not raw_url:
        logger.debug("%s: у билда нет source url — патчи не проверяются", name)
        return NO_SOURCE, None
    try:
        parsed = parse_source_url(raw_url)
    except SourceUrlError as exc:
        logger.warning("%s: патчи не проверены — source url не разобран: %s", name, exc)
        return FAILED, None
    if parsed.ref_kind == "srpm":
        logger.debug("%s: билд собран из SRPM — патчи не проверяются", name)
        return SRPM, None

    def read(ref):
        result = client.patch_files(parsed.host, parsed.project, ref)
        if result.problem and result.present is not None:
            logger.warning("%s: %s", name, result.problem)  # оговорка: подменён хост
        return result

    def links(ref, paths):
        urls = (client.blob_url(parsed.host, parsed.project, ref, path) for path in paths)
        return tuple(url for url in urls if url)

    branch = parsed.ref if parsed.ref_kind == "branch" else None
    commit = _commit_of(info, parsed)
    built = None
    if commit:
        built = read(commit)
        if built.problem and built.problem.endswith(_REF_GONE):
            if branch is None:
                # собран прямо с коммита: ветки нет, откатываться некуда
                logger.warning("%s: патчи не проверены — коммит %s недоступен",
                               name, commit[:12])
                return FAILED, None
            logger.warning("%s: коммит %s недоступен, патчи сняты с ветки %s",
                           name, commit[:12], branch)
            built = None
        elif built.present is None:
            logger.warning("%s: патчи не проверены — %s", name, built.problem)
            return FAILED, None

    if built is None:
        # хеша нет или коммит пропал: что в билде, знает только ветка
        tip = read(parsed.ref)
        if tip.present is None:
            logger.warning("%s: патчи не проверены — %s", name, tip.problem)
            return FAILED, None
        return (READ if tip.present else NO_DIR), {
            cve: PatchNote(FOUND, branch, links(parsed.ref, paths))
            for cve, paths in _files(tip.paths).items()}

    in_build = _files(built.paths)
    kind = READ if built.present else NO_DIR
    if branch is None:
        return kind, {cve: PatchNote(FOUND, None, links(commit, paths))
                      for cve, paths in in_build.items()}
    tip = read(branch)
    if tip.present is None:
        # что лежит в билде, известно и так; неизвестно, осталось ли в ветке
        logger.warning("%s: ветка %s не прочитана, патчи — только по коммиту сборки: %s",
                       name, branch, tip.problem)
        return FAILED, {cve: PatchNote(FOUND, None, links(commit, paths))
                        for cve, paths in in_build.items()}
    in_branch = _files(tip.paths)
    notes = {}
    for cve in list(in_build) + [cve for cve in in_branch if cve not in in_build]:
        if cve not in in_branch:
            notes[cve] = PatchNote(REMOVED, branch, links(commit, in_build[cve]))
        elif cve in in_build:
            notes[cve] = PatchNote(FOUND, branch, links(branch, in_branch[cve]))
        else:
            notes[cve] = PatchNote(BRANCH_ONLY, branch, links(branch, in_branch[cve]))
    return kind, notes


def _files(paths) -> Dict[str, List[str]]:
    """CVE → пути файлов с ней в имени, в порядке дерева."""
    files = {}
    for path in paths:
        for cve in cves_of(path):
            files.setdefault(cve, []).append(path)
    return files


def _commit_of(info: dict, parsed) -> Optional[str]:
    """Хеш коммита сборки.

    Из верхнего source берётся только хеш, и только если проект тот же:
    другой репозиторий — не уточнение, и чужой коммит хуже, чем никакого.
    Хост в сверке не участвует: ssh-хост может не совпасть с https-хостом.
    """
    if parsed.ref_kind == "commit":
        return parsed.ref
    raw = info.get("source")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        other = parse_source_url(raw)
    except SourceUrlError:
        return None
    if other.ref_kind != "commit" or not other.project or not parsed.project:
        return None
    if other.project.strip("/").lower() != parsed.project.strip("/").lower():
        return None
    return other.ref
