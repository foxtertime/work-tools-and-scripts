"""Статус CVE для компонента в RHEL по Red Hat CSAF/VEX.

Лента VEX на security.access.redhat.com — тот же источник, из которого
рисуется портал CVE Red Hat, и самый свежий: legacy API /hydra отстаёт на
недели.
"""
import json
import logging
import os
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, NamedTuple, Optional, Tuple

from . import __version__

logger = logging.getLogger(__name__)

NO_RECORD = "no VEX record"
NOT_LISTED = "not listed"
FETCH_ERROR = "fetch error"
FIXED = "Fixed"
VEX_URL = "https://security.access.redhat.com/data/csaf/v2/vex/{year}/{cve}.json"
USER_AGENT = "vulnsheet/%s (+CSAF VEX client)" % __version__
CACHE_TTL = 3600  # секунд
JOBS = 8
RETRIES = 3
TIMEOUT = 30  # секунд

VERSION_RE = re.compile(r"^\d+(\.\d+)*$")

# Семейства CPE, означающие саму ОС RHEL во всех потоках поддержки. Всё
# остальное — другой продукт с похожей на RHEL версией (enterprise_linux_ai,
# rhel_software_collections, ceph_storage…), и за RHEL его выдавать нельзя.
RHEL_FAMILIES = {
    "enterprise_linux", "enterprise_linux_eus", "rhel_eus", "rhel_e4s",
    "rhel_aus", "rhel_tus", "rhel_els", "rhel_eus_long_life",
    "rhel_mission_critical", "rhel_extras_rt",
}
CPE_RE = re.compile(r"cpe:/[oah]:redhat:([a-z_0-9]+):(\d+(?:\.\d+)*)")
ARCH_SUFFIX = re.compile(
    r"\.(src|noarch|i[3-6]86|x86_64|ia64|aarch64|armv7hl|armv7hnl|"
    r"ppc|ppc64|ppc64le|s390|s390x|riscv64)$")

# Корзина product_status → состояние, как его пишет портал. known_affected
# уточняется ремедиацией (см. _state_for).
BUCKET_STATE = {
    "fixed": FIXED,
    "known_not_affected": "Not affected",
    "under_investigation": "Under investigation",
    "known_affected": "Affected",
}

# Если у одного компонента под одной версией RHEL несколько вердиктов
# (BaseOS и AppStream расходятся), побеждает самый опасный: фикс в одном
# репозитории не должен прятать уязвимость в другом.
STATE_RANK = {
    "Affected": 0,
    "Fix deferred": 1,
    "Will not fix": 2,
    "Out of support scope": 3,
    "Under investigation": 4,
    FIXED: 5,
    "Not affected": 6,
}


class Verdict(NamedTuple):
    state: str = ""
    severity: str = ""
    cvss: str = ""
    fixed_nvr: str = ""
    fix_date: str = ""  # ISO, YYYY-MM-DD
    advisory_url: str = ""


def parse_rhel(value: str) -> str:
    """'RHEL 9' / 'rhel-9' / 'el9' → '9'; '9.2' остаётся '9.2'."""
    rhel = re.sub(r"^(rhel|el)[-_ ]*", "", str(value).strip(), flags=re.I)
    if not VERSION_RE.match(rhel):
        raise ValueError("версия RHEL должна быть вида 9 или 9.2, получено %r" % value)
    return rhel


# --------------------------------------------------------------------------
# индекс документа
# --------------------------------------------------------------------------

def build_index(doc: dict) -> dict:
    """Всё, что нужно lookup, — один раз на CVE, а не на каждую строку."""
    vuln = doc["vulnerabilities"][0]
    cpes, pkgs = _index_tree(doc)
    return {
        "cve": vuln.get("cve", ""),
        "vuln": vuln,
        "cpes": cpes,
        "pkgs": pkgs,
        "rels": {rel["full_product_name"]["product_id"]:
                 (rel["relates_to_product_reference"], rel["product_reference"])
                 for rel in doc.get("product_tree", {}).get("relationships", [])},
        "rem": _remediation_index(vuln),
        "severity": doc["document"].get("aggregate_severity", {}).get("text", ""),
    }


def _index_tree(doc):
    """product_id → cpe и product_id → имя пакета (из purl)."""
    cpes, pkgs = {}, {}

    def walk(branches):
        for branch in branches:
            product = branch.get("product")
            if product:
                product_id = product["product_id"]
                helper = product.get("product_identification_helper", {})
                if helper.get("cpe"):
                    cpes[product_id] = helper["cpe"]
                match = re.match(r"pkg:[^/]+/(?:redhat/)?([^@?]+)", helper.get("purl") or "")
                if match:
                    pkgs[product_id] = match.group(1)
            walk(branch.get("branches", []))

    walk(doc.get("product_tree", {}).get("branches", []))
    return cpes, pkgs


def _remediation_index(vuln):
    index = {}
    for rem in vuln.get("remediations", []):
        for product_id in rem.get("product_ids", []):
            index.setdefault(product_id, []).append(rem)
    return index


