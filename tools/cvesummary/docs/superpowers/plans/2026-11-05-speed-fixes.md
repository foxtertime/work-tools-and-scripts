# Speed correctness fixes implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task with superpowers:test-driven-development.

**Goal:** Исправить BUG-2611-04, BUG-2611-05, BUG-2610-14 и по уточнению
пользователя установить единый порог перерывов пять рабочих дней.

**Architecture:** rates сохраняет реальное пустое пересечение и явно
возвращает знаменатель темпа/календарную основу при отсутствии будней.
Интерфейс различает ноль и неизвестность; план хранит только явные
ручные настройки, а автоматические значения пересчитывает по данным.

**Tech Stack:** vanilla JS, Python 3.9+, node:test, unittest, Playwright.

**Spec:** Авторизованные пункты TODO и уточнение пользователя 2026-11-05:
общие и личные перерывы после пяти рабочих дней, остальные правила
сохраняются из ../specs/2026-11-05-personal-breaks-design.md.

## Global Constraints

- Сохранить незакоммиченные изменения предыдущих задач и остальные TODO.
- Не устанавливать зависимости, не менять формат исходной таблицы.
- Выходные без будней: закрытия / календарные дни вне общих перерывов,
  с явной подписью единицы. Полный перерыв не превращать в рабочий период.
- Пустое окно не подменять одним днём; показатели и прогноз неизвестны,
  текущий остаток сохраняется. Нулевая скорость при известном периоде — 0.
- Ручные поля плана сохранять независимо; очистка возвращает поле к авто,
  кнопка возвращает оба поля к текущим данным. Старое хранилище, смешивавшее
  авто и ручные значения, не использовать как доказательство ручного ввода.

## Review Focus

- Четыре/пять дней личного простоя, совпадение с общим порогом.
- Выходные, полные перерывы, нулевые закрытия и настоящее пустое окно.
- Пересчёт авто при смене дат, ручное поле + авто поле, reload и resize.
- Пустое окно в карточках, сценариях, фактическом и плановом прогнозе.

### Task 1: Pure calculations

- [x] Add failing tests for five-day threshold, weekend basis, empty window.
- [x] Fix rates and shared break threshold; run focused and all JS tests.

### Task 2: Rendering and plan state

- [x] Add failing browser tests for all three bugs and manual persistence.
- [x] Integrate clear zero/empty/calendar display and manual-only plan state.
- [x] Run Python/JS plus all browser suites; independently review changes.

### Task 3: Finish

- [x] Update docs/version/changelogs and remove the three completed TODOs.
- [x] Verify diff and keep changes uncommitted in the current feature branch.
