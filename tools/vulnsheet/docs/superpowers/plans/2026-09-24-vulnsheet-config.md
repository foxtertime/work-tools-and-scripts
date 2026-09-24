# vulnsheet: конфиг и стримы VEX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** У `vulnsheet` появляется YAML-конфиг (koji, RHEL, настройки загрузки VEX, маппинг пакетов на стримы VEX по версиям RHEL); VEX спрашивается про стрим из маппинга, koji — про пакет из входа; никаких откатов ни по версии RHEL, ни с пакета на его стримы.

**Architecture:** Новый модуль `config.py` читает и проверяет YAML и отдаёт `Config`; `vex.py` получает настройки загрузки записью `VexSettings` и стрим — аргументом `lookup`; `cli.py` сводит флаги с конфигом (флаг > конфиг > код) и передаёт стрим каждой задачи в `vex.lookup`. Зависимость односторонняя: `config` импортирует из `vex` `VexSettings` и `parse_rhel`, `vex` о конфиге не знает.

**Tech Stack:** Python 3.9+, стандартная библиотека, `koji`, PyYAML (только при заданном конфиге), `unittest`.

**Spec:** `tools/vulnsheet/docs/superpowers/specs/2026-09-24-vulnsheet-config-design.md` (дополняет `2026-09-24-vulnsheet-design.md`; где расходятся — действует он).

## Global Constraints

- Все пути ниже — от корня репозитория; тесты запускаются из `tools/vulnsheet/`: `python3 -m unittest discover -s tests -v`. Перед планом там 86 тестов, все зелёные.
- Python 3.9+: без `X | None`, без `match`; аннотации через `typing`.
- Зависимости: стандартная библиотека, `koji` (только внутри `kojiclient.connect`), PyYAML — импортируется только внутри `config` и только при заданном файле конфига. Тесты, которым нужен PyYAML, пропускаются без него (`skipUnless`), а не падают. В этом окружении PyYAML 6.0.3 установлен.
- Никаких откатов: `--rhel 9` — только продукты RHEL 9 (не 9.2); набор `vex_streams` берётся только с ключом, точно равным версии; пакет без маппинга — только обычный пакет, его стримы не берутся никогда. Подсказки `not listed (streams: …)` и `not listed (present for …)` остаются — они только объясняют `not listed`.
- Приоритет значений: флаг командной строки > конфиг > значение в коде.
- CSV, формат входа, файл отбраковки не меняются; в колонке `Компонент` — компонент из входа.
- Версия тулзы остаётся `1.0.0` (не выпущена); CHANGELOG-и дополняются, новая версия не заводится.
- Логи, сообщения и комментарии в коде — на русском; коммиты — на английском в Conventional Commits со скоупом `vulnsheet`, с футером `Co-Authored-By:`, называющим модель, которая писала коммит.
- В именах файлов, модулей и тестов нет слова «cve».
- Ветка `feature/vulnsheet`. `.tmp/` и `task.md` в корне не трогать и не коммитить; `__pycache__` и случайные `*.rejected.txt` не коммитить.

## Review Focus

1. **Версия RHEL числом с точкой в YAML** (`rhel: 9.10` или ключ `9.10:` без кавычек) — YAML прочитает это как число 9.1, и тулза молча взяла бы не ту версию. Ждут ошибку конфига с подсказкой писать версию в кавычках. Тест: `test_bad_values` (строка `rhel: 9.2`) и `test_float_version_key_is_rejected` (Task 3).
2. **Пустой файл конфига или секция без значений** (`vex:` без полей, `"9":` без пакетов) — ждут «конфига как бы нет», а не падения на `None`. Тесты: `test_empty_file_is_empty_config`, `test_empty_sections_are_allowed` (Task 3).
3. **Флаг задан и в конфиге другое значение** — ждут, что победит флаг; иначе человек не сможет разово переопределить тег. Тест: `test_flag_wins_over_config` (Task 4).
4. **Маппинг есть, но у Red Hat нужного стрима под этой версией нет** — ждут `not listed (streams: …)` со списком того, что есть, а не вердикт обычного пакета. Тест: `test_missing_stream_lists_what_exists` (Task 2).
5. **Настройки загрузки из конфига реально доходят до сети** (timeout, каталог кэша) — иначе поле в конфиге молча ничего не делает. Тест: `test_vex_settings_from_config_are_used` (Task 4).

---

## File Structure

```text
tools/vulnsheet/
├── vulnsheet.example.yaml     # Task 3 — образец конфига с комментариями
├── README.md                  # Task 5
├── CHANGELOG.md               # Task 5 — дополнить запись 1.0.0
├── vulnsheet/
│   ├── vex.py                 # Task 1 — VexSettings; Task 2 — стримы в lookup
│   ├── config.py              # Task 3 — новый
│   └── cli.py                 # Task 1 — VexSettings в вызове; Task 4 — --config
└── tests/
    ├── test_vex.py            # Task 1, Task 2
    ├── test_config.py         # Task 3 — новый
    └── test_cli.py            # Task 1 (подпись фейка), Task 4
```

Корень репозитория (Task 5): `CHANGELOG.md` — дополнить строку `vulnsheet` (1.0.0).

---

### Task 1: Настройки загрузки VEX одной записью

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/vex.py` (раздел «загрузка»: `download`, `fetch`, `fetch_all`; новая запись `VexSettings`)
- Modify: `tools/vulnsheet/vulnsheet/cli.py` (вызов `vex.fetch_all` в `_run`)
- Test: `tools/vulnsheet/tests/test_vex.py`, `tools/vulnsheet/tests/test_cli.py`

**Interfaces:**
- Produces:
  - `vex.VexSettings(NamedTuple)`: `cache_dir: Optional[str] = None` (None — без кэша), `cache_ttl: int = CACHE_TTL` (3600), `jobs: int = JOBS` (8), `retries: int = RETRIES` (3), `timeout: float = TIMEOUT` (30)
  - `vex.download(url: str, timeout: float = TIMEOUT) -> Optional[bytes]`
  - `vex.fetch(cve: str, settings: VexSettings = VexSettings()) -> Optional[dict]` — вызывает `download(url, settings.timeout)` позиционно
  - `vex.fetch_all(cves: Iterable[str], settings: VexSettings = VexSettings()) -> Tuple[Dict[str, Optional[dict]], Dict[str, str]]`

- [ ] **Step 1: Переписать тесты загрузки на новую подпись и дописать новые**

В `tools/vulnsheet/tests/test_vex.py` заменить строку импорта из `vulnsheet.vex` на две:

```python
from vulnsheet.vex import (NO_RECORD, Verdict, VexError, VexSettings, build_index,
                           fetch, fetch_all, lookup, parse_rhel, prepare_cache, vex_url)
