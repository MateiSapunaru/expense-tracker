from pages.expense_form_page import ExpenseFormPage
from pages.expense_list_page import ExpenseListPage


def test_add_expense_happy_path_redirects_and_lists_new_expense(driver, base_url):
    form = ExpenseFormPage(driver, base_url).load()
    form.fill_form(description="Team lunch", amount="42.50", category="food", date="2026-03-01")
    form.submit()

    list_page = ExpenseListPage(driver, base_url)
    list_page.wait.until(lambda d: d.current_url.rstrip("/") == base_url.rstrip("/"))

    rows = list_page.all_rows()
    assert rows[0] == {
        "date": "2026-03-01",
        "description": "Team lunch",
        "category": "food",
        "amount": "42.50",
    }


def test_add_expense_server_rejects_invalid_amount_even_if_client_checks_are_bypassed(driver, base_url):
    form = ExpenseFormPage(driver, base_url).load()
    form.fill_form(description="Bad amount", amount="0", category="food", date="2026-03-01")
    # amount=0 fails the server's ge=0.01 minimum, but it also fails the
    # input's own min="0.01" — a real click would never leave this page.
    # Bypassing client-side validation proves the server enforces this
    # independently, not just the browser.
    form.submit_bypassing_client_validation()

    error = form.wait_for_error()
    assert "amount" in error.lower()
    assert form.field_value("description") == "Bad amount"
    assert form.selected_category() == "food"
