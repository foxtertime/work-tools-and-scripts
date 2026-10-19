"""Патчи под CVE в GitLab: каталог PATCH коммита, из которого собран билд.

По ответу koji getBuild находится коммит сборки, и в его каталоге PATCH
CVE ищутся в именах файлов. Выбор коммита перенесён из тулзы dashboard
(collect.py): хеш — из extra.source.original_url, иначе из верхнего поля
source того же проекта; если хеша нет или коммита в репозитории уже нет —
читается ветка, во втором случае с предупреждением.
"""
import logging
import types
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, FrozenSet, Mapping, NamedTuple, Optional, Tuple

from .cveid import cves_of
from .sourceurl import SourceUrlError, parse_source_url

logger = logging.getLogger(__name__)

# Ответ дерева, по которому видно, что ref в репозитории нет (см.
# gitlabclient._resolve_missing_tree). Суффиксом — при подмене хоста впереди
# стоит заметка о ней.
_REF_GONE = "gitlab: ref not found"

# исходы проверки одного компонента
READ = "прочитано"
NO_DIR = "без каталога патчей"
NO_SOURCE = "без источника"
SRPM = "из SRPM"
FAILED = "ошибок"
# порядок, в каком исходы перечисляет итог прогона
KINDS = (READ, NO_DIR, NO_SOURCE, SRPM, FAILED)


class Result(NamedTuple):
    # компонент → CVE, чьи патчи лежат в каталоге PATCH билда; компонента с
    # ошибкой здесь нет — про его патчи ничего не известно
    patched: Dict[str, FrozenSet[str]]
    failed: Tuple[str, ...]                                # компоненты с ошибкой
    kinds: Mapping[str, int] = types.MappingProxyType({})  # исход → компонентов


def find(builds: Mapping[str, Optional[dict]], client, jobs: int = 8) -> Result:
    """CVE по компонентам: компонент → ответ getBuild (None — нет деталей)."""
    items = list(builds.items())
    if len(items) <= 1 or jobs <= 1:
        outcomes = [_check(name, info, client) for name, info in items]
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="gl") as pool:
            outcomes = list(pool.map(lambda item: _check(*item, client), items))

    patched, failed, kinds = {}, [], Counter()
    for (name, _), (kind, cves) in zip(items, outcomes):
        kinds[kind] += 1
        if kind == FAILED:
            failed.append(name)
        else:
            patched[name] = cves
    return Result(patched, tuple(failed), kinds)


def _check(name: str, info: Optional[dict], client) -> Tuple[str, FrozenSet[str]]:
    """(исход, CVE из каталога PATCH билда)."""
    none = frozenset()
    if info is None:
        logger.warning("%s: патчи не проверены — koji не дал деталей билда", name)
        return FAILED, none
    raw_url = ((info.get("extra") or {}).get("source") or {}).get("original_url")
    if not raw_url:
        logger.debug("%s: у билда нет source url — патчи не проверяются", name)
        return NO_SOURCE, none
    try:
        parsed = parse_source_url(raw_url)
    except SourceUrlError as exc:
        logger.warning("%s: патчи не проверены — source url не разобран: %s", name, exc)
        return FAILED, none
    if parsed.ref_kind == "srpm":
        logger.debug("%s: билд собран из SRPM — патчи не проверяются", name)
        return SRPM, none

    branch = parsed.ref if parsed.ref_kind == "branch" else None
    commit = _commit_of(info, parsed)
    found = None
    if commit:
        found = _tree(name, parsed, commit, client)
        if found.problem and found.problem.endswith(_REF_GONE):
            if branch is None:
                # собран прямо с коммита: ветки нет, откатываться некуда
                logger.warning("%s: патчи не проверены — коммит %s недоступен",
                               name, commit[:12])
                return FAILED, none
            logger.warning("%s: коммит %s недоступен, патчи сняты с ветки %s",
                           name, commit[:12], branch)
            found = None
    if found is None:
        # хеша нет или коммит пропал: что в билде, знает только ветка
        found = _tree(name, parsed, parsed.ref, client)
    if found.present is None:
        logger.warning("%s: патчи не проверены — %s", name, found.problem)
        return FAILED, none
    if not found.present:
        return NO_DIR, none
    return READ, frozenset(cve for path in found.paths for cve in cves_of(path))


def _tree(name, parsed, ref, client):
    result = client.patch_files(parsed.host, parsed.project, ref)
    if result.problem and result.present is not None:
        logger.warning("%s: %s", name, result.problem)  # оговорка: подменён хост
    return result


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