```

В классе `FetchTest` заменить тела методов так (остальные методы класса не трогать):

```python
    def test_downloads_once_then_reads_cache(self):
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
        download.assert_called_once_with(vex_url(CVE), 30)

    def test_404_means_no_record(self):
        with mock.patch("vulnsheet.vex.download", return_value=None):
            self.assertIsNone(fetch(CVE, VexSettings(cache_dir=self.cache)))

    def test_corrupt_cache_falls_back_to_network(self):
        with open(self.cached(), "w") as handle:
            handle.write("{оборвано")
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
        download.assert_called_once()

    def test_stale_cache_is_refetched(self):
        with open(self.cached(), "w") as handle:
            json.dump({"старый": True}, handle)
        os.utime(self.cached(), (0, 0))
        with mock.patch("vulnsheet.vex.download", return_value=BODY):
            self.assertEqual(fetch(CVE, VexSettings(cache_dir=self.cache)), DOC)
```

И дописать в конец класса `FetchTest` два теста:

```python
    def test_settings_reach_download_and_retries(self):
        with mock.patch("vulnsheet.vex.download", side_effect=OSError("сеть")) as download:
            with self.assertRaises(VexError):
                fetch(CVE, VexSettings(retries=2, timeout=5))
        self.assertEqual([c.args for c in download.call_args_list],
                         [(vex_url(CVE), 5), (vex_url(CVE), 5)])
        self.assertEqual([c.args for c in self.sleep.call_args_list], [(1,)])

    def test_zero_ttl_never_reads_cache(self):
        settings = VexSettings(cache_dir=self.cache, cache_ttl=0)
        with mock.patch("vulnsheet.vex.download", return_value=BODY) as download:
            fetch(CVE, settings)
            fetch(CVE, settings)
        self.assertEqual(download.call_count, 2)
```

В классе `FetchAllTest`:
- в `test_indices_failures_and_missing_records` заменить `def download(url):` на `def download(url, timeout):` и вызов `fetch_all([CVE, "CVE-2026-1001", "CVE-2026-1002", CVE], jobs=2)` на `fetch_all([CVE, "CVE-2026-1001", "CVE-2026-1002", CVE], VexSettings(jobs=2))`;
- в `test_malformed_document_is_not_cached` заменить `fetch_all([CVE], cache)` на `fetch_all([CVE], VexSettings(cache_dir=cache))`.

В `tools/vulnsheet/tests/test_cli.py` заменить подпись метода фейка:

```python
    def _download(self, url, timeout=None):
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: FAIL — `ImportError: cannot import name 'VexSettings' from 'vulnsheet.vex'`.

- [ ] **Step 3: Ввести `VexSettings` и провести его через загрузку**

В `tools/vulnsheet/vulnsheet/vex.py`, в разделе «загрузка», сразу после класса `VexError` добавить:

```python
class VexSettings(NamedTuple):
    """Настройки загрузки VEX; значения по умолчанию — встроенные."""
    cache_dir: Optional[str] = None  # None — без кэша
    cache_ttl: int = CACHE_TTL       # секунд; 0 — кэш не читать
    jobs: int = JOBS
    retries: int = RETRIES
    timeout: float = TIMEOUT         # секунд на запрос
```

Заменить функцию `download` целиком:

```python
def download(url: str, timeout: float = TIMEOUT) -> Optional[bytes]:
    """Тело ответа; None при 404 (у Red Hat нет записи). Остальное — исключение."""
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        logger.debug("GET %s → %d за %.2f с", url, exc.code, time.monotonic() - started)
        if exc.code == 404:
            return None
        raise
    logger.debug("GET %s → %d за %.2f с", url, code, time.monotonic() - started)
    return body
```

Заменить функцию `fetch` целиком:

```python
def fetch(cve: str, settings: VexSettings = VexSettings()) -> Optional[dict]:
    """Документ VEX; None, если у Red Hat записи нет; VexError — не получен."""
    cached = (os.path.join(settings.cache_dir, cve.lower() + ".json")
              if settings.cache_dir else None)
    if cached:
        doc = _read_cache(cached, settings.cache_ttl)
        if doc is not None:
            logger.debug("%s: из кэша", cve)
            return doc
    url = vex_url(cve)
    last = None
    for attempt in range(settings.retries):
        try:
            body = download(url, settings.timeout)
            if body is None:
                return None
            doc = json.loads(body)
        except Exception as exc:  # сеть и мусор в ответе — повторяем
            last = exc
            if attempt < settings.retries - 1:
                time.sleep(2 ** attempt)
            continue
        if cached:
            _write_cache(cached, body)
        return doc
    raise VexError("%s: %s" % (url, last))
```

В функции `fetch_all`:
- заменить подпись на `def fetch_all(cves: Iterable[str], settings: VexSettings = VexSettings()) -> Tuple[Dict[str, Optional[dict]], Dict[str, str]]:` (перенос строки — как в текущем коде);
- `doc = fetch(cve, cache_dir)` → `doc = fetch(cve, settings)`;
- `_evict_cache(cache_dir, cve)` → `_evict_cache(settings.cache_dir, cve)`;
- `ThreadPoolExecutor(max_workers=max(1, jobs), thread_name_prefix="w")` → `ThreadPoolExecutor(max_workers=max(1, settings.jobs), thread_name_prefix="w")`.

В `tools/vulnsheet/vulnsheet/cli.py`, в `_run`, заменить строку

```python
            indices, failures = vex.fetch_all(cves, vex.prepare_cache(_cache_dir()))
```

на

```python
            settings = vex.VexSettings(cache_dir=vex.prepare_cache(_cache_dir()))
            indices, failures = vex.fetch_all(cves, settings)
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: OK, 88 тестов (86 + 2 новых).

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/vex.py tools/vulnsheet/vulnsheet/cli.py \
        tools/vulnsheet/tests/test_vex.py tools/vulnsheet/tests/test_cli.py
git commit -m "refactor(vulnsheet): pass VEX loading settings as one record

Co-Authored-By: <your model> <noreply@anthropic.com>"
```

---

### Task 2: Стримы в `vex.lookup`, без отката на стримы

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/vex.py` (константа `NO_STREAM`, функция `_wanted`, функция `lookup`)
- Test: `tools/vulnsheet/tests/test_vex.py`

**Interfaces:**
- Consumes: `Verdict`, `NOT_LISTED`, `NO_RECORD`, `STATE_RANK`, помощники `_split_product`, `_rhel_version`, `_component_name`, `_state_for`, `_errata_for`, `_cvss_for`, `_nvr_for`, `_date_key` — всё уже есть в `vex.py`.
- Produces:
  - `vex.NO_STREAM = "(no stream)"`
  - `vex.lookup(index: Optional[dict], component: str, rhel: str, stream: Optional[str] = None) -> Verdict`
  - правило: без `stream` — только обычный пакет (стримы не берутся никогда); со `stream` — только продукты пакета, чей стрим совпадает со `stream` целиком или частью после двоеточия; маркеры `not listed (streams: …)` (есть другие варианты пакета ровно под этой версией) и `not listed (present for …)` (нужный вариант есть только в соседних минорных потоках); `streams` важнее `present for`.

- [ ] **Step 1: Перевернуть старый тест и дописать тесты стримов**

В `tools/vulnsheet/tests/test_vex.py`, в классе `LookupTest`, заменить метод `test_stream_is_reported_when_nothing_else` на:

```python
    def test_stream_is_never_taken_for_the_package(self):
        # Без маппинга firefox — только обычный пакет. Стрим — другой продукт,
        # и его вердикт в строку не попадает, даже если больше ничего нет.
        doc = csaf(CVE, [("known_affected", RHEL9, "firefox::firefox:flatpak")])
        self.assertEqual(self.verdict(doc, "firefox").state,
                         "not listed (streams: firefox:flatpak)")
