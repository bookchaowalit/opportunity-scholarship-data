# book-scholarship-data

Find education funding by degree and applicant eligibility.

Status: **local source pilot**. Original v1 demo/validation remains available.
The live lane uses v2 to distinguish unknown domain terms from false and program
directories from actual awards. Five reviewed official sources are enabled for
explicit manual acquisition; no scheduler, remote deployment or application submission.

## Users and boundary

For people and small teams discovering scholarships.
Degree and tuition awards; research project budgets belong to grant.

Subcategories: undergraduate, postgraduate, vocational, short-course, tuition-waiver.

Domain-specific terms: `study_level`, `funding_coverage`, `institution`, `service_obligation`.
Each record represents one program/offer intake window. A repeat intake receives
a distinct source record ID. Cross-domain packages use `related_records` rather
than copying the same award into several products.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
book-scholarship-data contract              # v1 (demo)
book-scholarship-data contract --version v2 # v2 (captured records)
book-scholarship-data demo --open-only
book-scholarship-data demo --query "undergraduate"
book-scholarship-data validate src/book_scholarship_data/demo.json
python -m unittest discover -s tests -v
```

Developer checks (the same commands CI runs in `.github/workflows/ci.yml` on
Python 3.10 and 3.12, plus a `contract`/`validate`/`demo` CLI smoke):

```bash
python -m pip install -e ".[dev]"
ruff check .
python -m pytest -q
```

All tests are offline: source adapters are exercised with inline fixtures, the
capture entry point is only checked for its fail-closed guard, and no test needs
the shared data-lake runtime or network access. `tests/test_policy.py` keeps
`sources.json`, every `source*.json` policy and the bundled schema consistent.

With dependencies already available, use `PYTHONPATH=src python3 -m book_scholarship_data`.
`demo` uses the fixed synthetic clock 2026-09-07T00:00:00Z unless `--as-of` is
provided. `--open-only` excludes closed, unknown-deadline, expired, stale (72h
default), and future-checked records. This is an availability filter; it does
not assert personal eligibility, selection probability, or a guaranteed payout.

Contracts: `src/book_scholarship_data/schema.json` (`scholarship.v1`, synthetic demo)
and `src/book_scholarship_data/schema-v2.json` (`scholarship.v2`, captured sources).
`validate` selects the schema from the envelope's `schema_version`; `contract` prints v1 by default and v2 with `--version v2`.
Unknown amounts, currencies, eligibility and deadlines remain unknown. Cash,
credit, discount, in-kind benefits and access are different value kinds. Never
sum them as cash income. Queries and validation are read-only and do not persist
provided files. The `live` label requires captured lineage, but validation alone
does not verify that referenced lake objects exist or prove source truth.

## Data ownership and source policy

Owner: bookchaowalit. Public program metadata only; no applications, personal
screening answers, financial credentials, cookies, or private transcripts.
See `sources.json` and the source policy below. Select official API/export, then feed,
then bounded permitted scraping. Exact source permission and retention must be
reviewed before network ingestion. No spending, account creation or messaging.

Implemented capture flow: approved source pull → immutable landing bytes
and checksum → Bronze Parquet and manifest through the shared lake runtime →
versioned read-only contract → consumer pull. Each product owns its source
adapters and lake prefix. Producers never write into another app's database,
CRM, tasks, application tracker, or notification system.

## Remaining implementation gates

1. Keep the five source adapters fresh and add parser fixtures when a provider changes its public contract.
2. Expand domain field extraction and live quality monitoring.
3. Package the local shared capture runtime for independent deployment.
   Current source capture and replay use the explicit data-lake runtime.
4. Add live source tests, retention/access controls and runtime monitoring.
5. Connect a read-only consumer. Personal eligibility, ranking, deadlines and
   application workflow belong to consumers with separate private storage.

No runtime port is reserved. The former `opportunity.v1` is archival; `job.v1` remains a separate job-data contract.
Breaking contract changes require a new version and a consumer migration.
There is no production deployment to roll back; discard demo output or restore
the previous contract version locally. Source permission, live availability,
real eligibility and production operations are **unverified**, not passing gates.

## Official source pilots

Source: [Chevening / FCDO](https://www.chevening.org/scholarship/thailand/). Access policy/evidence: [https://www.chevening.org/robots.txt](https://www.chevening.org/robots.txt).
The exact source configurations live in `src/book_scholarship_data/source*.json`;
the enabled IDs and capture status are recorded in `sources.json`.
GitHub documentation attribution: GitHub, CC BY 4.0 (docs repository license).
GOV.UK content attribution: Crown copyright, Open Government Licence v3.0.
Chevening attribution: Chevening/FCDO. Only private source archival and bounded
program metadata extraction; no public mirror of the source body.

Run from this repo with the existing data-lake Python environment:

```bash
export SOLO_DATA_LAKE_ROOT=/path/to/solo-data-lake
PYTHONPATH=src "$SOLO_DATA_LAKE_ROOT/.venv/bin/python" -m book_scholarship_data.capture acquire --lake "$PWD/data/lake" --state-dir "$PWD/data/control"
PYTHONPATH=src "$SOLO_DATA_LAKE_ROOT/.venv/bin/python" -m book_scholarship_data.capture records --lake "$PWD/data/lake" --state-dir "$PWD/data/control"
```

This lane depends on the explicit local shared `discovery.capture_runtime` v1
and existing `data_lake.product_adapter`. No parent-path auto-discovery, cloud
target, credentials or environment-selected lake is used. It is not a standalone
deployed ingestion package yet. The pure v1/v2 contract CLI remains standalone.

Capture preserves exact bytes, a Bronze document-metadata row and manifest before
domain parsing. Records are replayed from checksum-verified landing and Bronze
objects. The per-source control state records a fresh check even when unchanged
bytes reuse an existing immutable batch. Failed latest fetches fail closed;
parser failures leave a quarantined capture reference and no synthetic fallback.

There are at most two source GET attempts (15-second timeout each), a 2 MB
response cap and a six-hour cooldown under a local file lock. HTML sources
recheck robots.txt; API sources use their documented public API and license.
429/auth failures are not retried. Redirects need explicit policy review.
Sensitive session-token markers are refused before archive; the GitHub live lane
therefore reads licensed Markdown through the public Contents API, not pack HTML.

The grant pilot is a **funding directory**, not a claim of an open award.
Missing deadlines, fees, selection guarantees and domain terms remain unknown.
`records` reports the captured check time; callers must apply their freshness
window. No personal eligibility decision is inferred from country or page title.
Retention is operational in a private local archive; cleanup is manual under the
repository data lifecycle policy. No automatic deletion or source republication.

## Development

```bash
uv sync --frozen --all-extras && uv run mypy  # locked env (uv.lock) as CI installs it
uv run pytest -q --cov
```
