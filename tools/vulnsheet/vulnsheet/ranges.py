"""Апстрим-диапазоны уязвимых версий: NVD, иначе CVE.org.

NVD даёт CPE-конфигурации в едином формате и закрывает почти все CVE, но
свежие разбирает с опозданием или откладывает. CVE.org (CNA, затем ADP)
заполняет пробелы, но формат у каждого CNA свой: границы бывают текстом в
поле version, верхней границы может не быть («lessThan: *»), встречается
мусор. Продукт сопоставляется с пакетом по имени; вендор не учитывается.

NVD пускает 5 запросов в 30 секунд без ключа и 50 с ключом: запросы к нему
идут параллельно, но их старты разнесены под этот лимит. CVE.org —
параллельно без ограничений. Оба — с кэшем на диске.
"""
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

from . import __version__
from .rpmvercmp import rpmvercmp
from .vex import read_cache, write_cache

logger = logging.getLogger(__name__)

NVD = "NVD"
CVEORG = "CVE.org"
_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve}"
_CVEORG_URL = "https://cveawg.mitre.org/api/cve/{cve}"
USER_AGENT = "vulnsheet/%s (+upstream version ranges)" % __version__
# интервал между стартами запросов к NVD: без ключа — 5 запросов / 30 с, с ключом — 50
PAUSE = 6.0
PAUSE_WITH_KEY = 0.6

# версия без смысла: «любая», «неизвестна», «не указана»
_NO_VERSION = {"", "*", "-", "n/a", "unspecified", "unknown"}
_TEXT_BOUND = re.compile(r"^(>=|<=|>|<|=)\s*(\S+)$")


class Interval(NamedTuple):
    start: Optional[str]   # None — снизу не ограничен
    start_incl: bool
    end: Optional[str]     # None — сверху не ограничен
    end_incl: bool

    def contains(self, version: str) -> bool:
        if self.start is not None:
            order = rpmvercmp(version, self.start)
            if order < 0 or (order == 0 and not self.start_incl):
                return False
        if self.end is not None:
            order = rpmvercmp(version, self.end)
            if order > 0 or (order == 0 and not self.end_incl):
                return False
        return True

    def empty(self) -> bool:
        if self.start is None or self.end is None:
            return False
        order = rpmvercmp(self.start, self.end)
        return order > 0 or (order == 0 and not (self.start_incl and self.end_incl))

    def text(self) -> str:
        if self.start is not None and self.start == self.end:
            return "=" + self.start
        if self.start is None and self.end is None:
            return "любая версия"
        low = ("%s%s" % (">=" if self.start_incl else ">", self.start)
               if self.start is not None else "")
        if self.end is None:
            return "%s, верхняя граница не указана" % low
        high = "%s%s" % ("<=" if self.end_incl else "<", self.end)
        return "%s %s" % (low, high) if low else high


class Ranges(NamedTuple):
    source: str                      # NVD или CVEORG
    intervals: Tuple[Interval, ...]


class RangeNote(NamedTuple):
    version: str                     # апстрим-версия билда
    inside: Optional[bool]           # None — диапазон неизвестен
    source: Optional[str]
    intervals: Tuple[Interval, ...]  # внутри — те, что содержат версию; вне — все


def norm(name: str) -> str:
    """Имя продукта для сравнения: регистр и «пробел/_» не важны."""
    return re.sub(r"[\s_]+", "_", (name or "").strip().lower())


def nvd_intervals(doc: Optional[dict], names: Set[str]) -> List[Interval]:
    """Уязвимые диапазоны продукта из CPE-конфигураций документа NVD."""
    wanted = {norm(name) for name in names}
    found = []
    for vulnerability in (doc or {}).get("vulnerabilities") or []:
        for config in (vulnerability.get("cve") or {}).get("configurations") or []:
            for node in config.get("nodes") or []:
                for match in node.get("cpeMatch") or []:
                    # не уязвимые — это платформы («работает на …»), не продукт
                    if not match.get("vulnerable"):
                        continue
                    parts = (match.get("criteria") or "").split(":")
                    if len(parts) < 7 or norm(parts[4]) not in wanted:
                        continue
                    found.append(_nvd_interval(match, parts[5], parts[6]))
    return found