```

После класса `LookupTest` (перед `ParseRhelTest`) добавить:

```python
NGINX_FIXED = "nginx-2:1.20.1-22.el9_6.x86_64"


def nginx_doc():
    """Обычный nginx исправлен, стрим 1.26 уязвим, стрим 1.24 не будут чинить."""
    return csaf(CVE, [("fixed", APPSTREAM96, NGINX_FIXED),
                      ("known_affected", APPSTREAM96, "nginx::nginx:1.26"),
                      ("known_affected", APPSTREAM96, "nginx::nginx:1.24")],
                remediations=[vendor_fix(pid(APPSTREAM96, NGINX_FIXED)),
                              {"category": "no_fix_planned", "details": "Will not fix",
                               "product_ids": [pid(APPSTREAM96, "nginx::nginx:1.24")]}])


class StreamLookupTest(unittest.TestCase):
    def verdict(self, stream=None, component="nginx", doc=None):
        return lookup(build_index(doc or nginx_doc()), component, "9", stream)

    def test_plain_package_ignores_streams(self):
        verdict = self.verdict()
        self.assertEqual((verdict.state, verdict.fixed_nvr),
                         ("Fixed", "nginx-1.20.1-22.el9_6"))

    def test_mapped_stream_replaces_the_package(self):
        verdict = self.verdict("nginx:1.26")
        self.assertEqual((verdict.state, verdict.fixed_nvr, verdict.advisory_url),
                         ("Affected", "", ""))

    def test_each_stream_has_its_own_verdict(self):
        self.assertEqual(self.verdict("nginx:1.24").state, "Will not fix")

    def test_short_stream_form(self):
        self.assertEqual(self.verdict("1.26").state, "Affected")

    def test_package_inside_another_module(self):
        fixed_npm = "npm-1:10.8.2-1.el9_6.x86_64"
        doc = csaf(CVE, [("known_affected", APPSTREAM96, "npm::nodejs:20"),
                         ("fixed", APPSTREAM96, fixed_npm)],
                   remediations=[vendor_fix(pid(APPSTREAM96, fixed_npm))])
        self.assertEqual(self.verdict("nodejs:20", "npm", doc).state, "Affected")
        self.assertEqual(self.verdict(None, "npm", doc).state, "Fixed")

    def test_missing_stream_lists_what_exists(self):
        self.assertEqual(self.verdict("nginx:1.28").state,
                         "not listed (streams: (no stream), nginx:1.24, nginx:1.26)")

    def test_stream_only_in_minor_stream_hints_present_for(self):
        # Версия сравнивается точно: 9.2 в вердикт под 9 не попадает.
        doc = csaf(CVE, [("known_affected", EUS92, "nginx::nginx:1.26")])
        self.assertEqual(self.verdict("nginx:1.26", doc=doc).state,
                         "not listed (present for 9.2)")
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_vex -v`
Expected: FAIL — `TypeError: lookup() takes 3 positional arguments but 4 were given` в `StreamLookupTest`, и `test_stream_is_never_taken_for_the_package` падает с `'Affected' != 'not listed (streams: firefox:flatpak)'`.

- [ ] **Step 3: Переписать `lookup`**

В `tools/vulnsheet/vulnsheet/vex.py` после строки `FIXED = "Fixed"` добавить:

```python
NO_STREAM = "(no stream)"  # обычный пакет в списке стримов маркера
```

Перед функцией `lookup` добавить:

```python
def _wanted(variant: str, stream: Optional[str]) -> bool:
    """Тот ли это вариант пакета, о котором спрашивают.

    Без стрима — только обычный пакет: module/flatpak-стрим — другой
    продукт с тем же именем, и выдавать его вердикт за пакет нельзя. Со
    стримом — только он, целиком ('nginx:1.26') или частью после двоеточия
    ('1.26').
    """
    if not stream:
        return not variant
    return bool(variant) and (variant == stream or variant.split(":", 1)[-1] == stream)
```

Заменить функцию `lookup` целиком:

```python
def lookup(index: Optional[dict], component: str, rhel: str,
           stream: Optional[str] = None) -> Verdict:
    """Вердикт для компонента под версией RHEL; index=None — записи у Red Hat нет.

    Откатов нет: версия RHEL сравнивается точно, без стрима берётся только
    обычный пакет, со стримом — только этот стрим. Подсказки в маркере
    not listed лишь объясняют, почему ничего не нашлось.
    """
    if index is None:
        return Verdict(state=NO_RECORD)
    vuln, rem_index, cve = index["vuln"], index["rem"], index["cve"]
    if stream:
        logger.debug("%s %s: смотрим стрим %s", cve, component, stream)

    candidates = []
    siblings = {}     # версия → состояния нужного варианта в соседних потоках
    variants = set()  # другие варианты пакета ровно под этой версией
    for bucket, product_ids in vuln.get("product_status", {}).items():
        for product_id in product_ids:
            platform_id, component_id = _split_product(product_id, index["rels"])
            found = _rhel_version(index["cpes"].get(platform_id))
            if found is None:
                continue
            if _component_name(component_id, index["pkgs"]).lower() != component.lower():
                continue
            variant = component_id.split("::", 1)[1] if "::" in component_id else ""
            if not _wanted(variant, stream):
                if found == rhel:
                    variants.add(variant or NO_STREAM)
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
            })

    if not candidates:
        # Отсутствие в VEX — не «Not affected»: Red Hat перечисляет только то,
        # что оценил. Подсказка: какие варианты пакета есть под этой версией
        # (может, нужен маппинг на стрим), иначе — в каких соседних потоках
        # есть нужный вариант.
        state = NOT_LISTED
        if variants:
            state += " (streams: " + ", ".join(sorted(variants)) + ")"
        elif siblings:
            state += " (present for " + ", ".join(sorted(siblings)) + ")"
        return Verdict(state=state, severity=index["severity"])

    best = min(candidates, key=lambda c: (STATE_RANK.get(c["state"], 3.5),
                                          _date_key(c["date"])))
    states = sorted({c["state"] for c in candidates})
    if len(states) > 1:
        logger.debug("%s %s: несколько вердиктов под RHEL %s (%s), взят %s",
                     cve, component, rhel, ", ".join(states), best["state"])
    if variants:
        logger.debug("%s %s: другие варианты пакета не учитываются: %s",
                     cve, component, ", ".join(sorted(variants)))
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
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: OK, 95 тестов (88 + 7 новых в `StreamLookupTest`; переименованный тест числа не меняет).

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/vex.py tools/vulnsheet/tests/test_vex.py
git commit -m "feat(vulnsheet): look up VEX verdicts for a module stream, never fall back to streams

