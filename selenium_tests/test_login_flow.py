"""
Selenium end-to-end test for the Card-Jitsu login UI flow.

This test automates a full browser session to validate that:
- The login page loads correctly.
- A user can enter credentials and submit the form.
- Successful login redirects to the home page.
- UI elements expected on the home page (welcome text, deckbuilder button)
  are present.

NOTE:
    This test requires the Flask server to be running locally at:
    http://localhost:5000
"""
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def run_login_flow():
    """
    Run a Selenium-driven login flow to verify UI functionality.

    Steps performed:
        1. Launch Chrome via webdriver_manager.
        2. Navigate to the `/login` page.
        3. Enter username and password.
        4. Submit the login form.
        5. Wait for redirect to the home page.
        6. Assert the title contains "Card-Jitsu Home".
        7. Verify page heading and the presence of the deckbuilder button.

    Raises:
        AssertionError: If any UI validation fails.
    """
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    try:
        driver.get("http://localhost:5000/login")

        time.sleep(1)  # wait for page to load

        username_input = driver.find_element(By.NAME, "username")
        password_input = driver.find_element(By.NAME, "password")
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        username_input.send_keys("Aradtesting")
        password_input.send_keys("test")
        login_button.click()

        time.sleep(2)  # wait for login to process

        assert "Card-Jitsu Home" in driver.title

        heading = driver.find_element(By.TAG_NAME, "h1")
        assert "Welcome to Card-Jitsu" in heading.text

        deck_button = driver.find_element(By.ID, "deckbuilderbutton")
        assert deck_button.is_displayed()

        print("Selenium login flow test passed.")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_login_flow()