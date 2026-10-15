"""Патчи под CVE в GitLab: в билде и в его ветке сейчас.

По ответу koji getBuild находится коммит сборки. В нём и на вершине ветки,
с которой билд собран, читаются три источника: каталог PATCH (CVE в именах
файлов), строки PatchN спека и его %changelog. Спек — единственный .spec в
каталоге SPECS. Сравнение коммита с веткой говорит, осталась ли CVE в ветке
и нет ли в ветке того, что ещё не попало в билд. Выбор коммита перенесён из
тулзы dashboard (collect.py): хеш — из extra.source.original_url, иначе из
верхнего поля source того же проекта; если коммита в репозитории уже нет —
с ветки, с предупреждением.
"""
import logging
import types
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Mapping, NamedTuple, Optional, Tuple

from . import specfile
from .cveid import cves_of
from .sourceurl import SourceUrlError, parse_source_url

logger = logging.getLogger(__name__)

# Ответ дерева, по которому видно, что ref в репозитории нет (см.
# gitlabclient._resolve_missing_tree). Суффиксом — при подмене хоста впереди
# стоит заметка о ней.
_REF_GONE = "gitlab: ref not found"
SPEC_DIR = "SPECS"

# исходы проверки одного компонента, по каталогу PATCH билда; ошибок —
# любая ошибка GitLab или koji по компоненту, в том числе со спеком
READ = "прочитано"
NO_DIR = "без каталога патчей"
NO_SOURCE = "без источника"
SRPM = "из SRPM"
FAILED = "ошибок"
# порядок, в каком исходы перечисляет итог прогона
KINDS = (READ, NO_DIR, NO_SOURCE, SRPM, FAILED)

# что со спеком билда
SPEC_READ = "спек прочитан"
SPEC_NONE = "спека нет"
SPEC_MANY = "спеков несколько, не выбран"
SPEC_KINDS = (SPEC_READ, SPEC_NONE, SPEC_MANY)

# где упомянута CVE, в порядке фрагментов комментария
SRC_PATCH = "каталог PATCH"
SRC_SPEC = "PatchN в спеке"
SRC_CHANGELOG = "%changelog"
SOURCES = (SRC_PATCH, SRC_SPEC, SRC_CHANGELOG)

# что известно о CVE в одном источнике
FOUND = "found"              # в билде и в ветке; или ветки нет / не прочитана
REMOVED = "removed"          # было в билде, из ветки убрано
BRANCH_ONLY = "branch_only"  # в ветке есть, в билд ещё не попало


class Item(NamedTuple):
    label: Optional[str]  # «Patch12: файл», версия записи %changelog; у PATCH — None
    url: str              # ссылка на файл, у спека — со строкой (#L40)


class PatchNote(NamedTuple):
    kind: str
    branch: Optional[str]     # ветка, с которой сравнивали; None — не сравнивали
    items: Tuple[Item, ...]   # из ветки, у REMOVED — из коммита билда


class Result(NamedTuple):
    # компонент → CVE → источник → что известно
    notes: Dict[str, Dict[str, Dict[str, PatchNote]]]
    failed: Tuple[str, ...]                                     # компоненты с ошибкой
    kinds: Mapping[str, int] = types.MappingProxyType({})       # исход → компонентов
    spec_kinds: Mapping[str, int] = types.MappingProxyType({})  # спек → компонентов


class _Side(NamedTuple):
    """Что известно на одном ref. Источник → CVE → упоминания; None — источник
    неизвестен (спек не прочитан или не выбран)."""
    sources: Dict[str, Optional[Dict[str, List[Item]]]]
    spec: Optional[str]   # SPEC_*; None — ошибка чтения
    failed: bool


def find(builds: Mapping[str, Optional[dict]], client, jobs: int = 8) -> Result:
    """CVE по компонентам: компонент → ответ getBuild (None — нет деталей)."""
    items = list(builds.items())
    if len(items) <= 1 or jobs <= 1:
        outcomes = [_check(name, info, client) for name, info in items]
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="gl") as pool:
            outcomes = list(pool.map(lambda item: _check(*item, client), items))

    notes, failed, kinds, specs = {}, [], Counter(), Counter()
    for (name, _), (kind, found, spec) in zip(items, outcomes):
        kinds[kind] += 1
        if spec:
            specs[spec] += 1
        if kind == FAILED:
            failed.append(name)
        if found:
            notes[name] = found
    return Result(notes, tuple(failed), kinds, specs)


