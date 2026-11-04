# Removed from epic implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with superpowers:test-driven-development.

**Goal:** Статус «Убрано из эпика» с расчётными ролями, отдельными
графитовыми сегментами и точными счётчиками/выборками.

**Architecture:** roles.js определяет isRemoved/isDone и дубликаты.
Общий segments.js задаёт визуальные разбиения для renderer и drilldown,
чтобы добавление первого сегмента не смещало выборки. Часы/прогноз
получают расчётную роль через существующие вызовы roles.

**Tech Stack:** Python 3.9+, vanilla JS, node:test, unittest, Playwright.

**Spec:** ../specs/2026-11-05-removed-from-epic-design.md, подтверждён
пользователем 2026-11-05 после проверки согласованности.

## Global Constraints

- SecOps с новым статусом закрыт независимо от дат; остальные закрыты
  только с распознанными Start/End, открытая задача со Start работает.
- Не исключать строки из отчёта; исключить их только из определения
  дубликатов. Без End нет датированного закрытия и вклада в скорость.
- Графит первым в шапке и личной полосе статусов; триаж в шапке сохранён.
- Семантический счётчик включает убранные, сегменты не пересекаются.
- Не добавлять зависимости; сохранить предыдущие изменения без коммита.

## Review Focus

- Только убранные строки, пустой разработчик, SecOps с разным регистром.
- Смешанные группы дубликатов и выбор представителя уникальной пары.
- Start без End, SecOps без дат, ошибочная дата, часы и перерывы.
- Составы серого/зелёного сегментов и «Готово8/из них2» совпадают с кликами.
- Смешанный графит (открытые/закрытые), триаж, resize, светлая/тёмная темы.

### Task 1: Roles and shared partitions

**Files:** Modify assets/js/roles.js; create assets/js/segments.js;
test tests/js/roles.test.js, segments.test.js, activity.test.js.

**Interfaces:** roles.isRemoved(row): boolean; roles.isDone(row): boolean;
segments.hero(rowsWithReasons), segments.person(rows): arrays of
{key,label,color,group,rows}; segments.groups(parts): array of
{key,label,rows}; segments.uniqueRows(rows, duplicates): representatives.

- [x] Add role/duplicate/hour/forecast and disjoint-partition tests; observe failure.
- [x] Implement predicates and partitions; verify focused and full JS suites.

### Task 2: UI and drilldown

**Files:** Modify page.py, render.js, drilldown.js, summary.css;
create tests/browser/removed.cjs and removed_fixtures.py.

- [x] Add browser cases for the agreed ten-task example, mixed roles,
  only-removed data, no-removed regression, exact lists and AI counts.
- [x] Watch old renderer fail; add graphite parts, role-counter subsets,
  shared keyed bindings, color contrast and keyboard/list support.
- [x] Run Python/JS and all browser suites, inspect both theme screenshots.

### Task 3: Documentation and review

- [x] Bump1.26.0, update README and changelogs with role table and exceptions.
- [x] Fresh read-only review; fix confirmed issues with regression tests.
- [x] Verify final diff, update demo and leave changes uncommitted.

## Verification record

145 Node tests, 88 Python tests. Browser suites: drilldown 193, charts 24,
activity 15, speed 6, removed 5 scenarios with exact membership assertions.
Fresh independent review identified malformed End on removed SecOps as
an invented dated event; regression observed RED in rates and browser,
then GREEN after roles.endOf was applied consistently to dated consumers.
No deferred findings. Existing ordinary-status date validation is unchanged.
Demo: .tmp/cvesummary-personal-preview-bu1yid_y/removed.html (workspace only).
Changes remain uncommitted in feature/cvesummary-personal-breaks.
