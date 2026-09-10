from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from pages.base_page import BasePage

PATH = "/"


class ExpenseListPage(BasePage):
    """POM for the server-rendered expense list page ('/')."""

    # Exactly one of these two is always present — the server renders either
    # the table or the empty-state paragraph, never both.
    _READY = (By.CSS_SELECTOR, "#expenses-table, #empty-state")
    _ROWS = (By.CSS_SELECTOR, "#expenses-table tbody tr")
    _EMPTY_STATE = (By.ID, "empty-state")

    def load(self) -> "ExpenseListPage":
        self.open(PATH)
        self.wait.until(EC.presence_of_element_located(self._READY))
        return self

    def is_empty_state_shown(self) -> bool:
        return bool(self.driver.find_elements(*self._EMPTY_STATE))

    def row_count(self) -> int:
        return len(self.driver.find_elements(*self._ROWS))

    def all_rows(self) -> list[dict[str, str]]:
        rows = []
        for row in self.driver.find_elements(*self._ROWS):
            cells = row.find_elements(By.TAG_NAME, "td")
            rows.append(
                {
                    "date": cells[0].text,
                    "description": cells[1].text,
                    "category": cells[2].text,
                    "amount": cells[3].text,
                }
            )
        return rows
