import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options

# --- Paths ---
csv_path = r"C:\Users\skyfj\Documents\My Games\Umamusume\simulator inputs\uma_data.csv"
gecko_path = r"C:\Windows\geckodriver.exe"
firefox_path = r"C:\Program Files\Mozilla Firefox\firefox.exe"

# --- Setup ---
df = pd.read_csv(csv_path)
options = Options()
options.binary_location = firefox_path
service = FirefoxService(executable_path=gecko_path)
driver = webdriver.Firefox(service=service, options=options)
driver.maximize_window()
driver.get("https://alpha123.github.io/uma-tools/umalator-global/")
time.sleep(1)

# --- Helpers ---
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
    keys = ['Speed', 'Stamina', 'Power', 'Guts', 'Wit']
    for k, el in zip(keys, stat_inputs):
        print(f"→ {k}: {row[k]}")
        simulate_input(el, row[k])

def fill_aptitudes_and_strategy(row):
    def select_dropdown_value(container_selector, value):
        dropdown = driver.find_element(By.CSS_SELECTOR, container_selector + " select")
        dropdown.click()
        for option in dropdown.find_elements(By.TAG_NAME, "option"):
            if option.text.strip() == str(value):
                option.click()
                break
        time.sleep(0.2)

    # Surface, Distance, Strategy, Strategy Aptitude (they are <select>s)
    select_dropdown_value(".selected .horseAptitudes > div:nth-of-type(1)", row["Surface"])
    select_dropdown_value(".selected .horseAptitudes > div:nth-of-type(2)", row["Distance"])
    select_dropdown_value(".selected .horseAptitudes > div:nth-of-type(3)", row["Strategy"])
    select_dropdown_value(".selected .horseAptitudes > div:nth-of-type(4)", row["StrategyApt"])

def add_skills(row):
    skills = str(row["Skills"]).split("|")

    # ✅ Working — do not change
    driver.find_element(By.CSS_SELECTOR, ".selected .addSkillButton").click()
    time.sleep(0.5)
    search_input = driver.find_element(By.CSS_SELECTOR, ".selected .horseSkillPickerWrapper input.filterSearch")

    for skill_name in skills:
        trimmed = skill_name.strip()
        if not trimmed:
            continue
        print(f"🔍 Adding skill: {trimmed}")
        search_input.clear()
        search_input.send_keys(trimmed)
        time.sleep(0.7)

        # ✅ FIXED: Scope result to .selected popup only
        try:
            result = driver.find_element(
                By.XPATH,
                f"//div[contains(@class,'selected')]//div[contains(@class,'horseSkillPickerWrapper')]//span[@class='skillName' and normalize-space(text())='{trimmed}']"
            )
            result.click()
            time.sleep(0.2)
        except Exception:
            print(f"❌ Skill not found: {trimmed}")

    # ✅ Close popup with JavaScript to avoid overlay issues
    try:
        driver.execute_script("""
            const overlay = document.querySelector('.selected .horseSkillPickerOverlay');
            if (overlay) overlay.click();
        """)
    except Exception:
        print("⚠️ Could not close skill picker overlay.")
    time.sleep(0.5)


# --- Main Routine ---
def fill_umamusume(row):
    fill_stats(row)
    add_skills(row)

# Fill Umamusume 1 (first tab)
fill_umamusume(df.iloc[0])

# Switch to Umamusume 2
for tab in driver.find_elements(By.CLASS_NAME, "umaTab"):
    if "selected" not in tab.get_attribute("class"):
        tab.click()
        break
time.sleep(0.5)

# Fill Umamusume 2 (second tab)
fill_umamusume(df.iloc[1])

print("✅ All done!")
# driver.quit()
