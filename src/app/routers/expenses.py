from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.post(
    "",
    response_model=schemas.ExpenseRead,
    status_code=201,
    # Starlette returns a bare 400 for a body that isn't valid JSON at all,
    # raised before Pydantic validation runs, so FastAPI never auto-documents
    # it (only 422 for validation failures on a parsed body is added
    # automatically). Declaring it here so the spec matches real behavior.
    responses={400: {"description": "Malformed JSON body"}},
)
def create_expense(expense: schemas.ExpenseCreate, db: Session = Depends(get_db)):
    return crud.create_expense(db, expense)


@router.get("", response_model=list[schemas.ExpenseRead])
def list_expenses(
    # Upper bound isn't just cosmetic: an unbounded skip lets a value larger
    # than Postgres's bigint range reach the OFFSET clause and crash with a
    # DB-level error instead of a clean 422 (found via Schemathesis fuzzing).
    skip: int = Query(0, ge=0, le=1_000_000),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud.get_expenses(db, skip=skip, limit=limit)
