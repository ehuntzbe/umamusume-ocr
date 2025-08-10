import argparse
import logging
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options

ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(ENV_PATH)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger(__name__)
logger.debug("Environment loaded from %s with log level %s", ENV_PATH, LOG_LEVEL)

# --- Paths ---
gecko_path = r"C:\Windows\geckodriver.exe"
firefox_path = r"C:\Program Files\Mozilla Firefox\firefox.exe"


def load_dataframe(csv_file: str) -> pd.DataFrame:
    """Load the CSV from the inputs directory."""
    inputs_dir = Path(__file__).resolve().parent / "inputs"
    csv_path = inputs_dir / csv_file
    logger.info("Loading CSV data from %s", csv_path)
    df = pd.read_csv(csv_path)
    logger.debug("Dataframe loaded with shape %s", df.shape)
    return df


def init_driver() -> webdriver.Firefox:
    logger.info("Initializing Firefox driver")
    options = Options()
    options.binary_location = firefox_path
    service = FirefoxService(executable_path=gecko_path)
    try:
        driver = webdriver.Firefox(service=service, options=options)
    except Exception as e:
        logger.error("Failed to initialize Firefox driver: %s", e)
        raise
    driver.maximize_window()
    driver.get("https://alpha123.github.io/uma-tools/umalator-global/")
    time.sleep(1)
    logger.debug("Navigated to uma tools page")
    logger.info("Webdriver ready")
    return driver


def simulate_input(el, value):
    logger.debug("Simulating input: %s", value)
    el.click()
    el.send_keys(Keys.CONTROL + "a")
    el.send_keys(Keys.DELETE)
    for ch in str(value):
        el.send_keys(ch)
        time.sleep(0.05)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }))", el)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }))", el)
    logger.debug("Input events dispatched for value %s", value)
    time.sleep(0.2)


def fill_stats(row):
    stat_inputs = driver.find_elements(By.CSS_SELECTOR, "#umaPane .selected .horseParam input")
    keys = ["Speed", "Stamina", "Power", "Guts", "Wit"]
    for k, el in zip(keys, stat_inputs):
        logger.info("Setting %s to %s", k, row[k])
        simulate_input(el, row[k])


def _xpath_text_literal(text: str) -> str:
    """Return an XPath-safe string literal for the given text."""
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    parts = text.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"


def _close_skill_picker():
    try:
        driver.execute_script(
            """
            const overlay = document.querySelector('.selected .horseSkillPickerOverlay');
            if (overlay) overlay.click();
            """
        )
    except Exception as e:
        logger.warning("Could not close skill picker overlay: %s", e)


def add_skills(row):
    skills = str(row["Skills"]).split("|")
    logger.debug("Processing %d skills", len(skills))

    for skill_name in skills:
        trimmed = skill_name.strip()
        if not trimmed:
            logger.debug("Skipping empty skill entry")
            continue
        driver.find_element(By.CSS_SELECTOR, ".selected .addSkillButton").click()
        time.sleep(0.5)
        search_input = driver.find_element(
            By.CSS_SELECTOR, ".selected .horseSkillPickerWrapper input.filterSearch"
        )
        search_input.send_keys(trimmed)

        logger.info("Adding skill: %s", trimmed)
        xpath = (
            "//div[contains(@class,'selected')]//div[contains(@class,'horseSkillPickerWrapper')]//span[@class='skillName'"
            f" and normalize-space(text())={_xpath_text_literal(trimmed)}]"
        )
        try:
            result = driver.find_element(By.XPATH, xpath)
            result.click()
            time.sleep(0.2)
            logger.debug("Skill %s added", trimmed)
        except Exception as e:
            logger.error("Skill not found: %s (%s)", trimmed, e)
        finally:
            _close_skill_picker()
            time.sleep(0.2)


def fill_umamusume(row):
    logger.debug("Filling stats and skills for row")
    fill_stats(row)
    add_skills(row)


def run(df: pd.DataFrame):
    logger.info("Processing %d rows", len(df))
    for idx, row in df.iterrows():
        if idx > 0:
            tabs = driver.find_elements(By.CLASS_NAME, "umaTab")
            tabs[idx].click()
            time.sleep(0.5)
        logger.debug("Processing row %s", idx)
        fill_umamusume(row)


def main(csv_file: str):
    logger.info("Starting filling process for %s", csv_file)
    global driver
    df = load_dataframe(csv_file)
    driver = init_driver()
    try:
        run(df)
        logger.info("All done! Processed %d entries", len(df))
    except Exception as e:
        logger.exception("Unhandled exception during run: %s", e)
    finally:
        logger.debug("fill_umamusume main finished")
    # driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill Uma Musume data from CSV")
    parser.add_argument("csv_file", help="CSV filename located in the inputs directory")
    args = parser.parse_args()
    main(args.csv_file)
