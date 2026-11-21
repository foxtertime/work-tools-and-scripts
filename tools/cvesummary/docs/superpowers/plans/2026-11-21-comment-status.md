# Статус «Ожидает комментарий» — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** статус «Ожидает комментарий» считается как ревью, а показывается отдельно, пурпурным; в `cvereview` входит в пул ревью.

**Architecture:** в `roles.js` — роль `isComment` и общая `isSubmitted`
(ревью или комментарий) для расчётов скорости и темпа. Отображения
(`segments.js`, `render.js`, `drilldown.js`) получают ключ `comment` рядом
с `review`. В `cvereview` — одна строка правила пула и список фильтра.

**Tech Stack:** ванильный JS (UMD-модули), `node --test`, Playwright, Python `unittest`.

**Spec:** [`../specs/2026-11-21-comment-status-design.md`](../specs/2026-11-21-comment-status-design.md)

## Global Constraints

- Текст статуса: «Ожидает комментарий»; сравнение через `roles.norm` → `'ожидает комментарий'`.
- Цвет `--st-comment`: светлая тема `#8E3FAF`, тёмная и `.hero` `#C99BE6`.
- Подписи: сегмент шапки «Комментарий»; роль карточки «Ожидает комментарий», счётчик «комментарий»; раздел «Ожидает комментарий по принятой мере»; легенда «ожидает комментарий».
- Версии: `cvesummary` 1.43.0, `cvereview` 0.9.0; корневой `CHANGELOG.md` — в `[Unreleased]`.
- Коммиты на английском, Conventional Commits, scope = имя тулзы.

## Review Focus

- Регистр/пробелы: `'  ОЖИДАЕТ  комментарий '` — та же роль (тест в задаче 1).
- Комментарий без разработчика: в шапке — «Комментарий», как ревью без разработчика (тест в задаче 2).
- Комментарий без `End date` или с датой в будущем: не в скорости и не на таймлайне, в разделе карточки — есть (тесты в задачах 1, 3).
- Ревью и комментарий одного разработчика в один день: две отдельные части столбика и две выборки по клику (браузерная проверка в задаче 3).
- `cvereview`: SecOps с «Ожидает комментарий» в пул не входит (тест в задаче 4).

---

### Task 1: роли и расчёты (`cvesummary`)

**Files:** Modify `cvesummary/assets/js/roles.js`, `cvesummary/assets/js/pace.js`; Test `tests/js/roles.test.js`, `tests/js/pace.test.js`, `tests/js/activity.test.js`

**Interfaces — Produces:** `roles.isComment(r): boolean`, `roles.isSubmitted(r): boolean` (= `isReview || isComment`); `isSpeedDone` и `pace.isClosed` используют `isSubmitted`.

- [ ] Тесты: `isComment` для «Ожидает комментарий» и `'  ОЖИДАЕТ  комментарий '`, `isOpen`/`isWorking` = true, `isReview` = false; `isSpeedDone` только с корректной `End date`; в `pace` и `activity` — копии существующих тестов ревью (`pace.test.js:338-380`, `activity.test.js:49`) со статусом комментария дают те же числа.
- [ ] Прогнать — падают (`node --test tests/js/*.test.js`).
- [ ] Реализовать, прогнать — зелёные.

### Task 2: сегменты, цвет, шапка, карточка (`cvesummary`)

**Files:** Modify `segments.js`, `render.js` (`roleColor`, `hero-state`, `renderPeople`), `drilldown.js:350`, `summary.css` (4 строки переменных); Test `tests/js/segments.test.js`

- [ ] Тесты: `segments.hero` — ключи `['done-dev','review','comment','work',…]`, комментарий ни в одном правом сегменте (дополнить тест `segments.test.js:132`); `segments.person`/`personCounts` — роль `comment` между `review` и `pause`, `work` её не включает.
- [ ] Прогнать — падают.
- [ ] Реализовать: сегмент `{key:'comment', label:'Комментарий', color:'--st-comment', group:'comment'}`; `names.comment = 'комментарий'`; раздел карточки `['comment','Ожидает комментарий', mine.filter(r => r.comment)]` с правилами часов ревью; `drilldown.js` выбирает участников раздела по `measureStatus` (`done`/`review`/`comment`).
- [ ] Прогнать — зелёные.

### Task 3: таймлайны и браузерная проверка (`cvesummary`)

**Files:** Modify `render.js` (`completionSeries`, узор в `stackChart`, легенды), `drilldown.js:246`, `summary.html:241`; Test `tests/browser/fixtures.py`, `tests/browser/charts.cjs`, `tests/browser/drilldown.cjs`

- [ ] `completionSeries` строит части для обоих статусов: ключи `'\u0003review:'+k` и `'\u0003comment:'+k`, `segment` = `'review'`/`'comment'`, `hatch` = `'dots'`/`'comment-dots'`; флаги `hasReview`/`hasComment`; узор комментария — пурпурная точка с белой обводкой.
- [ ] `drilldown.js` для `[data-chart-segment="comment"]` выбирает `roles.isComment`, заголовок «Ожидает комментарий · …».
- [ ] Фикстуры: комментарии с датой, без даты и с будущей датой; проверки: цвет сегмента шапки = `--st-comment`, клик по части с узором открывает только комментарии, легенда содержит «ожидает комментарий», раздел карточки.
- [ ] Отдельный прогон по фикстуре в Chromium (существующие браузерные скрипты на `develop` падают раньше новых проверок — сверить, что падение то же, а новые проверки пройти отдельным скриптом).

### Task 4: `cvereview`

**Files:** Modify `assets/js/csv.js:9`, `assets/js/app.js` (фильтр, подписи), `README.md`, `VERSION`, `CHANGELOG.md`, пересобрать `cvereview.html` (`python3 build.py`); Test `tests/csv.test.cjs`, `tests/review-regressions.cjs`

- [ ] Тест: `eligible` принимает «Ожидает комментарий» у разработчика и отвергает у SecOps; фильтр статусов содержит «Ожидает комментарий».
- [ ] Прогнать — падает; реализовать; `node --test tests/*.test.cjs` и `node tests/browser.cjs` — зелёные.
- [ ] Коммит `feat(cvereview): include awaiting-comment status in review pool`.

### Task 5: документация и версия `cvesummary`

- [ ] `README.md`: таблица ролей, правила скорости/темпа, полоса шапки, цвет, раздел карточки, таймлайны, версия 1.43.0; `__init__.py` → 1.43.0; `CHANGELOG.md` тулзы; корневой `CHANGELOG.md` `[Unreleased]`.
- [ ] Python- и JS-тесты, корневые проверки из `CLAUDE.md`.
- [ ] Коммит `feat(cvesummary): add awaiting-comment status`.