# --------------------------------------------------------------------------
# разбор одного продукта
# --------------------------------------------------------------------------

def _rhel_version(cpe):
    """'cpe:/o:redhat:enterprise_linux:9::baseos' → '9'; не RHEL → None."""
    match = CPE_RE.match(cpe or "")
    if not match:
        return None
    family, version = match.groups()
    return version if family in RHEL_FAMILIES else None


def _split_product(product_id, rels):
    if product_id in rels:
        return rels[product_id]
    platform, _, component = product_id.partition(":")
    return platform, component


def _component_name(component_id, pkgs):
    if component_id in pkgs:
        return pkgs[component_id]
    plain = component_id.split("::", 1)[0]
    return ARCH_SUFFIX.sub("", re.sub(r"-\d+:.*$", "", plain))


def _state_for(product_id, bucket, rem_index):
    """Для known_affected точное состояние ('Will not fix', 'Fix deferred',
    'Out of support scope') Red Hat пишет в details ремедиации."""
    if bucket != "known_affected":
        return BUCKET_STATE.get(bucket, bucket)
    for rem in rem_index.get(product_id, []):
        if rem.get("category") in ("no_fix_planned", "none_available"):
            details = (rem.get("details") or "").strip()
            if details:
                return details
    return "Affected"


def _cvss_for(product_id, vuln):
    """Оценка продукта. Если продукта нет ни в одном блоке — только когда
    все блоки согласны: чужая оценка хуже, чем никакой."""
    scores = vuln.get("scores", [])
    chosen = next((s for s in scores if product_id in s.get("products", [])), None)
    if chosen is None:
        distinct = set()
        for block in scores:
            for key in ("cvss_v4", "cvss_v3"):
                if block.get(key):
                    distinct.add(block[key].get("baseScore", ""))
                    break
        return distinct.pop() if len(distinct) == 1 else ""
    for key in ("cvss_v4", "cvss_v3"):
        if chosen.get(key):
            return chosen[key].get("baseScore", "")
    return ""


def _date_key(date):
    """Свежие errata первыми, без даты — последними."""
    try:
        return tuple(-int(part) for part in date.split("-"))
    except ValueError:
        return (0, 0, 0)


def _errata_for(product_id, rem_index):
    """(url, дата ISO) самой свежей vendor_fix-ремедиации."""
    fixes = [r for r in rem_index.get(product_id, [])
             if r.get("category") == "vendor_fix" and r.get("url")]
    if not fixes:
        return "", ""
    newest = min(fixes, key=lambda r: _date_key((r.get("date") or "")[:10]))
    return newest["url"], (newest.get("date") or "")[:10]


def _nvr_for(component_id):
    """'openssl-1:3.5.8-1.el9_8.x86_64' → 'openssl-3.5.8-1.el9_8'.

    Эпоха срезается, чтобы NVR сравнивался с выводом `rpm -q`. Имя RPM не
    содержит двоеточия, поэтому первое '-<цифры>:' — всегда эпоха. У
    неисправленного продукта версии нет — пустая строка.
    """
    plain = component_id.split("::", 1)[0]
    if ":" not in plain:
        return ""
    return re.sub(r"-\d+:", "-", ARCH_SUFFIX.sub("", plain), count=1)


# --------------------------------------------------------------------------
# вердикт
# --------------------------------------------------------------------------

