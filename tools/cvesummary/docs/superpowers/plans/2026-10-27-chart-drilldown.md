# Chart Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Открывать исходные задачи по столбикам поступления и закрытий.

**Architecture:** render.js помечает период столбика; drilldown.js связывает
его с кешированными группами исходных строк. Существующий pointer capture
в timeline.js отделяет перетаскивание от клика; окно обслуживает все выборки.

**Tech Stack:** Vanilla JavaScript, SVG, Python unittest, node:test, Playwright.

**Spec:** ../specs/2026-10-27-chart-drilldown-design.md

## Global Constraints

- Автономный HTML, без новых зависимостей.
- Исходники и документация остаются внутри tools/cvesummary.
- Выборка соответствует всему столбику, включая все цвета.
- Даты позже даты отчёта не включаются; строки не дедуплицируются.

## Review Focus

Проверки задачи покрывают границы недели, последнюю неполную неделю,
одинаковые даты разных разработчиков, пустые периоды, будущие/плохие даты,
«Других», клавиатуру, resize, повторную отрисовку, прокрутку мышью и касание.

### Task 1: Clickable timeline periods

**Files:**
- Modify: cvesummary/assets/js/render.js — метаданные периода SVG.
- Modify: cvesummary/assets/js/drilldown.js — индексы дат и привязка окна.
- Inspect: cvesummary/assets/js/timeline.js — существующая защита drag.
- Modify: cvesummary/assets/summary.css — курсоры/фокус интерактивных графиков.
- Test: tests/browser/charts.cjs, tests/browser/fixtures.py — реальные клики
  по фиксированным данным, границы и взаимодействия.
- Modify: README.md, CHANGELOG.md, cvesummary/__init__.py,
  ../../CHANGELOG.md — документация и версия 1.23.0.

**Interfaces:**
- Consumes: stackChart(host, periods, cats, what, byDay, opts),
  drilldown.mount(CS), timeline.attach(box).
- Produces: host.dataset.chartDays (1/7), column.dataset.chartDay (UTC day).
  Привязки используют существующие bind/open и MutationObserver.

- [x] Добавить фиксированную браузерную таблицу и проверки списков за
      день/неделю, личных графиков, пустых периодов и границ даты отчёта.
- [x] Запустить charts.cjs: ожидается отсутствие открытия окна на текущем коде.
- [x] Добавить числовые метаданные периода, кеш групп строк и привязки SVG;
      сохранить события только на общем столбике, не на цветных сегментах.
- [x] Проверить drag, клавиатуру, фокус, касание и обновление после resize
      и смены дня/недели; менять timeline.attach только при провале drag-проверки.
- [x] Обновить версию и документацию. Выполнить Python, JS, обе браузерные
      проверки и корневые проверки. Ожидается успешный выход всех команд.
- [x] Провести независимое ревью, исправить существенные находки;
      оставить результат в feature-ветке для пользователя.

Проверки: RED — charts.cjs не дождался открытия окна после клика;
GREEN — 88 Python, 112 JS, 189 проверок существующего окна и 24 проверки
графиков, без ошибок страницы. Корневые проверки и git diff --check прошли.
Изменения timeline.js не понадобились: существующий pointer capture
сохраняет прокрутку и предотвращает открытие окна при drag.
Независимое ревью: существенных и малых замечаний нет. Существующая
нормализация некорректных календарных дат остаётся в ранее заведённом
техническом долге; выборки используют те же даты, что графики. Прогнозные
графики и посторонние локальные артефакты вне области этой задачи.
