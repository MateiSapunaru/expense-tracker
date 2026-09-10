import random
from datetime import date, timedelta

from locust import HttpUser, between, task

# Deliberately no Faker dependency for a handful of realistic-enough values.
# Pulling in a data-generation library just for this would be exactly the
# kind of unexplainable, indefensible addition this project is trying to avoid.
_DESCRIPTIONS = [
    "Groceries", "Coffee", "Metro pass", "Electricity bill", "Gym membership",
    "Dinner out", "Movie tickets", "Phone bill", "Rent", "Pharmacy",
]
_CATEGORIES = ["food", "transport", "housing", "utilities", "entertainment", "health", "other"]


def _random_expense() -> dict:
    return {
        "description": random.choice(_DESCRIPTIONS),
        "amount": str(round(random.uniform(1, 500), 2)),
        "category": random.choice(_CATEGORIES),
        "date": (date.today() - timedelta(days=random.randint(0, 365))).isoformat(),
    }


class ExpenseTrackerUser(HttpUser):
    """Load-tests the two busiest JSON endpoints: listing expenses (read,
    paginated) and creating one (write), weighted 3:1 to reflect a
    read-heavy usage pattern where most requests browse the list and far
    fewer add a new expense. Page routes (Jinja2) aren't included here;
    they're the same process serving the same DB, so load-testing the JSON
    API already exercises the shared crud.py/DB path underneath both."""

    wait_time = between(0.1, 1)

    @task(3)
    def list_expenses(self):
        skip = random.randint(0, 100)
        # `name=` collapses the varying `skip` value into one stat line in
        # Locust's report instead of one row per distinct URL.
        self.client.get(f"/api/expenses?skip={skip}&limit=20", name="/api/expenses [list]")

    @task(1)
    def create_expense(self):
        self.client.post("/api/expenses", json=_random_expense(), name="/api/expenses [create]")
