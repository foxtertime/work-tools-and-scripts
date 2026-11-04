# Personal developer breaks implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Скорость за активные периоды, личная штриховка и прогноз по активной команде.

**Architecture:** Чистый activity.js получает строки и результат hours.compute,
строит личные/общие перерывы и статистику окна. render.js использует его
для личных карточек и мощности будущего, сохраняя исторический общий темп.

**Tech Stack:** Python 3.9+, vanilla JS, node:test, unittest, Playwright.

**Spec:** ../specs/2026-11-05-personal-breaks-design.md

## Global Constraints

- Без зависимостей и сборщика; HTML автономный, тулза самодостаточна.
- Общий и личный порог 5 рабочих дней (уточнение пользователя); SecOps не входит в мощность команды.
- Перерывы по начатым задачам, не по закрытиям; выбор окна их не меняет.
- Только BUG-2611-03/FEAT-2611-01; остальные изменения TODO сохраняются.

## Review Focus

- Граница четырёх/пяти рабочих дней, включая выходные и хвост до даты отчёта.
- Открытая долгая задача и отсутствие начатых задач за всю историю.
- Узкое окно внутри перерыва, пересечения общих и личных перерывов.
- Несколько периодов и выпадение/возвращение участника в общем прогнозе.
- Личная штриховка не попадает на чужие/общие графики, тема и resize работают.

### Task 1: Activity calculations

**Files:** Create assets/js/activity.js, tests/js/activity.test.js; modify assets/js/pace.js.

**Interfaces:** activity.compute(rows, asOf, hoursResult) returns since, breaks,
people Map. activity.stats(person, from, to, commonBreaks) returns closed,
work, cut, rate. activity.team(state, from, to) returns outR, active, total.

- [x] Write tests for every calculation and boundary from Review Focus.
- [x] Run node --test tests/js/activity.test.js; expect missing module failure.
- [x] Implement module and optional threshold for pace.breaks (default remains 5).
- [x] Run activity tests and complete JS suite; expect all pass.

### Task 2: Rendering and forecast integration

**Files:** Modify page.py, assets/js/render.js, assets/summary.css;
create tests/browser/activity.cjs with its own temporary fixtures.

- [x] Write browser assertions for speeds, no-work windows, chart isolation,
  distinct patterns, team capacity, re-entry, weekends, dark theme and resize.
- [x] Run browser check against old renderer; expect incorrect speed/pattern.
- [x] Integrate activity module, cards, own hatch, legends and forecast capacity.
- [x] Run all Python/JS and all three browser checks; expect all pass.

### Task 3: Documentation and final review

**Files:** Modify README, tool/root CHANGELOG, __init__.py, TODO.

- [x] Describe semantics and capacity, bump 1.25.0, remove two completed tasks.
- [x] Review complete diff with a fresh reviewer and resolve confirmed issues.
- [x] Check git diff --check, recorded test evidence and final file scope.

## Execution decisions

Work in feature/cvesummary-personal-breaks in the current checkout so earlier
review edits remain present and reviewable. No dependency setup required.
Leave changes uncommitted for review; no merges, pushes or releases.