Co-Authored-By: <your model> <noreply@anthropic.com>"
```

---

### Task 3: Модуль конфига и образец

**Files:**
- Create: `tools/vulnsheet/vulnsheet/config.py`
- Create: `tools/vulnsheet/vulnsheet.example.yaml`
- Test: `tools/vulnsheet/tests/test_config.py`

**Interfaces:**
- Consumes: `vex.VexSettings` (Task 1), `vex.parse_rhel(value: str) -> str` (поднимает `ValueError`).
- Produces:
  - `config.ENV_VAR = "VULNSHEET_CONFIG"`
  - `class config.ConfigError(Exception)` — текст уже содержит путь файла
  - `config.Config(NamedTuple)`: `path: Optional[str] = None`, `koji_hub: Optional[str] = None`, `koji_tag: Optional[str] = None`, `rhel: Optional[str] = None`, `vex: VexSettings = VexSettings()` (`cache_dir` — `None`, если в конфиге не задан), `vex_streams: Dict[str, Dict[str, str]] = {}` (ключ — нормализованная версия RHEL)
  - `Config.stream_for(component: str, rhel: str) -> Optional[str]` — только набор ровно этой версии
  - `config.load_config(path: Optional[str]) -> Config` — `None` → `Config()`

- [ ] **Step 1: Написать падающие тесты**

`tools/vulnsheet/tests/test_config.py`:

```python
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from vulnsheet.config import Config, ConfigError, load_config
from vulnsheet.vex import VexSettings

try:
    import yaml  # noqa: F401 — только чтобы понять, есть ли PyYAML
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

ROOT = os.path.join(os.path.dirname(__file__), "..")

FULL = """\
koji:
  hub: https://koji.example.com/kojihub
  tag: sl9-updates
rhel: "9"
vex:
  cache_dir: ~/vulnsheet-cache
  cache_ttl: 0
  jobs: 4
  retries: 2
  timeout: 12.5
vex_streams:
  "9":
    nginx: nginx:1.26
    npm: nodejs:20
  "10":
    nodejs: nodejs:22
"""


class DefaultsTest(unittest.TestCase):
    def test_no_path_gives_builtin_values(self):
        cfg = load_config(None)
        self.assertEqual(cfg, Config())
        self.assertEqual(cfg.vex, VexSettings())
        self.assertIsNone(cfg.stream_for("nginx", "9"))


class StreamForTest(unittest.TestCase):
    CFG = Config(vex_streams={"9": {"nginx": "nginx:1.26"},
                              "9.2": {"nodejs": "nodejs:20"}})

    def test_exact_version(self):
        self.assertEqual(self.CFG.stream_for("nginx", "9"), "nginx:1.26")
        self.assertEqual(self.CFG.stream_for("nodejs", "9.2"), "nodejs:20")

    def test_minor_does_not_fall_back_to_major(self):
        self.assertIsNone(self.CFG.stream_for("nginx", "9.2"))

    def test_major_does_not_take_minor_set(self):
        self.assertIsNone(self.CFG.stream_for("nodejs", "9"))

    def test_unknown_package_or_version(self):
        self.assertIsNone(self.CFG.stream_for("vim", "9"))
        self.assertIsNone(self.CFG.stream_for("nginx", "10"))


class MissingYamlTest(unittest.TestCase):
    def test_config_without_pyyaml_is_reported(self):
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with self.assertRaises(ConfigError) as caught:
                load_config("vulnsheet.yaml")
        self.assertIn("python3-pyyaml", str(caught.exception))


@unittest.skipUnless(HAVE_YAML, "нужен PyYAML")
class LoadTest(unittest.TestCase):
    def setUp(self):
        self.room = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.room)

    def write(self, text):
        path = os.path.join(self.room, "vulnsheet.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def assertRejected(self, text, needle):
        with self.assertRaises(ConfigError) as caught:
            load_config(self.write(text))
        self.assertIn(needle, str(caught.exception))
        return caught.exception

    def test_full_file(self):
        path = self.write(FULL)
        cfg = load_config(path)
        self.assertEqual(cfg.path, path)
        self.assertEqual((cfg.koji_hub, cfg.koji_tag, cfg.rhel),
                         ("https://koji.example.com/kojihub", "sl9-updates", "9"))
        self.assertEqual(cfg.vex, VexSettings(
            cache_dir=os.path.expanduser("~/vulnsheet-cache"), cache_ttl=0,
            jobs=4, retries=2, timeout=12.5))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26", "npm": "nodejs:20"},
                                           "10": {"nodejs": "nodejs:22"}})

    def test_empty_file_is_empty_config(self):
        self.assertEqual(load_config(self.write(""))._replace(path=None), Config())

    def test_empty_sections_are_allowed(self):
        cfg = load_config(self.write("koji:\nvex:\nvex_streams:\n  \"9\":\n"))
        self.assertEqual(cfg.vex, VexSettings())
        self.assertEqual(cfg.vex_streams, {"9": {}})

    def test_unknown_nested_key_names_full_path(self):
        self.assertRejected("vex:\n  cache_tll: 10\n", "vex.cache_tll")

    def test_unknown_top_level_key(self):
        self.assertRejected("koj:\n  hub: x\n", "koj")

    def test_error_names_the_file(self):
        error = self.assertRejected("vex:\n  jobs: 0\n", "vex.jobs")
        self.assertIn("vulnsheet.yaml", str(error))

    def test_bad_values(self):
        cases = [
            ("vex:\n  jobs: 0\n", "vex.jobs"),
            ("vex:\n  jobs: true\n", "vex.jobs"),
            ("vex:\n  retries: 1.5\n", "vex.retries"),
            ("vex:\n  cache_ttl: -1\n", "vex.cache_ttl"),
            ("vex:\n  timeout: 0\n", "vex.timeout"),
            ("vex:\n  timeout: false\n", "vex.timeout"),
            ("vex:\n  cache_dir: ''\n", "vex.cache_dir"),
            ("koji:\n  tag: 9\n", "koji.tag"),
            ("koji:\n  hub: ''\n", "koji.hub"),
            ("rhel: nine\n", "rhel"),
            ("rhel: 9.2\n", "кавычк"),
            ("vex: [1]\n", "vex"),
            ("vex_streams: [nginx]\n", "vex_streams"),
            ("vex_streams:\n  \"9\": [nginx]\n", "vex_streams.9"),
            ("vex_streams:\n  \"9\":\n    nginx: ''\n", "vex_streams.9"),
            ("- a\n", "словар"),
        ]
        for text, needle in cases:
            with self.subTest(text=text):
                self.assertRejected(text, needle)

    def test_unquoted_integer_version_key(self):
        cfg = load_config(self.write("vex_streams:\n  9:\n    nginx: nginx:1.26\n"))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26"}})

    def test_float_version_key_is_rejected(self):
        # 9.10 без кавычек YAML прочитал бы как 9.1 — молча не та версия.
        self.assertRejected("vex_streams:\n  9.10:\n    nginx: nginx:1.26\n", "кавычк")

    def test_version_keys_are_normalised(self):
        cfg = load_config(self.write("vex_streams:\n  RHEL 9:\n    nginx: nginx:1.26\n"))
        self.assertEqual(cfg.vex_streams, {"9": {"nginx": "nginx:1.26"}})

    def test_duplicate_version_after_normalisation(self):
        self.assertRejected("vex_streams:\n  9:\n    a: b\n  RHEL 9:\n    c: d\n", "дважды")

    def test_missing_file(self):
        with self.assertRaises(ConfigError) as caught:
            load_config(os.path.join(self.room, "нет.yaml"))
        self.assertIn("не читается", str(caught.exception))

    def test_yaml_syntax_error(self):
        self.assertRejected("koji: [\n", "YAML")

    def test_example_file_is_valid(self):
        cfg = load_config(os.path.join(ROOT, "vulnsheet.example.yaml"))
        self.assertEqual(cfg.stream_for("nginx", "9"), "nginx:1.26")
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vulnsheet.config'`.

