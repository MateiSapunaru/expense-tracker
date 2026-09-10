from datetime import date as date_
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models import ExpenseCategory


class ExpenseCreate(BaseModel):
    # Postgres text columns reject embedded NUL bytes at the wire protocol
    # level, which otherwise surfaces as an unhandled 500 rather than a
    # validation error — length/type constraints alone don't catch this
    # since a NUL byte is a perfectly valid single character otherwise.
    # Expressed as `pattern` (not a bespoke validator) so the constraint is
    # both enforced AND documented in the OpenAPI schema — Schemathesis
    # respects a documented `pattern` when generating "valid" data instead
    # of treating our rejection of it as a contract mismatch.
    description: str = Field(min_length=1, max_length=255, pattern=r"^[^\x00]*$")
    # Bounds match the `Numeric(10, 2)` column in models.Expense (8 integer
    # digits + 2 decimal digits) so invalid amounts get a clean 422 instead of
    # an unhandled DB overflow error turning into a 500.
    #
    # json_schema_extra fully replaces the generated schema instead of merging
    # into it: Pydantic's default schema for Decimal is an `anyOf` of "number"
    # and "string" representations, and the min/max only land on the "number"
    # branch, leaving the "string" branch unbounded. Since we only intend
    # clients to send amount as a plain JSON number, we pin the schema to
    # that single representation so the documented contract is accurate.
    amount: Decimal = Field(
        ge=Decimal("0.01"),
        le=Decimal("99999999.99"),
        decimal_places=2,
        json_schema_extra={
            "type": "number",
            "minimum": 0.01,
            "maximum": 99999999.99,
            "multipleOf": 0.01,
            "anyOf": None,
        },
    )
    category: ExpenseCategory
    date: date_


class ExpenseRead(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime

    # Pydantic serializes Decimal to a JSON string by default (to avoid
    # precision loss), but our documented response schema says `amount` is a
    # number. Emitting it as a float here is safe: values are capped under
    # 10^8 with 2 decimal places, well within float64's exact range, so the
    # response now actually matches the schema instead of contradicting it.
    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> float:
        return float(value)
