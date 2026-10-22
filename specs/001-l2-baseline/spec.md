---
id: SPEC-001
title: L2 baseline for opportunity-scholarship-data
status: in review
created: 2026-10-22
owner: bookchaowalit
---

# SPEC-001: L2 baseline

## Document control

| Field | Value |
|---|---|
| Main-only | yes (ADR-0004 v1.1: red run is local, red and green commits pushed together) |
| Maker | Claude session b-data (2026-10-22) |
| Checker / approver | pending (owner) |

## Problem

The Big Loop scorecard (2026-10-22) had this repo at L0: no lockfile, no type check and no
error reporting. A capture run that fails exits 2 through the shared runtime, which only
prints a generic line, so a failing scheduled capture is invisible.

## Behaviour

1. Dependencies resolve from the committed `uv.lock`; CI installs with `uv sync --frozen`.
2. `mypy` runs in CI over `src/` and `tests/` (gradual; strict on `observability.py`).
3. When `SENTRY_DSN` is set and the `sentry` extra is installed, a capture run that exits
   non-zero sends exactly one Sentry event (`level=error`, tag `source_id`, the exit code).
   A run that succeeds sends nothing. Without a DSN, Sentry is never imported or initialised.
   `send_default_pii` is false and no payload or source body is attached.
4. CI fails when total coverage drops below 87%.

## Acceptance

| AC | Given / When / Then | Test |
|---|---|---|
| AC-01 | Given `SENTRY_DSN` is set, when the runtime returns exit code 2, then one `error` event tagged `source_id` is sent and the exit code is unchanged | `tests/test_capture_job.py::test_failed_capture_reaches_sentry` |
| AC-02 | Given `SENTRY_DSN` is set, when the run succeeds, then no event is sent | `test_successful_capture_sends_nothing` |
| AC-03 | Given no `SENTRY_DSN`, when a run fails, then Sentry is not initialised | `test_without_dsn_sentry_stays_off` |
| AC-04 | CI on `main` is green on Python 3.10 and 3.13 with the coverage gate | CI run below |

## Red/green log

| AC | Red (sha · command · failure) | Green |
|---|---|---|
| AC-01, AC-02 | `72952ad` · `python -m pytest -q tests/test_capture_job.py` · `AssertionError: 0 != 1` | `GREEN_CI` |

## Schedule (no change in this spec)

Owner decision D6 (which host runs schedules) is open, so no scheduler is touched. Today the
capture is invoked by data-lake-pipelines' discovery portfolio, registered as a 6-hourly
Windows task. Planned replacement once D6 is decided: one hosted scheduled job per portfolio
(not per product) that runs `portfolio.py acquire` against the chosen lake target with
`SENTRY_DSN` set, so each failed source shows up as a Sentry event from this module. The
schedule change belongs in data-lake-pipelines, not here.

## Out of scope

Live source captures, lake writes to R2, new sources, and the drift-marker backlog in
`docs/UPGRADE-PLAN.md`.