- [ ] **Step 3: Написать `config.py`**

`tools/vulnsheet/vulnsheet/config.py`:

```python
"""Конфиг vulnsheet: YAML, все поля необязательные.

Модуль читает и проверяет файл; сводит его с флагами командной строки cli.
PyYAML импортируется только при заданном файле: без конфига тулзе хватает
стандартной библиотеки и koji.
"""
import os
from typing import Dict, NamedTuple, Optional

from .vex import VexSettings, parse_rhel

ENV_VAR = "VULNSHEET_CONFIG"

_TOP_KEYS = {"koji", "rhel", "vex", "vex_streams"}
_KOJI_KEYS = {"hub", "tag"}
_VEX_KEYS = {"cache_dir", "cache_ttl", "jobs", "retries", "timeout"}


class ConfigError(Exception):
    """Конфиг не найден, не читается или не проходит проверку."""


class Config(NamedTuple):
    path: Optional[str] = None
    koji_hub: Optional[str] = None
    koji_tag: Optional[str] = None
    rhel: Optional[str] = None
    vex: VexSettings = VexSettings()
    # ключ — нормализованная версия RHEL; словарь по умолчанию общий, но его
    # никто не меняет: Config неизменяем по смыслу
    vex_streams: Dict[str, Dict[str, str]] = {}

    def stream_for(self, component: str, rhel: str) -> Optional[str]:
        """Стрим VEX для компонента — только из набора ровно этой версии RHEL.

        Отката нет: для 9.2 набор "9" не применяется, и наоборот.
        """
        return self.vex_streams.get(rhel, {}).get(component)


def load_config(path: Optional[str]) -> Config:
    if path is None:
        return Config()
    raw = _read_yaml(path)
    if raw is None:  # пустой файл
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("%s: корень конфига должен быть словарём" % path)
    _check_keys(raw, _TOP_KEYS, "", path)
    koji = _section(raw, "koji", path)
    _check_keys(koji, _KOJI_KEYS, "koji.", path)
    vex = _section(raw, "vex", path)
    _check_keys(vex, _VEX_KEYS, "vex.", path)

    defaults = VexSettings()
    cache_dir = _string(vex, "cache_dir", "vex.cache_dir", path)
    settings = VexSettings(
        cache_dir=os.path.expanduser(cache_dir) if cache_dir else None,
        cache_ttl=_integer(vex, "cache_ttl", "vex.cache_ttl", path, 0, defaults.cache_ttl),
        jobs=_integer(vex, "jobs", "vex.jobs", path, 1, defaults.jobs),
        retries=_integer(vex, "retries", "vex.retries", path, 1, defaults.retries),
        timeout=_timeout(vex, path, defaults.timeout),
    )
    return Config(
        path=path,
        koji_hub=_string(koji, "hub", "koji.hub", path),
        koji_tag=_string(koji, "tag", "koji.tag", path),
        rhel=_rhel(raw.get("rhel"), "rhel", path),
        vex=settings,
        vex_streams=_streams(raw.get("vex_streams"), path),
    )


def _read_yaml(path):
    try:
        import yaml  # только при заданном конфиге
    except ImportError:
        raise ConfigError("для конфига нужен PyYAML: поставьте python3-pyyaml "
                          "(или pip install pyyaml)")
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except OSError as exc:
        raise ConfigError("%s: не читается: %s" % (path, exc))
    except (yaml.YAMLError, ValueError) as exc:  # ValueError — не UTF-8
        raise ConfigError("%s: ошибка YAML: %s" % (path, exc))


def _check_keys(section, allowed, prefix, path):
    unknown = sorted(str(key) for key in section if str(key) not in allowed)
    if unknown:
        raise ConfigError("%s: неизвестный ключ %s" % (
            path, ", ".join(prefix + key for key in unknown)))


def _section(raw, key, path):
    value = raw.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("%s: %s должен быть словарём" % (path, key))
    return value


def _string(section, key, name, path):
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("%s: %s должен быть непустой строкой" % (path, name))
    return value.strip()


def _integer(section, key, name, path, minimum, default):
    value = section.get(key)
    if value is None:
        return default
    # bool в питоне — подкласс int: «jobs: true» не должно стать единицей
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError("%s: %s должен быть целым числом" % (path, name))
    if value < minimum:
        raise ConfigError("%s: %s должен быть не меньше %d" % (path, name, minimum))
    return value


def _timeout(section, path, default):
    value = section.get("timeout")
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError("%s: vex.timeout должен быть числом больше нуля" % path)
    return value


def _rhel(value, name, path):
    """Версия RHEL строкой или целым; число с точкой — ошибка: YAML читает
    9.10 как 9.1, и версия молча стала бы другой."""
    if value is None:
        return None
    if isinstance(value, float):
        raise ConfigError('%s: %s — версию с точкой пишите в кавычках: "9.2"' % (path, name))
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ConfigError('%s: %s — версия RHEL строкой, например "9" или "9.2"'
                          % (path, name))
    try:
        return parse_rhel(str(value))
    except ValueError as exc:
        raise ConfigError("%s: %s: %s" % (path, name, exc))


def _streams(value, path):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("%s: vex_streams должен быть словарём версия → пакеты" % path)
    result = {}
    for key, mapping in value.items():
        name = "vex_streams.%s" % key
        rhel = _rhel(key, name, path)
        if rhel is None:
            raise ConfigError("%s: %s — нужна версия RHEL" % (path, name))
        if rhel in result:
            raise ConfigError("%s: в vex_streams версия %s указана дважды" % (path, rhel))
        if mapping is None:
            mapping = {}
        if not isinstance(mapping, dict):
            raise ConfigError("%s: %s должен быть словарём пакет → стрим" % (path, name))
        streams = {}
        for package, stream in mapping.items():
            if (not isinstance(package, str) or not package.strip()
                    or not isinstance(stream, str) or not stream.strip()):
                raise ConfigError("%s: %s: пакет и стрим — непустые строки (%r: %r)"
                                  % (path, name, package, stream))
            streams[package.strip()] = stream.strip()
        result[rhel] = streams
    return result
```

