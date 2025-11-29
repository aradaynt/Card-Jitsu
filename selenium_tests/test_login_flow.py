import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def run_login_flow():
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