def _check(name: str, info: Optional[dict], client):
    """(исход, CVE → источник → PatchNote или None, что со спеком)."""
    if info is None:
        logger.warning("%s: патчи не проверены — koji не дал деталей билда", name)
        return FAILED, None, None
    raw_url = ((info.get("extra") or {}).get("source") or {}).get("original_url")
    if not raw_url:
        logger.debug("%s: у билда нет source url — патчи не проверяются", name)
        return NO_SOURCE, None, None
    try:
        parsed = parse_source_url(raw_url)
    except SourceUrlError as exc:
        logger.warning("%s: патчи не проверены — source url не разобран: %s", name, exc)
        return FAILED, None, None
    if parsed.ref_kind == "srpm":
        logger.debug("%s: билд собран из SRPM — патчи не проверяются", name)
        return SRPM, None, None

    repo = _Repo(name, parsed, client)
    branch = parsed.ref if parsed.ref_kind == "branch" else None
    commit = _commit_of(info, parsed)
    built = None
    if commit:
        built = repo.tree(commit)
        if built.problem and built.problem.endswith(_REF_GONE):
            if branch is None:
                # собран прямо с коммита: ветки нет, откатываться некуда
                logger.warning("%s: патчи не проверены — коммит %s недоступен",
                               name, commit[:12])
                return FAILED, None, None
            logger.warning("%s: коммит %s недоступен, патчи сняты с ветки %s",
                           name, commit[:12], branch)
            built = None
        elif built.present is None:
            logger.warning("%s: патчи не проверены — %s", name, built.problem)
            return FAILED, None, None

    if built is None:
        # хеша нет или коммит пропал: что в билде, знает только ветка
        tip = repo.tree(parsed.ref)
        if tip.present is None:
            logger.warning("%s: патчи не проверены — %s", name, tip.problem)
            return FAILED, None, None
        side = repo.side(parsed.ref, tip)
        kind = FAILED if side.failed else READ if tip.present else NO_DIR
        return kind, _compare(side, None, branch), side.spec

    build = repo.side(commit, built)
    kind = FAILED if build.failed else READ if built.present else NO_DIR
    if branch is None:
        return kind, _compare(build, None, None), build.spec
    tip = repo.tree(branch)
    if tip.present is None:
        # что лежит в билде, известно и так; неизвестно, осталось ли в ветке
        logger.warning("%s: ветка %s не прочитана, CVE — только по коммиту сборки: %s",
                       name, branch, tip.problem)
        return FAILED, _compare(build, None, None), build.spec
    head = repo.side(branch, tip)
    if head.failed:
        kind = FAILED
    return kind, _compare(build, head, branch), build.spec


class _Repo:
    """Чтение одного репозитория компонента: деревья, спек, ссылки."""

    def __init__(self, name, parsed, client):
        self.name, self.parsed, self.client = name, parsed, client

    def tree(self, ref, path=None):
        host, project = self.parsed.host, self.parsed.project
        result = (self.client.patch_files(host, project, ref) if path is None
                  else self.client.tree(host, project, ref, path))
        if result.problem and result.present is not None:
            logger.warning("%s: %s", self.name, result.problem)  # оговорка: подменён хост
        return result

    def link(self, ref, path, line=None) -> Optional[str]:
        url = self.client.blob_url(self.parsed.host, self.parsed.project, ref, path)
        return url and (url + "#L%d" % line if line else url)

    def side(self, ref, patch_tree) -> _Side:
        patches = {}
        for path in patch_tree.paths:
            url = self.link(ref, path)
            for cve in cves_of(path):
                if url:
                    patches.setdefault(cve, []).append(Item(None, url))
        spec, path, text = self.spec(ref)
        sources = {SRC_PATCH: patches, SRC_SPEC: None, SRC_CHANGELOG: None}
        if spec == SPEC_NONE:
            sources[SRC_SPEC] = sources[SRC_CHANGELOG] = {}
        elif text is not None:
            sources[SRC_SPEC] = self.mentions(ref, path, {
                cve: mentions for cve, mentions in specfile.patch_mentions(text).items()})
            sources[SRC_CHANGELOG] = self.mentions(ref, path, {
                cve: [mention] for cve, mention in specfile.changelog_mentions(text).items()})
        return _Side(sources, spec, spec is None)

    def mentions(self, ref, path, found) -> Dict[str, List[Item]]:
        result = {}
        for cve, mentions in found.items():
            for mention in mentions:
                url = self.link(ref, path, mention.line)
                if url:
                    result.setdefault(cve, []).append(Item(mention.label, url))
        return result

    def spec(self, ref):
        """(что со спеком, путь, текст). Спек — единственный .spec в SPECS;
        если их несколько — <имя пакета>.spec, если он среди них."""
        listing = self.tree(ref, SPEC_DIR)
        if listing.present is None:
            logger.warning("%s: каталог %s на %s не прочитан: %s",
                           self.name, SPEC_DIR, ref, listing.problem)
            return None, None, None
        specs = [path for path in listing.paths
                 if path.count("/") == 1 and path.lower().endswith(".spec")]
        if not specs:
            logger.debug("%s: в %s на %s нет .spec", self.name, SPEC_DIR, ref)
            return SPEC_NONE, None, None
        path = specs[0]
        if len(specs) > 1:
            path = "%s/%s.spec" % (SPEC_DIR, self.name)
            if path not in specs:
                logger.warning("%s: в %s на %s несколько спеков (%s) — спек не выбран",
                               self.name, SPEC_DIR, ref, ", ".join(specs))
                return SPEC_MANY, None, None
        got = self.client.file_text(self.parsed.host, self.parsed.project, ref, path)
        if got.text is None:
            logger.warning("%s: спек %s на %s не прочитан: %s", self.name, path, ref, got.problem)
            return None, None, None
        return SPEC_READ, path, got.text


def _compare(build: _Side, head: Optional[_Side], branch: Optional[str]):
    """CVE → источник → PatchNote: билд против ветки, по каждому источнику.

    head=None — сравнивать не с чем (ветки нет, не прочитана или читали
    только её): всё найденное — FOUND, branch — подпись для пометки."""
    notes = {}
    for source in SOURCES:
        built = build.sources[source]
        if built is None:
            continue  # что в билде, неизвестно — и сравнивать нечего
        tip = head.sources[source] if head is not None else None
        if head is None or tip is None:
            label = branch if head is None else None
            for cve, items in built.items():
                notes.setdefault(cve, {})[source] = PatchNote(FOUND, label, tuple(items))
            continue
        for cve in list(built) + [cve for cve in tip if cve not in built]:
            if cve not in tip:
                note = PatchNote(REMOVED, branch, tuple(built[cve]))
            elif cve in built:
                note = PatchNote(FOUND, branch, tuple(tip[cve]))
            else:
                note = PatchNote(BRANCH_ONLY, branch, tuple(tip[cve]))
            notes.setdefault(cve, {})[source] = note
    return notes


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
