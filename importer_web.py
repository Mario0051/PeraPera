import time
import datetime
from api import PeraPeraAPI

from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

def _get_skill_translation_map(pp_api: PeraPeraAPI) -> dict:
    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        return {}

    skill_map = {}
    if "47" in text_data:
        source_names = pp_api.mdb.get_text_data_category(47)
        for skill_id, translated_name in text_data["47"].items():
            if translated_name:
                source_name = source_names.get(int(skill_id))
                if source_name:
                    skill_map[source_name] = translated_name
    return skill_map

def _scrape_gametora_missions(pp_api: PeraPeraAPI):
    pp_api.log.info("Starting GameTora mission scraper...")

    try:
        pp_api.log.info("Setting up Selenium WebDriver...")
        service = FirefoxService(GeckoDriverManager().install())
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        driver = webdriver.Firefox(service=service, options=options)
        pp_api.log.info("WebDriver is ready.")
    except Exception as e:
        pp_api.log.error(f"Failed to initialize Selenium WebDriver: {e}")
        pp_api.log.error("Please ensure you have Firefox installed.")
        return

    mission_urls = {
        "Story Events": "https://gametora.com/umamusume/events/story-events",
        "Missions": "https://gametora.com/umamusume/missions",
        "Daily": "https://gametora.com/umamusume/missions/daily",
        "Main": "https://gametora.com/umamusume/missions/main",
        "Permanent": "https://gametora.com/umamusume/missions/permanent",
    }

    current_year = datetime.datetime.now().year
    for year in range(current_year - 1, current_year + 1):
        mission_urls[f"History {year}"] = f"https://gametora.com/umamusume/missions/history-{year}"

    scraped_translations = {}
    skill_map = _get_skill_translation_map(pp_api)
    pp_api.log.info(f"Loaded {len(skill_map)} translated skill names to improve mission text.")

    for name, url in mission_urls.items():
        pp_api.log.info(f"Scraping '{name}' missions from: {url}")
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[class^='missions_row_text_']"))
            )
            time.sleep(1)

            script = """
                let skill_dict = arguments[0];
                let out = [];
                let elements = document.querySelectorAll("[class^='missions_row_text_']");
                for (let i = 0; i < elements.length; i++) {
                    if (elements[i].children.length < 2) continue;

                    let jp_text = elements[i].children[0].innerText;
                    let en_element = elements[i].children[1];

                    let skill_elements = en_element.querySelectorAll("[aria-expanded='false']");
                    for (let j = 0; j < skill_elements.length; j++) {
                        let skill_name = skill_elements[j].innerText;
                        if (skill_dict.hasOwnProperty(skill_name)) {
                            skill_elements[j].textContent = skill_dict[skill_name];
                        }
                    }
                    let en_text = en_element.innerText;
                    out.push([jp_text, en_text]);
                }
                return out;
            """

            results = driver.execute_script(script, skill_map)

            for jp_text, en_text in results:
                cleaned_jp = jp_text.replace("\n", "").replace("\\n", "")
                if cleaned_jp and en_text:
                    scraped_translations[cleaned_jp] = en_text

        except TimeoutException:
            pp_api.log.warn(f"Timed out waiting for mission content on '{name}' page. Skipping.")
        except Exception as e:
            pp_api.log.error(f"An error occurred while scraping '{name}': {e}")

    driver.quit()
    pp_api.log.info(f"Scraping complete. Found {len(scraped_translations)} potential mission translations.")

    if not scraped_translations:
        return

    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

    mission_categories = ["66", "67"]
    filled_count = 0

    for cat_id in mission_categories:
        if cat_id in text_data:
            source_missions = pp_api.mdb.get_text_data_category(int(cat_id))
            for item_id, item_entry in text_data[cat_id].items():
                if not item_entry:
                    source_text = source_missions.get(int(item_id))
                    if source_text:
                        cleaned_source = source_text.replace("\n", "").replace("\\n", "")
                        if cleaned_source in scraped_translations:
                            text_data[cat_id][item_id] = scraped_translations[cleaned_source]
                            filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully imported {filled_count} mission translations from GameTora.")
    else:
        pp_api.log.info("No new mission translations to import from GameTora.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "import-web",
        help="Imports community translations by scraping web pages like GameTora.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--gametora-missions", action="store_true",
        help="Import mission translations from gametora.com."
    )

    def run(args):
        with PeraPeraAPI() as pp_api:
            if args.gametora_missions:
                _scrape_gametora_missions(pp_api)

    parser.set_defaults(func=run)
    return parser