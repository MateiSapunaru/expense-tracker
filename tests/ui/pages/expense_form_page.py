from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from pages.base_page import BasePage

PATH = "/expenses/new"

# A native <input type="date"> expects locale-formatted keystrokes (e.g.
# MM/DD/YYYY on en-US Chrome), which is a well-known source of Selenium
# flakiness. Setting the value directly via the DOM and firing input/change
# events (so the browser treats it like a real edit) sidesteps that entirely.
_SET_DATE_JS = (
    "arguments[0].value = arguments[1];"
    "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
    "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));"
)


class ExpenseFormPage(BasePage):
    """POM for the add-expense form page ('/expenses/new')."""

    _FORM = (By.ID, "expense-form")
    _DESCRIPTION = (By.ID, "description")
    _AMOUNT = (By.ID, "amount")
    _CATEGORY = (By.ID, "category")
    _DATE = (By.ID, "date")
    _SUBMIT = (By.ID, "submit-expense")
    _ERROR = (By.ID, "form-error")

    _FIELD_LOCATORS = {
        "description": _DESCRIPTION,
        "amount": _AMOUNT,
        "date": _DATE,
    }

    def load(self) -> "ExpenseFormPage":
        self.open(PATH)
        self.wait.until(EC.presence_of_element_located(self._FORM))
        return self

    def fill_form(self, *, description: str, amount: str, category: str, date: str) -> "ExpenseFormPage":
        self.driver.find_element(*self._DESCRIPTION).send_keys(description)
        self.driver.find_element(*self._AMOUNT).send_keys(amount)
        Select(self.driver.find_element(*self._CATEGORY)).select_by_value(category)
        self.driver.execute_script(_SET_DATE_JS, self.driver.find_element(*self._DATE), date)
        return self

    def submit(self) -> None:
        """Realistic path: click the submit button, same as a real user.
        The browser's own HTML5 constraints (required/min/max/step) apply."""
        self.driver.find_element(*self._SUBMIT).click()

    def submit_bypassing_client_validation(self) -> None:
        """Calls the <form> element's native `submit()` via JS. Per the HTML
        spec this skips constraint validation entirely (unlike a real click
        or `requestSubmit()`), which is exactly what any non-browser client
        (curl, a hand-crafted request) would also skip, which is how this
        suite proves the server enforces validation on its own, not just the
        page's HTML attributes."""
        self.driver.execute_script("arguments[0].submit();", self.driver.find_element(*self._FORM))

    def wait_for_error(self) -> str:
        return self.wait.until(EC.visibility_of_element_located(self._ERROR)).text

    def field_value(self, field: str) -> str:
        return self.driver.find_element(*self._FIELD_LOCATORS[field]).get_attribute("value")

    def selected_category(self) -> str:
        return Select(self.driver.find_element(*self._CATEGORY)).first_selected_option.get_attribute("value")