- [ ] **Step 4: Написать образец конфига**

`tools/vulnsheet/vulnsheet.example.yaml`:

```yaml
# Конфиг vulnsheet. Все поля необязательные; флаг командной строки главнее
# значения отсюда, а значение отсюда — встроенного. Подключается флагом
# --config или переменной окружения VULNSHEET_CONFIG.

koji:
  hub: https://koji.example.com/kojihub   # то же, что --koji-url
  tag: sl9-updates                        # то же, что --tag

# То же, что --rhel. Версию пишите строкой в кавычках: YAML прочитал бы
# 9.10 как число 9.1.
rhel: "9"

vex:
  # По умолчанию — $XDG_CACHE_HOME/vulnsheet или ~/.cache/vulnsheet.
  cache_dir: ~/.cache/vulnsheet
  cache_ttl: 3600   # секунд; 0 — кэш не читать, всегда идти в сеть
  jobs: 8           # параллельных загрузок
  retries: 3        # попыток на документ
  timeout: 30       # секунд на запрос

# Стримы VEX: пакет из входа → стрим, как его пишет Red Hat. Набор берётся
# только для версии, ровно равной --rhel: для 9.2 набор "9" не применяется.
# Пакет без записи здесь — только обычный пакет, его стримы не берутся.
# Влияет только на VEX: koji по-прежнему спрашивается про пакет из входа.
vex_streams:
  "9":
    nginx: nginx:1.26
    npm: nodejs:20      # пакет внутри чужого модуля
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_config -v`
Expected: OK, 20 тестов (без PyYAML 14 из них — `skipped`).

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: OK, 115 тестов.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/vulnsheet/config.py tools/vulnsheet/vulnsheet.example.yaml \
        tools/vulnsheet/tests/test_config.py
git commit -m "feat(vulnsheet): add YAML config with VEX stream mapping

Co-Authored-By: <your model> <noreply@anthropic.com>"
```

---

### Task 4: Подключить конфиг к CLI

**Files:**
- Modify: `tools/vulnsheet/vulnsheet/cli.py`
- Test: `tools/vulnsheet/tests/test_cli.py`

**Interfaces:**
- Consumes: `config.load_config`, `config.ConfigError`, `config.ENV_VAR`, `Config.stream_for`, `Config.vex`, `Config.koji_hub/koji_tag/rhel` (Task 3); `vex.VexSettings`, `vex.fetch_all(cves, settings)`, `vex.lookup(index, component, rhel, stream)` (Tasks 1–2).
- Produces: флаг `--config PATH`; `--rhel`, `--koji-url`, `--tag` необязательны для argparse; нет значения ни во флаге, ни в конфиге → фатальная ошибка «нужен --tag или koji.tag в конфиге» (код 2); `ConfigError` → фатальная ошибка (код 2) без трейсбека.

- [ ] **Step 1: Написать падающие тесты**

В `tools/vulnsheet/tests/test_cli.py`:

Заменить строку импорта из `tests.fakes` на:

```python
from tests.fakes import APPSTREAM96, RHEL9, FakeKojiSession, csaf, pid
```

После определения `VIM_DOC` добавить:

```python
try:
    import yaml  # noqa: F401 — только чтобы понять, есть ли PyYAML
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

NGINX_BLOCK = BLOCK.replace("vim", "nginx")
# под RHEL 9 обычный nginx исправлен, а стрим nginx:1.26 — уязвим
NGINX_DOC = csaf("CVE-2026-73070", [("fixed", APPSTREAM96, "nginx-2:1.20.1-22.el9_6.x86_64"),
                                    ("known_affected", APPSTREAM96, "nginx::nginx:1.26")])
CONFIG = """\
koji:
  hub: https://koji.example.com/kojihub
  tag: sl9
rhel: "9"
vex_streams:
  "9":
    nginx: nginx:1.26
"""
```

В `CliCase.setUp`, сразу после строки с `mock.patch.dict(os.environ, {"XDG_CACHE_HOME": …}).start()`, добавить:

```python
        # настоящий конфиг из окружения того, кто гоняет тесты, сюда не ходит;
        # patch.dict вернёт переменную на место после теста
        os.environ.pop("VULNSHEET_CONFIG", None)
```

В класс `FatalTest` добавить:

```python
    def test_missing_required_value_is_fatal(self):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(BLOCK)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--rhel", "9", "--tag", "sl9", src, "-o", self.path("r.csv")])
        self.log = err.getvalue()
        self.assertFatal(code, "нужен --koji-url или koji.hub в конфиге")
        self.connect.assert_not_called()