def _nvd_interval(match: dict, version: str, update: str) -> Interval:
    bounds = [match.get(key) for key in ("versionStartIncluding", "versionStartExcluding",
                                          "versionEndIncluding", "versionEndExcluding")]
    if any(bounds):
        start_in, start_ex, end_in, end_ex = bounds
        return Interval(start_in or start_ex, bool(start_in), end_in or end_ex, bool(end_in))
    if version in _NO_VERSION:
        return Interval(None, False, None, False)
    # openbsd:openssh:8.5:p1 — версия и «обновление» вместе дают 8.5p1
    if update not in _NO_VERSION:
        version += update
    return Interval(version, True, version, True)


def cveorg_intervals(doc: Optional[dict], names: Set[str]) -> List[Interval]:
    """Уязвимые диапазоны продукта из записи CVE.org: CNA, а если у него
    для продукта ничего нет — ADP."""
    containers = (doc or {}).get("containers") or {}
    for container in [containers.get("cna") or {}] + list(containers.get("adp") or []):
        found = _affected_intervals(container.get("affected") or [], names)
        if found:
            return found
    return []


def _affected_intervals(affected: Iterable[dict], names: Set[str]) -> List[Interval]:
    wanted = {norm(name) for name in names}
    found = []
    for entry in affected:
        if norm(entry.get("product")) not in wanted and norm(entry.get("packageName")) not in wanted:
            continue
        for version in entry.get("versions") or []:
            # статус unaffected описывает исправленные версии, rpm — сборки
            # дистрибутивов (их даёт VEX): ни то ни другое не апстрим-диапазон
            if version.get("status", "affected") != "affected" or version.get("versionType") == "rpm":
                continue
            interval = _cveorg_interval(version)
            if interval is not None and not interval.empty():
                found.append(interval)
    return found


def _cveorg_interval(entry: dict) -> Optional[Interval]:
    version = str(entry.get("version") or "").strip()
    less, less_eq = entry.get("lessThan"), entry.get("lessThanOrEqual")
    if less or less_eq:
        high = str(less or less_eq).strip()
        start = None if version in _NO_VERSION or version == "0" else version
        end = None if high in _NO_VERSION else high
        return Interval(start, start is not None, end, end is not None and bool(less_eq))
    if version.lower() in _NO_VERSION:
        return None
    if version[0] in "<>=":
        return _text_interval(version)
    return Interval(version, True, version, True)


def _text_interval(text: str) -> Optional[Interval]:
    """«>= 2.43.0, < 2.43.4», «< 9.0.2106», «= 2.45.0» — так пишут git и vim."""
    start = end = None
    start_incl = end_incl = False
    for part in text.split(","):
        match = _TEXT_BOUND.match(part.strip())
        if not match:
            return None
        op, value = match.groups()
        if op in ("=", ">=", ">"):
            start, start_incl = value, op != ">"
        if op in ("=", "<=", "<"):
            end, end_incl = value, op != "<"
    return Interval(start, start_incl, end, end_incl)


def pick(nvd_doc: Optional[dict], cveorg_doc: Optional[dict], names: Set[str]) -> Optional[Ranges]:
    """Диапазоны продукта: из NVD, если он их знает, иначе из CVE.org."""
    found = nvd_intervals(nvd_doc, names)
    if found:
        return Ranges(NVD, tuple(found))
    found = cveorg_intervals(cveorg_doc, names)
    if found:
        return Ranges(CVEORG, tuple(found))
    return None


def upstream_version(nvr: str) -> Optional[str]:
    """Апстрим-версия из NVR: nginx-1.26.3-2.sl9 → 1.26.3; эпоха срезается."""
    parts = (nvr or "").rsplit("-", 2)
    if len(parts) != 3 or not all(parts):
        return None
    return parts[1].split(":", 1)[-1] or None


def judge(version: str, ranges: Optional[Ranges]) -> RangeNote:
    """Где версия относительно диапазонов."""
    if ranges is None:
        return RangeNote(version, None, None, ())
    inside = tuple(interval for interval in ranges.intervals if interval.contains(version))
    if inside:
        return RangeNote(version, True, ranges.source, inside)
    return RangeNote(version, False, ranges.source, ranges.intervals)


