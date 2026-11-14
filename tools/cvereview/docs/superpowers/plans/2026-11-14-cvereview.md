# cvereview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Выпустить автономный HTML для ревью CSV vulnsheet с чеклистами по мере и переносимым JSON состояния.

**Architecture:** Чистые локальные JS-модули читают CSV, выбирают чеклисты, сопоставляют состояние и строят ссылки. Контроллер обслуживает один HTML, файловые input, кеш и доступную DOM-разметку выбранного прототипа. Python stdlib собирает исходники в воспроизводимый HTML только при разработке.

**Tech Stack:** JavaScript без runtime-зависимостей; Node built-in test runner; Python 3.9+ для сборки; Playwright для браузерной проверки.

**Spec:** `../specs/2026-11-14-cvereview-design.md`.

## Global Constraints

- `tools/cvereview/cvereview.html`, версия 0.1.0, один файл открывается через file://.
- CSS, JS, шрифты и иконки встроены; без внешних запросов и runtime-зависимостей.
- CSV и JSON выбираются вручную; нет доступа к папке или автозаписи на диск.
- Пул: «Ожидает ревью» или «Готов», непустой разработчик, кроме SecOps.
- Чеклисты по всем 11 мерам; unseen/ok/bad; done разрешён после отметки всех пунктов.
- Ключ задачи — JSON-тройка Task ID, CVE ID, компонент; изменившийся контекст/профиль требует повторного ревью.
- Чужие локальные файлы и соседние тулзы не изменять. Работа в подготовленной feature/cvereview.

## Review Focus

- Невалидный повторный CSV/JSON не должен затирать рабочую сессию: Task 3/4, атомарность загрузки.
- Один Task ID может содержать разные CVE/компоненты: Task 1/3, идентичность и отсутствие слипания.
- Смена меры/версии чеклиста не переносит галочки по позиции: Task 2/3, previousReview и unseen.
- Импорт из более старой сессии с архивными задачами: Task 3, явное переопределение и сохранение несопоставленных записей.
- Кавычки/HTML/URL из файлов не исполняются, недоступный кеш не мешает работе: Task 1/4/5, реальные вредоносные ячейки и отказ localStorage.

## Files and responsibilities

- `assets/js/csv.js`: декодирование и полный CSV-разбор, нормализация полей, диагностика и ключи.
- `assets/js/checklists.js`: справочник профилей, ID/версии/пояснения, выбор по мере.
- `assets/js/links.js`: проверка URL и шаблонов, кнопки тикета/GitLab/CVE/RHSA.
- `assets/js/model.js`: рабочая сессия, переходы, basis/повторное ревью, JSON validate/import/export.
- `assets/js/app.js`: DOM/события, загрузки/скачивание/кеш, фильтры, страницы по 50 карточек, отмена.
- `assets/review.html`, `assets/style.css`, `assets/fonts/`: выбранный UI и локальные ресурсы.
- `build.py`: детерминированная упаковка и `--check`; `cvereview.html`: результат.
- `tests/{csv,checklists,links,model}.test.cjs`, `tests/browser.cjs`: регрессии ядра и реальный HTML.
- `README.md`, `TODO.md`, `CHANGELOG.md`, `VERSION`, `examples/vulnsheet-demo.csv`: использование, версия, пример.

### Task 1: CSV and row identity

**Files:** Create `assets/js/csv.js`, `tests/csv.test.cjs`, `tests/helpers.cjs`.

**Interfaces:** `CR.csv` in browser / CommonJS in Node. `parse(text, sourceName='') -> table`; `decode(Uint8Array) -> {text,encoding}`; `read(bytes,sourceName) -> table`; `identity(row) -> {task,cve,component}`; `keyOf(row) -> string`; `eligible(row) -> boolean`. Table `{sourceName,headers,rows,diagnostics,delimiter,encoding}`; rows use task/cve/component/dev/status/measure/sl/rh/p/d/rstate/severity/cvss/comment/start/end/fixdate/rhsa/link/ai_* plus raw fields and source record number.

- [ ] Write tests: semicolon CSV with pre-header, CRLF and quoted multiline/escaped quote fields; comma/tab/BOM/cp1251; required headers, malformed quotes/NUL, shuffled headers; empty identifiers, exact/conflicting duplicates; case/space status matching and both accepted statuses; distinct tuples with same Task ID.
- [ ] Run `node --test tools/cvereview/tests/csv.test.cjs`; observe failures from absent parser.
- [ ] Implement a character-state CSV parser, delimiter/header selection, decoder and row normalization; preserve raw values, reject conflicting duplicates before returning a new table.
- [ ] Run the same test command; expected all tests pass.
- [ ] Commit `feat(cvereview): parse browser-loaded vulnerability CSV`.

### Task 2: Measure profiles and links

**Files:** Create `assets/js/checklists.js`, `assets/js/links.js`, corresponding test files.

**Interfaces:** `CR.checklists.forMeasure(measure) -> {id,version,label,warning,items:[{id,label,description}]}` and `byId(id) -> profile|null`; `CR.links.safeURL(value) -> string|null`, `validateTemplate(value) -> string`, `forRow(row,settings) -> [{id,label,url,reason?}]`. Defaults: tracker URL from spec, GitLab unset.

