from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_TIMEOUT_SECONDS = 10


class BasePage:
    """Shared plumbing every page object needs: driver handle, base URL, one
    shared explicit wait, and navigation via the nav bar shared across every
    page (base.html).
    """

    _NAV_EXPENSES = (By.LINK_TEXT, "Expenses")
    _NAV_ADD_EXPENSE = (By.LINK_TEXT, "Add expense")

    def __init__(self, driver: WebDriver, base_url: str):
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS)

    def open(self, path: str) -> None:
        self.driver.get(f"{self.base_url}{path}")

    def go_to_list(self) -> "ExpenseListPage":
        # Imported here, not at module level, to avoid a circular import:
        # ExpenseListPage itself subclasses BasePage.
        from pages.expense_list_page import ExpenseListPage

        self.wait.until(EC.element_to_be_clickable(self._NAV_EXPENSES)).click()
        return ExpenseListPage(self.driver, self.base_url)

    def go_to_add_expense(self) -> "ExpenseFormPage":
        from pages.expense_form_page import ExpenseFormPage

        self.wait.until(EC.element_to_be_clickable(self._NAV_ADD_EXPENSE)).click()
        return ExpenseFormPage(self.driver, self.base_url)