class RangeSettings(NamedTuple):
    """Настройки загрузки; значения по умолчанию — встроенные."""
    cache_dir: Optional[str] = None  # None — без кэша
    cache_ttl: int = 86400           # секунд; 0 — кэш не читать
    jobs: int = 8                    # параллельных запросов к каждому источнику
    retries: int = 3
    timeout: float = 30
    nvd_key: Optional[str] = None


class Docs(NamedTuple):
    """Документы по CVE; None — записи нет или источник не ответил."""
    nvd: Optional[dict]
    cveorg: Optional[dict]
    failed: Tuple[str, ...]          # источники, которые не ответили


def nvd_url(cve: str) -> str:
    return _NVD_URL.format(cve=cve)


def cveorg_url(cve: str) -> str:
    return _CVEORG_URL.format(cve=cve)


def download(url: str, timeout: float, headers: Optional[dict] = None) -> Optional[bytes]:
    """Тело ответа; None при 404 (записи нет). Остальное — исключение."""
    started = time.monotonic()
    request = urllib.request.Request(url, headers=dict(headers or {}, **{"User-Agent": USER_AGENT}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        logger.debug("GET %s → %d за %.2f с", url, exc.code, time.monotonic() - started)
        if exc.code == 404:
            return None
        raise
    # ключ NVD едет заголовком и в журнал не попадает
    logger.debug("GET %s → %d за %.2f с", url, code, time.monotonic() - started)
    return body


def fetch_all(cves: Iterable[str], settings: RangeSettings = RangeSettings()
              ) -> Tuple[Dict[str, Docs], Dict[str, str]]:
    """Документы NVD и CVE.org по уникальным CVE и CVE, по которым не ответил
    ни один источник."""
    cves = list(dict.fromkeys(cves))
    started = time.monotonic()
    cveorg, cveorg_errors = _fetch_many(CVEORG, cves, settings, None, None)
    nvd, nvd_errors = _fetch_nvd(cves, settings, time.monotonic() - started)

    docs, failures = {}, {}
    for cve in cves:
        failed = tuple(source for source, errors in ((NVD, nvd_errors), (CVEORG, cveorg_errors))
                       if cve in errors)
        if len(failed) == 2:
            failures[cve] = cveorg_errors[cve]
        docs[cve] = Docs(nvd.get(cve), cveorg.get(cve), failed)
    return docs, failures


def _fetch_nvd(cves, settings, cveorg_seconds):
    """NVD: запросы параллельно, но их старты разнесены под лимит NVD; с
    ключом — 50 запросов в 30 с, без ключа — 5. 404 с ключом значит, что
    ключ отклонён, — тогда NVD до конца прогона не спрашивается."""
    interval = PAUSE_WITH_KEY if settings.nvd_key else PAUSE
    cached = sum(1 for cve in cves if _fresh(_cache_path(settings, NVD, cve), settings.cache_ttl))
    logger.info("диапазоны: CVE.org — CVE %d за %s; NVD — CVE %d, из кэша %d, в сеть %d, ~%s %s",
                len(cves), _duration(cveorg_seconds), len(cves), cached, len(cves) - cached,
                _duration((len(cves) - cached) * interval),
                "с ключом" if settings.nvd_key else "без ключа")
    headers = {"apiKey": settings.nvd_key} if settings.nvd_key else None
    progress = _Progress(len(cves))
    return _fetch_many(NVD, cves, settings, headers, _Limiter(interval), progress)


def _fetch_many(source, cves, settings, headers, limiter, progress=None):
    """Документы одного источника параллельно: (CVE → документ, CVE → ошибка)."""
    docs, errors = {}, {}
    lock = threading.Lock()
    rejected = threading.Event()
    url = nvd_url if source == NVD else cveorg_url

    def load(cve):
        try:
            if rejected.is_set():
                raise _Rejected("ключ отклонён")
            doc = _fetch(source, url(cve), cve, settings, headers, limiter)
        except _Rejected as exc:
            if headers and not rejected.is_set():
                rejected.set()
                logger.warning("диапазоны: NVD ответил 404 на запрос с ключом — ключ "
                               "отклонён, проверьте его; NVD до конца прогона не спрашивается")
            elif not headers:
                logger.warning("диапазоны: NVD по %s ответил 404", cve)
            with lock:
                errors[cve] = str(exc)
        except Exception as exc:
            logger.warning("диапазоны: %s по %s не ответил: %s", source, cve, exc)
            with lock:
                errors[cve] = str(exc)
        else:
            with lock:
                docs[cve] = doc
        if progress is not None:
            progress.step()

    with ThreadPoolExecutor(max_workers=max(1, settings.jobs), thread_name_prefix="r") as pool:
        list(pool.map(load, cves))
    return docs, errors


class _Rejected(Exception):
    """NVD ответил 404: для существующих и несуществующих CVE он отвечает 200,
    404 бывает только на отклонённый ключ."""


class _Limiter:
    """Старты запросов не чаще раза в interval секунд, из любых потоков.
    Ожидание ответа идёт в счёт паузы; простой впрок не копится."""

    def __init__(self, interval: float, clock=time.monotonic, sleep=None):
        self.interval, self.clock = interval, clock
        self.sleep = sleep or (lambda seconds: time.sleep(seconds))
        self.lock = threading.Lock()
        self.next = None

    def wait(self) -> None:
        with self.lock:
            now = self.clock()
            slot = now if self.next is None else max(now, self.next)
            self.next = slot + self.interval
        if slot > now:
            self.sleep(slot - now)


class _Progress:
    """Прогресс NVD: не реже раза в 30 с, с оценкой оставшегося, и в конце."""
    EVERY = 30.0

    def __init__(self, total: int):
        self.total, self.done = total, 0
        self.started = self.reported = time.monotonic()
        self.lock = threading.Lock()

    def step(self) -> None:
        with self.lock:
            self.done += 1
            now = time.monotonic()
            done, elapsed = self.done, now - self.started
            if done < self.total and now - self.reported < self.EVERY:
                return
            self.reported = now
        if done == self.total:
            logger.info("диапазоны: NVD %d/%d за %s", done, self.total, _duration(elapsed))
        else:
            left = elapsed / done * (self.total - done)
            logger.info("диапазоны: NVD %d/%d, ~%s осталось", done, self.total, _duration(left))


def _duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return "%d с" % seconds
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return "%d мин %d с" % (minutes, seconds) if seconds else "%d мин" % minutes
    hours, minutes = divmod(minutes, 60)
    return "%d ч %d мин" % (hours, minutes)


def _cache_path(settings, source, cve) -> Optional[str]:
    if not settings.cache_dir:
        return None
    return os.path.join(settings.cache_dir, "nvd" if source == NVD else "cveorg",
                        cve.lower() + ".json")


def _fresh(path, ttl) -> bool:
    try:
        return bool(path and ttl) and time.time() - os.path.getmtime(path) < ttl
    except OSError:
        return False


def _fetch(source, url, cve, settings, headers, limiter) -> Optional[dict]:
    cached = _cache_path(settings, source, cve)
    if cached:
        try:
            os.makedirs(os.path.dirname(cached), exist_ok=True)
        except OSError as exc:
            logger.debug("кэш диапазонов недоступен: %s", exc)
            cached = None
    if cached and settings.cache_ttl:
        doc = read_cache(cached, settings.cache_ttl)
        if doc is not None:
            logger.debug("%s %s: из кэша", source, cve)
            return doc
    last = None
    for attempt in range(max(1, settings.retries)):
        if attempt:
            time.sleep(2 ** attempt)
        if limiter is not None:
            limiter.wait()
        try:
            body = download(url, settings.timeout, headers)
            if body is None:
                if source == NVD:
                    raise _Rejected("404")
                return None
            doc = json.loads(body)
        except _Rejected:
            raise
        except Exception as exc:  # сеть и мусор в ответе — повторяем
            last = exc
            continue
        if cached:
            write_cache(cached, body)
        return doc
    raise last


def ranges_for(docs: Docs, names: Set[str]) -> Tuple[Optional[Ranges], bool]:
    """Диапазоны продукта и признак «не известны из-за сбоя»: если источник
    не ответил, а другой ничего не знает, «неизвестен» было бы неправдой."""
    found = pick(docs.nvd, docs.cveorg, names)
    return found, found is None and bool(docs.failed)
