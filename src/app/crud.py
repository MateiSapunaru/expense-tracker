from sqlalchemy.orm import Session

from app import models, schemas


def create_expense(db: Session, expense: schemas.ExpenseCreate) -> models.Expense:
    db_expense = models.Expense(**expense.model_dump())
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


def get_expenses(db: Session, skip: int = 0, limit: int = 50) -> list[models.Expense]:
    return (
        db.query(models.Expense)
        .order_by(models.Expense.date.desc(), models.Expense.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
