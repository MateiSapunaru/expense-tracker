from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import ExpenseCategory

# Excluded from the OpenAPI schema: these routes render HTML forms/pages, not
# the JSON API contract Schemathesis validates. They're covered by the
# Selenium suite instead.
router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/")
def list_expenses_page(request: Request, db: Session = Depends(get_db)):
    expenses = crud.get_expenses(db, skip=0, limit=100)
    return templates.TemplateResponse(
        request, "expenses/list.html", {"expenses": expenses}
    )


@router.get("/expenses/new")
def new_expense_page(request: Request):
    return templates.TemplateResponse(
        request, "expenses/form.html", {"categories": list(ExpenseCategory)}
    )


@router.post("/expenses/new")
def create_expense_page(
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db),
):
    submitted = {
        "description": description,
        "amount": amount,
        "category": category,
        "date": date,
    }
    try:
        expense = schemas.ExpenseCreate.model_validate(submitted)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        message = f"{first_error['loc'][0]}: {first_error['msg']}"
        return templates.TemplateResponse(
            request,
            "expenses/form.html",
            {
                "categories": list(ExpenseCategory),
                "error": message,
                "values": submitted,
            },
            status_code=422,
        )

    crud.create_expense(db, expense)
    return RedirectResponse(url="/", status_code=303)
