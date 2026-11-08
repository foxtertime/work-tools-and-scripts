# Removed tasks outside the epic pool

> **For agentic workers:** Use superpowers:executing-plans for inline execution.

**Goal:** Exclude removed tasks everywhere except the explicit removed counter/block and completed developer work in throughput.

**Architecture:** Split source rows once into the epic pool, removed rows and speed history. All general rendering, hours, charts and drilldowns use the pool. Speed history adds only removed tasks completed by a named non-SecOps developer with valid, ordered Start/End dates no later than the report date. Keep raw rows in the report for the explicit removed lists.

**Tech Stack:** Existing Python HTML assembler, vanilla JavaScript, unittest, node:test and Playwright.

**Spec:** User clarification on 2026-11-08 supersedes the earlier removed-from-epic design wherever it retained removed rows in general totals, workload or cuts.

## Global constraints

- Preserve the removed counter below the hero bar and the dedicated removed block, including their exact task lists.
- Remove these rows from unique pairs, components, severity, measures, RHEL/status, AI/remediation, incoming flow, backlog, anomalies, assignments, load, hours and ordinary charts/exports.
- Exclude removed unfinished work and removed SecOps from speed and its working days/breaks.
- Include completed removed developer work in task/day rates and forecast capacity, without adding its incoming/closing events to the epic backlog balance.
- Keep existing behavior for ordinary rows and preserve the earlier UI edits in this working tree.

## Review focus

- All-removed and empty inputs: zero pool totals, preserved removed lists, no phantom backlog or SecOps throughput.
- Removed-only unique pairs and newer removed AI verdicts must not appear in pool counts or override active pair representatives.
- Invalid, reversed, future or incomplete removed dates must not contribute workdays or closures.
- Overlapping removed work must not dilute pool task hours; unfinished removed work must not prevent a break.
- Exact selections must remain correct after resizing, including source row identifiers and duplicate links.

### Task 1: Scope and throughput

Files: new `cvesummary/assets/js/scope.js`, `cvesummary/page.py`, `cvesummary/assets/js/pace.js`, new `tests/js/scope.test.js`, `tests/js/pace.test.js`.

- [x] Add failing tests for scope membership, dates, nonmutation, pool hours and speed-only completed history.
- [x] Add `scope.split(rows, asOf) -> {pool, removed, speed}` and register it after roles/dates.
- [x] Extend rates/scenarios with an optional speed-history input; incoming/open/closedTotal remain based on pool rows.
- [x] Run `node --test tests/js/scope.test.js tests/js/pace.test.js`; expect zero failures.

### Task 2: Report and exact selections

Files: `render.js`, `drilldown.js`, `tests/browser/removed.cjs`, `tests/browser/removed_fixtures.py`, `tests/browser/drilldown.cjs`.

- [x] Add browser assertions covering all excluded sections, speed, mixed/all-removed data, and exact source-row lists.
- [x] Use pool data by default; route only the explicit removed views to removed data, and rates/activity to speed history.
- [x] Keep pool workload and hours separate from workdays used for throughput. Show speed-only developers with zero pool assignments.
- [x] Run removed and general drilldown browser suites; expect zero page errors and no mismatched counts.

### Task 3: Documentation and preview

- [x] Update README to the clarified policy.
- [x] Run Python and JS suites, relevant browser suites, and `git diff --check`.
- [x] Rebuild the existing 120-row example and verify 100 pool tasks, 20 removed, and excluded removed-only rows across the UI.
- [x] Review the change and open the updated example in a visible desktop Chrome window.

## Verification record

- Python: 88 tests passed. JavaScript: 149 tests passed.
- Browser: removed 11 checks; drilldown 195 checks (157 numeric counters); speed 6; charts 24. All completed without page errors. One initial removed-suite navigation exceeded its 4-second timeout; an unchanged sequential rerun passed.
- Independent read-only review: no actionable defects; 57 additional targeted tests passed.
- No commits or branch changes made; earlier session edits are preserved.
