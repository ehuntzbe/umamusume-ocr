import argparse
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options

# --- Paths ---
gecko_path = r"C:\Windows\geckodriver.exe"
firefox_path = r"C:\Program Files\Mozilla Firefox\firefox.exe"


def load_dataframe(csv_file: str) -> pd.DataFrame:
    """Load the CSV from the inputs directory."""
    inputs_dir = Path(__file__).resolve().parent / "inputs"
    csv_path = inputs_dir / csv_file
    return pd.read_csv(csv_path)


def init_driver() -> webdriver.Firefox:
    options = Options()
    options.binary_location = firefox_path
    service = FirefoxService(executable_path=gecko_path)
    driver = webdriver.Firefox(service=service, options=options)
    driver.maximize_window()
    driver.get("https://alpha123.github.io/uma-tools/umalator-global/")
    time.sleep(1)
    return driver


def simulate_input(el, value):
    el.click()
    el.send_keys(Keys.CONTROL + "a")
    el.send_keys(Keys.DELETE)
    for ch in str(value):
        el.send_keys(ch)
        time.sleep(0.05)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }))", el)
    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }))", el)
    time.sleep(0.2)


def fill_stats(row):
    stat_inputs = driver.find_elements(By.CSS_SELECTOR, "#umaPane .selected .horseParam input")
    keys = ["Speed", "Stamina", "Power", "Guts", "Wit"]
    for k, el in zip(keys, stat_inputs):
        print(f"→ {k}: {row[k]}")
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
    except Exception:
        print("⚠️ Could not close skill picker overlay.")


def add_skills(row):
    skills = str(row["Skills"]).split("|")

    for skill_name in skills:
        trimmed = skill_name.strip()
        if not trimmed:
            continue
        driver.find_element(By.CSS_SELECTOR, ".selected .addSkillButton").click()
        time.sleep(0.5)
        search_input = driver.find_element(
            By.CSS_SELECTOR, ".selected .horseSkillPickerWrapper input.filterSearch"
        )
        search_input.send_keys(trimmed)

        print(f"🔍 Adding skill: {trimmed}")
        xpath = (
            "//div[contains(@class,'selected')]//div[contains(@class,'horseSkillPickerWrapper')]//span[@class='skillName'"
            f" and normalize-space(text())={_xpath_text_literal(trimmed)}]"
        )
        try:
            result = driver.find_element(By.XPATH, xpath)
            result.click()
            time.sleep(0.2)
        except Exception:
            print(f"❌ Skill not found: {trimmed}")
        finally:
            _close_skill_picker()
            time.sleep(0.2)


def fill_umamusume(row):
    fill_stats(row)
    add_skills(row)


def run(df: pd.DataFrame):
    for idx, row in df.iterrows():
        if idx > 0:
            tabs = driver.find_elements(By.CLASS_NAME, "umaTab")
            tabs[idx].click()
            time.sleep(0.5)
        fill_umamusume(row)


def main(csv_file: str):
    global driver
    df = load_dataframe(csv_file)
    driver = init_driver()
    run(df)
    print("✅ All done!")
    # driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill Uma Musume data from CSV")
    parser.add_argument("csv_file", help="CSV filename located in the inputs directory")
    args = parser.parse_args()
    main(args.csv_file)