def lookup(index: Optional[dict], component: str, rhel: str) -> Verdict:
    """Вердикт для компонента под версией RHEL; index=None — записи у Red Hat нет."""
    if index is None:
        return Verdict(state=NO_RECORD)
    vuln, rem_index, cve = index["vuln"], index["rem"], index["cve"]

    candidates = []
    siblings = {}  # версия → состояния, для соседних минорных потоков
    for bucket, product_ids in vuln.get("product_status", {}).items():
        for product_id in product_ids:
            platform_id, component_id = _split_product(product_id, index["rels"])
            found = _rhel_version(index["cpes"].get(platform_id))
            if found is None:
                continue
            if _component_name(component_id, index["pkgs"]).lower() != component.lower():
                continue
            state = _state_for(product_id, bucket, rem_index)
            if found != rhel:
                if found.split(".")[0] == rhel.split(".")[0]:
                    siblings.setdefault(found, set()).add(state)
                continue
            url, date = _errata_for(product_id, rem_index)
            candidates.append({
                "state": state, "url": url, "date": date,
                "cvss": _cvss_for(product_id, vuln),
                "nvr": _nvr_for(component_id),
                "variant": component_id.split("::", 1)[1] if "::" in component_id else "",
            })

    # Спрашивали обычный пакет; module/flatpak-стрим — другой продукт с тем
    # же именем. Берём стримы, только если ничего другого под этим именем нет.
    plain = [c for c in candidates if not c["variant"]]
    streams = sorted({c["variant"] for c in candidates if c["variant"]})
    if plain:
        if streams:
            logger.debug("%s %s: стримы %s не учитываются", cve, component, ", ".join(streams))
        candidates = plain
    elif streams:
        logger.debug("%s %s: обычного пакета нет, взяты стримы %s", cve, component,
                     ", ".join(streams))

    if not candidates:
        # Отсутствие в VEX — не «Not affected»: Red Hat перечисляет только то,
        # что оценил. Если есть соседние минорные потоки — говорим об этом.
        state = NOT_LISTED
        if siblings:
            state += " (present for " + ", ".join(sorted(siblings)) + ")"
        return Verdict(state=state, severity=index["severity"])

    best = min(candidates, key=lambda c: (STATE_RANK.get(c["state"], 3.5),
                                          _date_key(c["date"])))
    states = sorted({c["state"] for c in candidates})
    if len(states) > 1:
        logger.debug("%s %s: несколько вердиктов под RHEL %s (%s), взят %s",
                     cve, component, rhel, ", ".join(states), best["state"])
    divergent = sorted(v for v, found_states in siblings.items()
                       if found_states - {best["state"]})
    if divergent:
        logger.debug("%s %s: у потоков %s другой вердикт", cve, component,
                     ", ".join(divergent))

    # NVR фикса — только у Fixed и только по той errata, что в строке.
    fixed_nvr = "|".join(sorted({c["nvr"] for c in candidates
                                 if c["nvr"] and c["state"] == FIXED
                                 and c["url"] == best["url"]}))
    return Verdict(state=best["state"], severity=index["severity"],
                   cvss=str(best["cvss"]), fixed_nvr=fixed_nvr,
                   fix_date=best["date"], advisory_url=best["url"])


# --------------------------------------------------------------------------
# загрузка
# --------------------------------------------------------------------------

class VexError(Exception):
    """Документ VEX не получен после всех попыток."""


def vex_url(cve: str) -> str:
    return VEX_URL.format(year=cve.split("-")[1], cve=cve.lower())


def download(url: str) -> Optional[bytes]:
    """Тело ответа; None при 404 (у Red Hat нет записи). Остальное — исключение."""
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        logger.debug("GET %s → %d за %.2f с", url, exc.code, time.monotonic() - started)
        if exc.code == 404:
            return None
        raise
    logger.debug("GET %s → %d за %.2f с", url, code, time.monotonic() - started)
    return body


def _read_cache(path, ttl):
    """Документ из кэша или None: нет, устарел или испорчен — идём в сеть."""
    try:
        if time.time() - os.path.getmtime(path) >= ttl:
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _write_cache(path, body):
    """Атомарно: оборванная запись не должна отравить кэш. Ошибка — не повод
    ронять прогон."""
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
    except OSError as exc:
        logger.debug("кэш %s не записан: %s", path, exc)


def prepare_cache(path: str) -> Optional[str]:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        logger.warning("кэш VEX отключён: %s", exc)
        return None
    return path


def fetch(cve: str, cache_dir: Optional[str] = None,
          ttl: int = CACHE_TTL) -> Optional[dict]:
    """Документ VEX; None, если у Red Hat записи нет; VexError — не получен."""
    cached = os.path.join(cache_dir, cve.lower() + ".json") if cache_dir else None
    if cached:
        doc = _read_cache(cached, ttl)
        if doc is not None:
            logger.debug("%s: из кэша", cve)
            return doc
    url = vex_url(cve)
    last = None
    for attempt in range(RETRIES):
        try:
            body = download(url)
            if body is None:
                return None
            doc = json.loads(body)
        except Exception as exc:  # сеть и мусор в ответе — повторяем
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
            continue
        if cached:
            _write_cache(cached, body)
        return doc
    raise VexError("%s: %s" % (url, last))


def fetch_all(cves: Iterable[str], cache_dir: Optional[str] = None,
              jobs: int = JOBS) -> Tuple[Dict[str, Optional[dict]], Dict[str, str]]:
    """Индексы документов по уникальным CVE и ошибки загрузки.

    Индекс None — у Red Hat записи нет. CVE с ошибкой в индексы не попадает.
    """
    cves = list(dict.fromkeys(cves))
    indices, failures = {}, {}
    lock = threading.Lock()
    done = 0
    step = max(1, len(cves) // 10)

    def load(cve):
        nonlocal done
        try:
            doc = fetch(cve, cache_dir)
            index = build_index(doc) if doc is not None else None
        except Exception as exc:  # в том числе испорченный документ
            with lock:
                failures[cve] = str(exc)
            logger.warning("VEX для %s не получен: %s", cve, exc)
        else:
            with lock:
                indices[cve] = index
        with lock:
            done += 1
            if done % step == 0 or done == len(cves):
                logger.info("VEX: %d/%d CVE", done, len(cves))

    with ThreadPoolExecutor(max_workers=max(1, jobs), thread_name_prefix="w") as pool:
        list(pool.map(load, cves))
    return indices, failures