- [ ] Write tests for all exact production measure names, normalized matching, unknown/empty fallback, unique semantic IDs and nonempty descriptions; special non-applicability profile without build/patch checks.
- [ ] Write link tests: full Task URL, encoded component path, disabled unconfigured GitLab, CVE fallback, conditional RHSA, rejected unsafe/malformed protocols and invalid templates.
- [ ] Run `node --test tools/cvereview/tests/checklists.test.cjs tools/cvereview/tests/links.test.cjs`; observe RED.
- [ ] Implement the spec's 11 profiles plus two explicit fallback profiles, and HTTP(S)-only link construction.
- [ ] Run `node --test tools/cvereview/tests/*.test.cjs`; expected all pass.
- [ ] Commit `feat(cvereview): add measure-specific checklists and task links`.

### Task 3: State model and JSON

**Files:** Create `assets/js/model.js`, `tests/model.test.cjs`.

**Interfaces:** `CR.model.create(table, previousSession=null) -> session`; `setCheck(session,key,item,value) -> session`; `decide(session,key,pool,comment?) -> session`; `importJSON(session,text) -> {session,summary}`; `exportJSON(session) -> string`; `profile(row)`, `complete(record,profile)`, `basis(row)`. Session holds table, records array keyed by identity, settings, dirty. Functions never mutate caller state; failures throw user-readable errors. JSON schema/app/profile snapshots follow the spec.

- [ ] Write tests for unseen initial state, per-card isolation, completion guard, all marked including bad, blank problem comment, return preserving checks, and done read-only checks.
- [ ] Write tests for round-trip, reordered rows, changed build/measure/profile version, prior snapshot retention, ignored unrelated fields, archived records, explicit import override, invalid/duplicate keys/unknown schema/enums/done with unseen, and atomic failure.
- [ ] Run `node --test tools/cvereview/tests/model.test.cjs`; observe RED.
- [ ] Implement immutable transitions and strict validation; compare normalized basis and profile; retain historical profile labels. Merge selected JSON explicitly; records outside current eligibility remain archived.
- [ ] Run `node --test tools/cvereview/tests/*.test.cjs`; expected all pass.
- [ ] Commit `feat(cvereview): persist review decisions and reconcile updated CSV`.

### Task 4: Working standalone UI

**Files:** Create `assets/review.html`, `assets/style.css`, `assets/js/app.js`, `assets/fonts/`, `build.py`, `tests/browser.cjs`, `examples/vulnsheet-demo.csv`, `VERSION`.

**Interfaces:** The controller consumes CR modules from Tasks 1–3. Real file inputs `csv-file`, `state-file`; buttons `load-csv`, `load-state`, `save-state`; cards identified with stable `data-key`, check inputs with `data-item`. Cache namespace `cvereview:workspace:v1`, holding CSV text, source name and exported state. The build places inline JS in csv/checklists/links/model/app order; no imports/fetch at runtime.

- [ ] Write browser scenarios for empty app, real CSV upload, correct eligibility/profile, tri-state gating, required problem comment, undo, JSON download/reimport, changed source invalidation, unsafe cell rendering, bad file atomicity, reload/cache failure, links and mobile layout. Run on missing HTML; observe failure.
- [ ] Implement chosen prototype layout without UI LAB/demo rows, measure-specific right sidebar, settings and optional release label. Provide live source diagnostics and separate browser-cache/JSON status, filters and pagination of 50 cards.
- [ ] Implement file operations transactionally and cache restoration via validated CSV+JSON. Imports clear undo. Exports download JSON; no claim of automatic filesystem writes. Rebuild only affected card for check changes to preserve focus/open details.
- [ ] Implement deterministic builder with font data URLs and local licenses, preserving safe serialization of source assets. Build with `python3 tools/cvereview/build.py`.
- [ ] Run all Node tests and `PLAYWRIGHT_MODULE=<installed module> node tools/cvereview/tests/browser.cjs`. Expected all scenarios pass; file://, no external requests; 360–1440 px and correct 3:1 desktop split.
- [ ] Commit `feat(cvereview): ship standalone CSV review page`.

### Task 5: Documentation, reproduction and final verification

**Files:** Update tool `README.md`, `TODO.md`, add `CHANGELOG.md`; update root README/CHANGELOG/TODO only for this tool; finalize generated HTML and plan checkboxes.

- [ ] Document browser usage, JSON precedence, pool rules, all measure profiles, stale-review behavior, cache limits, configuring internal links, version/build/tests and example CSV.
- [ ] Remove completed tool TODO; keep only genuinely deferred work, without starting unrelated TODO tasks.
- [ ] Run full Node and browser suites, `python3 tools/cvereview/build.py --check`, root required checks and `git diff --check`. Verify rebuilding leaves HTML unchanged.
- [ ] Commit `docs(cvereview): document offline review workflow and state files`.
- [ ] Request one fresh whole-branch review against this plan/spec; fix Important/Critical findings with RED→GREEN tests; record minor findings and rulings in ledger.
- [ ] Leave completed feature branch without merge/push/publication; open the real cvereview.html in Chrome and report result and material limitations.
