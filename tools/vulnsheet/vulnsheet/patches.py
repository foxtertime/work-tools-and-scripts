"""Патчи под CVE в каталоге патчей GitLab, из которого собран билд.

По ответу koji getBuild находится коммит сборки, по нему читается каталог
PATCH, и из имён файлов берутся CVE-идентификаторы. Выбор коммита перенесён
из тулзы dashboard (collect.py): хеш — из extra.source.original_url, иначе
из верхнего поля source того же проекта; если коммита в репозитории уже
нет — с ветки, с предупреждением.
"""
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, FrozenSet, Iterable, Mapping, NamedTuple, Optional, Tuple

from .sourceurl import SourceUrlError, parse_source_url

logger = logging.getLogger(__name__)

# Граница справа не нужна: \d{4,} жадный, и в CVE-2024-12345 найдётся именно
# CVE-2024-12345, которое с CVE-2024-1234 не совпадёт.
_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.I)

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


class Result(NamedTuple):
    cves: Dict[str, FrozenSet[str]]   # компонент → CVE из имён файлов; только прочитанные
    failed: Tuple[str, ...]           # компоненты, которые проверить не удалось


def cves_in(paths: Iterable[str]) -> FrozenSet[str]:
    """CVE-идентификаторы из путей файлов, в верхнем регистре."""
    return frozenset(match.group(0).upper()
                     for path in paths for match in _CVE_RE.finditer(path))


def find(builds: Mapping[str, Optional[dict]], client, jobs: int = 8) -> Result:
    """Патчи по компонентам: компонент → ответ getBuild (None — нет деталей)."""
    items = list(builds.items())
    if len(items) <= 1 or jobs <= 1:
        outcomes = [_check(name, info, client) for name, info in items]
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="gl") as pool:
            outcomes = list(pool.map(lambda item: _check(*item, client), items))

    cves, failed, kinds = {}, [], Counter()
    for (name, _), (kind, found) in zip(items, outcomes):
        kinds[kind] += 1
        if kind == FAILED:
            failed.append(name)
        elif found is not None:
            cves[name] = found
    if items:
        logger.info("патчи GitLab: %s", ", ".join(
            "%s %d" % (kind, kinds[kind]) for kind in (READ, NO_DIR, NO_SOURCE, SRPM, FAILED)))
    return Result(cves, tuple(failed))


def _check(name: str, info: Optional[dict], client):
    """(исход, CVE из каталога патчей или None)."""
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

    commit = _commit_of(info, parsed)
    result = _read(name, client, parsed, commit)
    if result.problem:
        if result.present is None:
            logger.warning("%s: патчи не проверены — %s", name, result.problem)
            return FAILED, None
        logger.warning("%s: %s", name, result.problem)
    if not result.present:
        return NO_DIR, frozenset()
    return READ, cves_in(result.paths)


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


def _read(name, client, parsed, commit):
    """Каталог патчей на коммите сборки; на ветке — если хеша нет или коммита
    в репозитории уже не осталось (ветку форс-пушнули)."""
    if not commit:
        return client.patch_files(parsed.host, parsed.project, parsed.ref)
    result = client.patch_files(parsed.host, parsed.project, commit)
    if not result.problem or not result.problem.endswith(_REF_GONE):
        return result
    if parsed.ref_kind == "commit":
        # собран прямо с коммита: ветки нет, откатываться некуда
        return result._replace(problem="коммит %s недоступен" % commit[:12])
    logger.warning("%s: коммит %s недоступен, патчи сняты с ветки %s",
                   name, commit[:12], parsed.ref)
    return client.patch_files(parsed.host, parsed.project, parsed.ref)
