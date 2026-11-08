# Break Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Apply common-break priority and place vertical labels on the first day of every break.
**Architecture:** Compute common breaks first. Calculate personal breaks independently inside the intervals outside common breaks, reusing `pace.breaks`; use the shared `breakHatch` renderer for every timeline.
**Tech Stack:** Python 3.9+ stdlib, vanilla JavaScript, SVG, Node tests, Chromium checks.
**Spec:** [Break priority](../specs/2026-11-09-break-priority-design.md).

## Global Constraints

Keep pool, hours and completion rules. Preserve the pending personal review-measures change.
Personal idle threshold remains five weekdays; new qualifying idle intervals are retrospective.

## Review Focus

- Fewer than five idle weekdays before a common break must remain counted days.
- Four versus five weekdays after a common break must change rate and forecast participation.
- Multiple common breaks reset independently; people without Start date follow the same rule.
- No common break retains prior personal-break behavior; SecOps does not define team activity.
- Narrow weekly and forecast plots still show labels at the start; labels do not intercept clicks.

### Task 1: Common-break priority in calculations

Files: `cvesummary/assets/js/activity.js`, `tests/js/activity.test.js`.
Interface: preserve `activity.compute(rows, asOf, hours)` and `stats` / `team` results.

- [x] Add and run failing tests for existing-personal → common → new idle,
  short fragments, multiple common periods, no Start date, and common-only periods.
  Assert exact inclusive dates, cut/work/closed counts and current membership.
- [x] Compute common breaks before personal ones; call the existing break detector
  separately between common intervals, with the existing empty-days fallback.
- [x] Run `node --test tests/js/activity.test.js tests/js/pace.test.js` and inspect results.

### Task 2: First-day vertical labels and end-to-end checks

Files: `cvesummary/assets/js/render.js`, `cvesummary/assets/summary.css`,
`tests/browser/activity_fixtures.py`, `tests/browser/activity.cjs`.

- [x] Add failing browser checks for disjoint common/personal ranges, the new
  countdown in displayed speed/forecast, and label geometry in day/week,
  flow/burn-up/burn-down, desktop/mobile and light/dark views.
- [x] Remove the minimum-width condition; rotate labels −90° at the centre
  of the first visible day and the vertical centre of the plot.
- [x] Verify browser activity checks, then all Python, JS and browser suites.
- [x] Update README, tool/root changelogs and tool version to 1.40.0.
- [x] Rebuild an example showing personal → common → short idle/new personal,
  inspect screenshots, and open it in the desktop browser.
- [x] Review the combined pending change; leave release integration for the user's release request.
