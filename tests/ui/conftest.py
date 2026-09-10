import os

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app import crud, schemas
from app.database import Base, SessionLocal, engine
from app.models import Expense

# Selenium drives a real browser against a real HTTP server (unlike
# Schemathesis's in-process ASGI trick in tests/api), so this suite needs the
# app actually running: `docker compose up` locally, a background `uvicorn`
# process in CI. It talks to the same Postgres directly to seed and reset data.
BASE_URL = os.environ.get("UI_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_expenses_table():
    session = SessionLocal()
    try:
        session.query(Expense).delete()
        session.commit()
    finally:
        session.close()


@pytest.fixture
def seed_expenses():
    """Factory fixture: call with field overrides to insert one expense at a
    time, directly through the app's own crud layer (not a bespoke insert),
    so a test only has to spell out the fields it actually cares about."""
    session = SessionLocal()
    defaults = {
        "description": "Coffee",
        "amount": "4.50",
        "category": "food",
        "date": "2026-01-15",
    }

    def _seed(**overrides) -> Expense:
        data = {**defaults, **overrides}
        return crud.create_expense(session, schemas.ExpenseCreate.model_validate(data))

    yield _seed
    session.close()


@pytest.fixture
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def driver():
    options = Options()
    if os.environ.get("UI_HEADLESS", "true").lower() != "false":
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    drv = webdriver.Chrome(options=options)
    yield drv
    drv.quit()
