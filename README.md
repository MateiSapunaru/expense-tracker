# Expense Tracker — QA Automation Portfolio (Project B)

A Python-native expense tracker (FastAPI + Jinja2 + PostgreSQL) built as the target
application for a layered test automation suite: Selenium (UI), Schemathesis (API
schema/contract), and Locust (performance). This is one of two portfolio projects
deliberately built with different tooling than its counterpart (Node/React +
Playwright + Pact) to demonstrate range across the two dominant stacks in test
automation.

## Stack

- **Backend**: FastAPI
- **DB**: PostgreSQL, accessed via SQLAlchemy
- **Frontend**: FastAPI + Jinja2 server-rendered templates (kept simple — functionality over polish)
- **UI testing**: Selenium (Python), Page Object Model, explicit waits
- **API testing**: pytest + Schemathesis (property-based testing against the auto-generated OpenAPI spec)
- **Performance testing**: Locust
- **CI/CD**: GitHub Actions, parallel jobs (UI / API-schema / perf smoke)
- **Containerization**: Docker + docker-compose (app + Postgres)

## Design decisions

This section is a running log of non-obvious choices and why they were made —
written as we go, not reconstructed after the fact.

- **src-layout (`src/app/`) over flat layout.** Prevents Python from silently
  resolving `import app` to an uninstalled local directory — the package only
  becomes importable once it's actually installed (`pip install -e .`), so tests
  exercise the real installed package rather than whatever happens to be in the
  working directory. This matters more for library packaging than for a plain
  web app, but it's cheap to set up correctly and is the layout the Python
  Packaging Authority recommends.
- **pyproject.toml (PEP 621) + hatchling, no requirements.txt.** Hatchling was
  chosen over Poetry because it needs almost no configuration for a single
  src-layout package and doesn't introduce a separate lockfile/tooling layer
  that would be hard to justify for a project this size.
- **psycopg2-binary over psycopg3.** psycopg2 is still the more widely used,
  more commonly documented sync driver for SQLAlchemy + Postgres; chosen for
  familiarity and interview-defensibility over the newer psycopg3.
- **No Alembic (yet).** Schema is created via `Base.metadata.create_all()` on
  startup instead of migrations. This is a scoping call for a 2-day project,
  not an oversight — Alembic would be the natural next step for a
  production-grade version.
- **`amount` is `Numeric(10, 2)`, not `Float`.** Floats use binary
  floating-point and accumulate rounding error on money (e.g. `0.1 + 0.2 !=
  0.3`); `Numeric`/`Decimal` is exact base-10 arithmetic, which is the
  standard choice for currency values.
- **`category` is a fixed Python `Enum`, not a free-text string.** Rejects
  invalid categories at the API boundary (FastAPI returns `422` automatically)
  instead of letting arbitrary strings accumulate in the DB. Trade-off: adding
  a category means a code change, not just new data — acceptable here since
  the category set is small and stable.

## Findings from Schemathesis (Day 1)

[tests/api/test_schema.py](tests/api/test_schema.py) runs Schemathesis's
property-based fuzzing against the app's own auto-generated OpenAPI spec,
in-process via `schemathesis.openapi.from_asgi` (no separate server process
needed). Within a handful of runs it surfaced real issues — this is the
actual value of schema/contract testing over hand-written example tests: it
finds the inputs you didn't think to write a test for. Each finding below was
triaged individually rather than blindly "fixed to make the fuzzer pass":

| Finding | Verdict | Resolution |
|---|---|---|
| `OPTIONS /api/expenses` returns a `405` whose `Allow` header omits `GET` | Framework quirk — Starlette computes `Allow` per matched route, not per path, when multiple methods share a path | Excluded the `allow_header_conformance` check (documented inline) |
| Undeclared query params (e.g. `?x=1`) are silently accepted instead of rejected | Accepted design trade-off — FastAPI's default permissive/forward-compatible behavior; the alternative (strict rejection) trades away tolerance for unrecognized-but-harmless params | Excluded the `negative_data_rejection` check (documented inline) |
| `amount`'s `decimal_places=2` constraint has no OpenAPI equivalent, so a schema-"valid" value with 3+ decimal places got rejected | Real schema/implementation mismatch | Added `multipleOf: 0.01` to the schema; tightened the lower bound from `gt=0` to `ge=0.01` (the actual business minimum) to remove a floating-point boundary edge case at `multipleOf ∩ exclusiveMinimum≈0` |
| `amount` had no upper bound — a large value passed validation but crashed at the DB layer (`NumericValueOutOfRange`) as an unhandled `500` | **Real bug** | Added `le=99999999.99`, matching the `Numeric(10, 2)` column exactly |
| Pydantic's JSON schema for `Decimal` is `anyOf[number, string]`; only the `number` branch carried the min/max, so an oversized *string* value still validated as "positive" data | Schema-generation quirk in how Pydantic represents `Decimal` | Overrode `json_schema_extra` to pin the schema to a single `number` representation; added a JSON-mode `field_serializer` so the actual response now emits a number too (previously Pydantic serialized `Decimal` as a string by default, which would have contradicted the corrected schema) |
| `skip` had no upper bound — a value beyond Postgres's `bigint` range crashed the `OFFSET` clause as an unhandled `500` | **Real bug** | Added `le=1_000_000` |
| A malformed (non-JSON) request body returns Starlette's own `400`, which FastAPI never auto-documents (it only adds `422` for validation failures on an already-parsed body) | Documentation gap | Declared `400` explicitly via the route's `responses=` |
| A NUL byte (`\u0000`) in `description` passed length/type validation but crashed the Postgres driver (`ValueError: string literal cannot contain NUL`) | **Real bug** | Replaced with a `pattern` constraint (`^[^\x00]*$`) instead of a bespoke validator, so the exclusion is both enforced *and* documented — Schemathesis then stops treating our rejection of it as a contract violation |

Net effect: three genuine crash bugs (missing upper bounds letting bad input
reach the DB) caught before ever writing a Selenium or Locust test, plus two
schema-accuracy fixes and two documented judgment calls about what *not* to
"fix". The two excluded checks are deliberate, not swept under the rug —
excluding a check without justification would be worse than not running
Schemathesis at all.

## Running locally

```bash
docker compose up --build
```

Then check `http://localhost:8000/health` — it should return `{"status": "ok"}`
once the app has connected to Postgres.

## Status

Day 1, step 3: `Expense` model + `POST/GET /api/expenses` (paginated),
Schemathesis contract suite passing (see findings above) and stable across
repeated runs. Jinja2 frontend and CI still to come.
