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
- **Jinja2 pages reuse `crud.py` directly, not an internal HTTP call to the
  JSON API.** Both are the same process — the JSON API and the HTML pages
  are two presentation layers over identical business logic, so there's no
  reason to round-trip through HTTP to talk to itself.
- **Page routes are `include_in_schema=False`.** Without this they'd be
  pulled into the OpenAPI spec and Schemathesis would start fuzzing HTML
  form endpoints as if they were part of the JSON contract. The page routes
  are covered by Selenium instead; Schemathesis owns the JSON API only.
- **Create form uses Post/Redirect/Get (303 on success).** Prevents a page
  refresh after submitting from re-submitting the same expense.

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

## Selenium UI suite

[tests/ui/](tests/ui/) drives the Jinja2 pages through a real browser —
the layer Schemathesis deliberately doesn't touch (page routes are
`include_in_schema=False`, see above). Structured as Page Object Model:
`tests/ui/pages/base_page.py` holds the driver, a shared explicit wait, and
navigation via the nav bar common to every page; `expense_list_page.py` and
`expense_form_page.py` each model one page's locators and actions.

A few decisions worth being able to defend:

- **Selenium Manager, no `webdriver-manager`.** Selenium ≥4.6 auto-resolves
  the matching chromedriver itself. `webdriver-manager` solved a problem
  that no longer exists as a separate dependency.
- **Test data is seeded by talking to the DB directly** (via the app's own
  `crud.py`/`SessionLocal`), the same pattern `tests/api/conftest.py` already
  uses, rather than seeding through the JSON API over HTTP. Faster, and
  keeps the UI suite from having a hard dependency on the API layer being
  up — the trade-off is it's not a *fully* black-box suite, which is a fair
  thing to be asked about.
- **The suite talks to a real running `uvicorn` process**, unlike
  Schemathesis's in-process ASGI trick — a browser can't drive an app that
  isn't actually listening on a port. Locally that's `docker compose up`;
  CI starts `uvicorn` as a background step (see CI below).
- **`amount=0` is submitted by calling the `<form>` element's native
  `submit()` via JS**, not by clicking the Save button. Per the HTML spec,
  a direct `.submit()` call skips the browser's own constraint validation
  (`min="0.01"` on the input), unlike a real click. That's the point: any
  non-browser client (curl, a hand-crafted request) skips the same
  client-side checks, so this is how the suite proves the server enforces
  the `ge=0.01` minimum on its own rather than relying on the page's HTML
  attributes to keep bad data out.
- **Date fields are set via `element.value = ...` + a dispatched `input`/
  `change` event**, not `send_keys`. A native `<input type="date">` expects
  locale-formatted keystrokes (e.g. `MM/DD/YYYY` on en-US Chrome), which is
  a well-documented source of Selenium flakiness across environments.

## Locust load test (smoke)

[tests/perf/locustfile.py](tests/perf/locustfile.py) load-tests the two
hottest JSON endpoints — `GET /api/expenses` (list, paginated) and
`POST /api/expenses` (create) — weighted 3:1 read:write to approximate real
usage (most requests browse the list; far fewer add an expense). It's a
smoke test, not a capacity benchmark: the goal is "does this reveal anything
worth knowing," not "what's the maximum throughput this can sustain."

Run against the containerized app:

```bash
locust -f tests/perf/locustfile.py --headless -u 20 -r 5 -t 30s --host http://localhost:8000
```

**Result at 20 concurrent users, 30s:** 956 requests, 0 failures.

| Endpoint | Median | 95th pct | Max |
|---|---|---|---|
| `GET /api/expenses` (list) | 11 ms | 22 ms | 114 ms |
| `POST /api/expenses` (create) | 59 ms | 68 ms | 166 ms |

**Finding:** creating an expense is consistently ~5x slower than listing
them, even though both are single-row-scale operations against a table with
only a few hundred rows. The likely cause is in
[crud.py](src/app/crud.py#L6-L11): `create_expense` does `db.add()` →
`db.commit()` → `db.refresh()`. The commit is a real disk-synced write
(`fsync`), and `refresh()` issues a second round-trip `SELECT` afterward to
reload the server-generated `id` and `created_at` — needed because
`ExpenseRead` returns both, but it means every create is a write *plus* a
read, while list is a single read. This isn't a bug (the endpoint still
responds well under 100ms at this scale, comfortably fine for the traffic
this app would ever see) — but it's the honest, expected shape of a
write-vs-read latency gap, and worth being able to explain rather than being
surprised by if asked "why is create slower than list?" in an interview.

## Running locally

```bash
docker compose up --build
```

Then check `http://localhost:8000/health` — it should return `{"status": "ok"}`
once the app has connected to Postgres.

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) currently runs one job,
`api-schema`, against a Postgres service container on every push/PR to
`master`. It's deliberately not the full three-job (UI / API-schema / perf)
setup from the project plan yet — `ui-tests` (Selenium) and `perf-smoke`
(Locust) are added on Day 2 alongside the suites they actually run, rather
than standing up empty CI jobs today with nothing behind them.

## Status

Day 1 complete: `Expense` model + `POST/GET /api/expenses` (paginated),
Schemathesis contract suite passing (see findings above) and stable across
repeated runs, a Jinja2 frontend (list + add-expense form, PRG on submit)
verified manually in-browser including the server-side validation error
path, and a CI skeleton running the schema suite on every push.

Day 2 in progress: Selenium UI suite covers the expense list (empty state,
populated state, date-descending ordering) and the add-expense form (happy
path through to the redirect, and the server-side validation path via a
client-validation bypass) — 5 tests, all passing against the containerized
app. Locust smoke test run against the same containerized app: 0 failures
at 20 concurrent users, with a documented (non-bug) create-vs-list latency
gap — see above. Remaining: finalized parallel CI (`ui-tests` +
`perf-smoke` jobs).