```

Перед классом `BrokenPipeTest` добавить:

```python
@unittest.skipUnless(HAVE_YAML, "нужен PyYAML")
class ConfigTest(CliCase):
    def setUp(self):
        super().setUp()
        self.session.builds["nginx"] = "nginx-1.26.3-1.sl9"
        self.docs[vex_url("CVE-2026-73070")] = NGINX_DOC

    def write_config(self, text=CONFIG):
        path = self.path("vulnsheet.yaml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_raw(self, *argv, text=NGINX_BLOCK + "\n"):
        src = self.path("tasks.txt")
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(text)
        err = io.StringIO()
        with redirect_stderr(err):
            code = main([src, "-o", self.path("report.csv")] + list(argv))
        self.log = err.getvalue()
        return code

    def test_stream_goes_to_vex_and_plain_name_to_koji(self):
        code = self.run_raw("--config", self.write_config())
        self.assertEqual(code, EXIT_OK)
        line = self.report_lines()[1]
        self.assertIn(";nginx;nginx-1.26.3-1.sl9;", line)
        self.assertIn(";Affected;", line)
        self.assertEqual(self.session.calls, [("sl9", "nginx")])
        self.assertIn("nginx → nginx:1.26 (1)", self.log)
        self.assertIn("хаб https://koji.example.com/kojihub, тег sl9, RHEL 9", self.log)

    def test_without_mapping_plain_package_is_used(self):
        text = CONFIG.split("vex_streams:")[0]
        self.assertEqual(self.run_raw("--config", self.write_config(text)), EXIT_OK)
        self.assertIn(";Fixed;", self.report_lines()[1])
        self.assertNotIn("стримы VEX", self.log)

    def test_mapping_for_another_version_is_not_used(self):
        code = self.run_raw("--config", self.write_config(), "--rhel", "9.2")
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("стримы VEX", self.log)
        self.assertIn(";not listed", self.report_lines()[1])

    def test_flag_wins_over_config(self):
        path = self.write_config(CONFIG.replace("tag: sl9", "tag: sl9-old"))
        # если бы победил конфиг, тег sl9-old не нашёлся бы — код 2
        self.assertEqual(self.run_raw("--config", path, "--tag", "sl9"), EXIT_OK)
        self.assertEqual(self.session.calls, [("sl9", "nginx")])

    def test_config_from_environment(self):
        path = self.write_config()
        with mock.patch.dict(os.environ, {"VULNSHEET_CONFIG": path}):
            self.assertEqual(self.run_raw(), EXIT_OK)
        self.assertIn("конфиг: " + path, self.log)

    def test_vex_settings_from_config_are_used(self):
        path = self.write_config(CONFIG + "vex:\n  timeout: 7\n  cache_dir: %s\n"
                                 % self.path("mycache"))
        self.assertEqual(self.run_raw("--config", path), EXIT_OK)
        self.assertEqual(self.download.call_args.args,
                         (vex_url("CVE-2026-73070"), 7))
        self.assertTrue(os.path.exists(self.path("mycache/cve-2026-73070.json")))

    def test_broken_config_is_fatal(self):
        code = self.run_raw("--config", self.write_config("vex:\n  jobs: 0\n"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("vex.jobs", self.log)
        self.assertNotIn("Traceback", self.log)
        self.connect.assert_not_called()

    def test_missing_config_file_is_fatal(self):
        code = self.run_raw("--config", self.path("нет.yaml"))
        self.assertEqual(code, EXIT_FATAL)
        self.assertIn("не читается", self.log)
        self.assertNotIn("Traceback", self.log)
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `cd tools/vulnsheet && python3 -m unittest tests.test_cli -v`
Expected: FAIL — `ConfigTest` падает на `error: unrecognized arguments: --config` (SystemExit 2) и на `the following arguments are required`; `test_missing_required_value_is_fatal` — argparse завершает разбор с SystemExit вместо кода 2 из `main`.

- [ ] **Step 3: Изменить `cli.py`**

В `tools/vulnsheet/vulnsheet/cli.py`:

Строку `from . import __version__, kojiclient, logs, report, vex` заменить на:

```python
from . import __version__, config, kojiclient, logs, report, vex
```

В `_parser` заменить три определения аргументов `--rhel`, `--koji-url`, `--tag` на:

```python
    parser.add_argument("--config",
                        help="YAML-конфиг (по умолчанию — из $%s, иначе без конфига)"
                             % config.ENV_VAR)
    parser.add_argument("--rhel", type=_rhel,
                        help="версия RHEL: 9 — только 9, 9.2 — только 9.2 "
                             "(или rhel в конфиге)")
    parser.add_argument("--koji-url", help="URL kojihub (или koji.hub в конфиге)")
    parser.add_argument("--tag", help="koji-тег (или koji.tag в конфиге)")
```

Перед функцией `_run` добавить:

```python
def _settings(args):
    """Конфиг и три обязательных значения: флаг > конфиг > значение в коде."""
    path = args.config or os.environ.get(config.ENV_VAR) or None
    cfg = config.load_config(path)
    if path:
        logger.info("конфиг: %s", path)
    else:
        logger.info("без конфига")
    rhel = args.rhel or cfg.rhel
    hub = args.koji_url or cfg.koji_hub
    tag = args.tag or cfg.koji_tag
    for value, flag, key in ((rhel, "--rhel", "rhel"),
                             (hub, "--koji-url", "koji.hub"),
                             (tag, "--tag", "koji.tag")):
        if not value:
            raise _Fatal("нужен %s или %s в конфиге" % (flag, key))
    return cfg, rhel, hub, tag
```

В функции `_run`:
- первой строкой тела вставить `cfg, rhel, hub, tag = _settings(args)`;
- строку `logger.info("хаб %s, тег %s, RHEL %s", args.koji_url, args.tag, args.rhel)` заменить на:

```python
    logger.info("хаб %s, тег %s, RHEL %s", hub, tag, rhel)
    streams = {t.component: cfg.stream_for(t.component, rhel) for t in tasks}
    applied = Counter(t.component for t in tasks if streams[t.component])
    if applied:
        logger.info("стримы VEX для RHEL %s: %s", rhel, ", ".join(
            "%s → %s (%d)" % (name, streams[name], count) for name, count in applied.items()))
```

- внутри `if tasks:` заменить три строки

```python
            session = kojiclient.connect(args.koji_url)
            nvrs = kojiclient.latest_builds(session, args.tag, packages)
            settings = vex.VexSettings(cache_dir=vex.prepare_cache(_cache_dir()))
```

на

```python
            session = kojiclient.connect(hub)
            nvrs = kojiclient.latest_builds(session, tag, packages)
            settings = cfg.vex._replace(
                cache_dir=vex.prepare_cache(cfg.vex.cache_dir or _cache_dir()))
```

- строку `else vex.lookup(indices[t.cve], t.component, args.rhel)` заменить на `else vex.lookup(indices[t.cve], t.component, rhel, streams[t.component])`.

В функции `main`, сразу после блока `except _Fatal as exc: return _fatal(str(exc))`, добавить:

```python
    except config.ConfigError as exc:
        return _fatal(str(exc))
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `cd tools/vulnsheet && python3 -m unittest discover -s tests -v`
Expected: OK, 124 теста (115 + 1 в `FatalTest` + 8 в `ConfigTest`).

Run: `cd tools/vulnsheet && python3 -m vulnsheet --help`
Expected: в справке есть `--config`, у `--rhel`/`--koji-url`/`--tag` — «или … в конфиге».

- [ ] **Step 5: Commit**

```bash
git add tools/vulnsheet/vulnsheet/cli.py tools/vulnsheet/tests/test_cli.py
git commit -m "feat(vulnsheet): read settings and VEX streams from the config in the CLI

Co-Authored-By: <your model> <noreply@anthropic.com>"
```

---

### Task 5: Документация

**Files:**
- Modify: `tools/vulnsheet/README.md`
- Modify: `tools/vulnsheet/CHANGELOG.md`
- Modify: `CHANGELOG.md` (корень)

**Interfaces:**
- Consumes: поведение из Tasks 1–4, образец `tools/vulnsheet/vulnsheet.example.yaml`.

- [ ] **Step 1: README — требования**

В `tools/vulnsheet/README.md`, в разделе «## Требования», после пункта про `koji` добавить пункт:

```markdown
- `PyYAML` — только если задан конфиг (`--config` или `VULNSHEET_CONFIG`):
  системный пакет `python3-pyyaml` или `pip install pyyaml`. Без конфига не
  нужен.
```

Абзац под списком

```markdown
Переменных окружения и токенов не нужно. Кэш VEX лежит в
`$XDG_CACHE_HOME/vulnsheet` (по умолчанию `~/.cache/vulnsheet`) и живёт час.
```

заменить на

```markdown
Токенов не нужно. Из переменных окружения читается только `VULNSHEET_CONFIG`
— путь к конфигу, если не задан `--config`. Кэш VEX по умолчанию лежит в
`$XDG_CACHE_HOME/vulnsheet` (иначе `~/.cache/vulnsheet`) и живёт час; и то и
другое меняется в конфиге.
```

- [ ] **Step 2: README — запуск**

В разделе «## Запуск» заменить три строки таблицы:

```markdown
| `--rhel` | версия RHEL, обязательный: `9` — только 9, `9.2` — только 9.2; `RHEL 9`, `el9` тоже годятся |
| `--koji-url` | URL kojihub, обязательный |
| `--tag` | koji-тег, обязательный |
```

на

```markdown
| `--config` | YAML-конфиг (см. «Конфиг»); без него — из `VULNSHEET_CONFIG`, иначе без конфига |
| `--rhel` | версия RHEL: `9` — только 9, `9.2` — только 9.2; `RHEL 9`, `el9` тоже годятся. Обязательна — флагом или `rhel` в конфиге |
| `--koji-url` | URL kojihub. Обязателен — флагом или `koji.hub` в конфиге |
| `--tag` | koji-тег. Обязателен — флагом или `koji.tag` в конфиге |
```

После примера «Из буфера обмена» (перед «## Вход») добавить:

````markdown
С конфигом, где заданы хаб, тег и версия, хватает входа и выхода:

```bash
python3 -m vulnsheet --config vulnsheet.yaml tasks.txt -o report.csv
```

## Конфиг

YAML; все поля необязательные. Образец со всеми полями и комментариями —
[vulnsheet.example.yaml](vulnsheet.example.yaml). Подключается `--config
PATH` или переменной `VULNSHEET_CONFIG` (флаг главнее). Значение берётся так:
флаг командной строки, иначе конфиг, иначе встроенное.

| Поле | Смысл | Встроенное |
|---|---|---|
| `koji.hub`, `koji.tag`, `rhel` | то же, что `--koji-url`, `--tag`, `--rhel` | — |
| `vex.cache_dir` | каталог кэша VEX, `~` раскрывается | `$XDG_CACHE_HOME/vulnsheet` или `~/.cache/vulnsheet` |
| `vex.cache_ttl` | сколько секунд документ живёт в кэше; `0` — кэш не читать | `3600` |
| `vex.jobs` | параллельных загрузок | `8` |
| `vex.retries` | попыток на документ | `3` |
| `vex.timeout` | секунд на запрос | `30` |
| `vex_streams` | стримы VEX по версиям RHEL, см. ниже | — |

Версию RHEL пишите строкой в кавычках (`"9.2"`): YAML прочитал бы `9.10` как
число `9.1`, поэтому число с точкой — ошибка конфига.

Конфиг проверяется целиком до работы: неизвестный ключ (опечатка вроде
`vex.cache_tll`), неверный тип или значение вне границ — фатальная ошибка с
путём файла и полным именем ключа.

### Стримы VEX

Некоторые пакеты собираются из модульного стрима Red Hat: наш `nginx` — это
`nginx:1.26` у Red Hat. Для таких пакетов в `vex_streams` задаётся стрим:

```yaml
vex_streams:
  "9":
    nginx: nginx:1.26
    npm: nodejs:20      # пакет внутри чужого модуля
```

- Маппинг влияет только на VEX: koji по-прежнему спрашивается про пакет из
  входа (`nginx`), и в колонке `Компонент` — тоже он.
- Набор берётся только для версии, ровно равной `--rhel`: для `9.2` набор
  `"9"` не применяется, и наоборот.
- Пакет без записи в маппинге — только обычный пакет: его стримы у Red Hat
  не учитываются никогда, даже если обычного пакета нет.
- Какие подмены сработали, пишется в журнал строкой вида
  `стримы VEX для RHEL 9: nginx → nginx:1.26 (3)`.
````

- [ ] **Step 3: README — выход, журнал, коды возврата, разработка**

В разделе «## Выход» в списке «Маркеры в `RHEL state`» после пункта про `not listed (present for 9.2, 9.4)` добавить:

```markdown
- `not listed (streams: nginx:1.24, nginx:1.26)` — под этой версией у Red Hat
  есть другие варианты пакета: стримы или, если спрашивали стрим, обычный
  пакет (`(no stream)`). Обычно значит, что нужен или устарел маппинг в
  `vex_streams`.
```

Абзац «Как выбирается вердикт: …» заменить на:

```markdown
Как выбирается вердикт: версия RHEL сравнивается точно (`9` — только 9, не
9.2); имя компонента сравнивается точно (`vim` не совпадает с
`vim-enhanced`); без маппинга берётся только обычный пакет, с маппингом —
только заданный стрим; если под одной версией RHEL вердиктов несколько
(BaseOS и AppStream расходятся), побеждает самый опасный; эпоха в NVR
срезается, чтобы он сравнивался с `rpm -q`. Подсказки в скобках у
`not listed` только объясняют, почему ничего не нашлось, — данных из других
потоков и стримов в строку они не подставляют.
```

В разделе «## Журнал» в строке таблицы для `info` заменить `хаб, тег, RHEL;` на `конфиг (путь или «без конфига»); хаб, тег, RHEL; применённые стримы VEX;`.

В разделе «## Коды возврата» строку для кода `2` заменить на:

```markdown
| `2` | фатально: неверные аргументы; нет версии RHEL, хаба или тега ни во флагах, ни в конфиге; конфиг не найден, не читается или не проходит проверку; нет PyYAML при заданном конфиге; вход не читается, не в UTF-8 или пуст; выход не пишется; хаб koji недоступен, тега нет или не установлен `koji` |
```

В разделе «## Разработка» в таблицу модулей после строки `vex.py` добавить:

```markdown
| `config.py` | чтение и проверка YAML-конфига, выбор стрима VEX |
```

- [ ] **Step 4: CHANGELOG тулзы и корня**

В `tools/vulnsheet/CHANGELOG.md`, в конец абзаца записи `## 1.0.0 — 2026-09-24` (после «…подать снова.») добавить новый абзац:

```markdown
Хаб, тег, версию RHEL и настройки загрузки VEX можно держать в YAML-конфиге
(`--config` или `VULNSHEET_CONFIG`). Там же задаются стримы VEX: если наш
пакет собран из модульного стрима Red Hat (`nginx` → `nginx:1.26`), VEX
спрашивается про стрим, а koji — про пакет. Откатов нет: `--rhel 9` — только
RHEL 9, пакет без маппинга — только обычный пакет.
```

В корневом `CHANGELOG.md`, в пункте `` `vulnsheet` (1.0.0): … `` заменить последнее предложение «Заменяет три разрозненных скрипта.» на:

```markdown
  Хаб, тег, версия RHEL и стримы VEX для пакетов из модулей Red Hat
  задаются в YAML-конфиге. Заменяет три разрозненных скрипта.
```

(отступ — как у остальных строк пункта, два пробела).

- [ ] **Step 5: Проверки**

Run из корня репозитория — корневые проверки из `CLAUDE.md`, раздел «Проверки» (все четыре блока), и:

```bash
(cd tools/vulnsheet && python3 -m unittest discover -s tests)
```

Expected: ни одной строки `NOT EXECUTABLE` / `MISSING` / `BROKEN` (ссылка на `vulnsheet.example.yaml` в README резолвится); тесты — `OK`, 124.

- [ ] **Step 6: Commit**

```bash
git add tools/vulnsheet/README.md tools/vulnsheet/CHANGELOG.md CHANGELOG.md
git commit -m "docs(vulnsheet): document the config and VEX stream mapping

Co-Authored-By: <your model> <noreply@anthropic.com>"
```
