# Production calendar implementation plan

> **For agentic workers:** Use superpowers:executing-plans. Steps use checkboxes.

**Goal:** Russian holidays and working-day transfers in all CVE working-day calculations.
**Architecture:** CLI loads validated XML with cache and bundled fallback; JSON embedded in report configures shared dates module before calculations.
**Tech Stack:** Python stdlib, vanilla JS, unittest, node:test, Playwright.
**Spec:** ../specs/2026-11-09-production-calendar-design.md

## Global constraints

Standalone HTML, no new dependencies, RU five-day calendar; shortened days count as full days.
Preserve observed work on nonworking days and existing pool/review/break rules.
Use feature branch in existing checkout, consistent with this session. Leave uncommitted for user release request.

## Review focus

- Network/cache errors never prevent report generation; no silent missing-year fallback.
- Invalid or truncated remote calendars never poison cache.
- Working Saturdays and holidays both affect forecasting and denominators.
- Observed holiday work, review completions and common-break resets remain intact.
- Old direct page.render callers and network-free tests remain supported.

## Task 1: Calendar source and embedding

- [x] Tests in tests/test_workcalendar.py: XML validation, RU holidays/transfers, fresh/stale/broken cache, bundled fallback, missing years, cache write failure, CLI embedding.
- [x] Watch tests fail, implement cvesummary/workcalendar.py and CLI integration; bundle source XML 2025–2027 with attribution.
- [x] Run Python suite without network.

## Task 2: Calculations and display

- [x] Tests in tests/js/calendar.test.js: Nov4 rate, holiday hours, working Saturday, forecast, five-day break threshold and common/personal priority.
- [x] Watch tests fail, add dates.setCalendar/isNonWorking/dayLabel and use across hours/activity/pace/render.
- [x] Add calendar coverage text, holiday background tooltip; preserve legacy weekday fallback.
- [x] Run all JS and relevant browser tests, add offline holiday browser case.

## Task 3: Documentation and review

- [x] Version 1.41.0, tool/root changelogs and README behavior/source/cache documentation.
- [x] Build November demo, inspect holiday shading and rates in browser; root checks.
- [x] Fresh whole-change review, address material findings and record verification.
