from pages.expense_list_page import ExpenseListPage


def test_empty_state_shown_when_no_expenses(driver, base_url):
    page = ExpenseListPage(driver, base_url).load()

    assert page.is_empty_state_shown()
    assert page.row_count() == 0


def test_populated_list_shows_seeded_expenses(driver, base_url, seed_expenses):
    seed_expenses(description="Groceries", amount="55.20", category="food", date="2026-01-10")
    seed_expenses(description="Metro pass", amount="20.00", category="transport", date="2026-01-12")

    page = ExpenseListPage(driver, base_url).load()

    assert not page.is_empty_state_shown()
    assert page.row_count() == 2


def test_list_is_ordered_by_date_descending(driver, base_url, seed_expenses):
    seed_expenses(description="Older", amount="10.00", category="food", date="2026-01-01")
    seed_expenses(description="Newer", amount="20.00", category="food", date="2026-01-20")

    rows = ExpenseListPage(driver, base_url).load().all_rows()

    assert [row["description"] for row in rows] == ["Newer", "Older"]
