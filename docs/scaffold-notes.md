# Copied scaffold in opportunity-scholarship-data

The sibling `opportunity-*-data` repositories (book-*-data products) each carry a copy of
the same scaffold. The owner decided on 2026-10-21 that services keep their own code (no
shared package), so the copies stay, and every change to one is applied to all of them in
the same wave.

| File | Rule |
|---|---|
| `src/book_scholarship_data/cli.py` | Vendored contract CLI, SHA-256 pinned per variant in `tests/test_shared_cli.py` |
| `tests/test_shared_cli.py` | Byte-identical in every sibling (holds the pins) |
| `src/book_scholarship_data/observability.py` | Byte-identical in every sibling: opt-in Sentry for capture runs |
| `tests/test_capture_job.py` | Byte-identical in every sibling: a failed capture reaches Sentry, nothing is sent without a DSN |
| `pyproject.toml` `[tool.mypy]` / dev + sentry extras | Same settings in every sibling; only the package name differs |
| `.github/workflows/ci.yml` | Shared CI v1.1.1 (`87dc5e1`); only the CLI smoke lines and coverage threshold differ |

`capture.py` is **not** shared: each product owns its source adapters.

## Wave b-data (2026-10-22)

Applied to every sibling: `uv.lock` (CI installs with `uv sync --frozen --all-extras`),
mypy in gradual mode with strict settings on `observability.py`, the opt-in Sentry module and
its test, the two `test_shared_cli.py` type fixes (no behaviour change), CI v1.0.1 → v1.1.1
with a coverage gate. Red first: `tests/test_capture_job.py::test_failed_capture_reaches_sentry` failed on the old `capture.main` (no event for exit code 2).
