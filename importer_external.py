import argparse
import requests
from api import PeraPeraAPI

GAMETORA_SKILLS_URL = "https://gametora.com/loc/umamusume/skills.json"
UMAPYOI_CHARA_LIST_URL = "https://umapyoi.net/api/v1/character"
UMAPYOI_CHARA_DETAIL_URL = "https://umapyoi.net/api/v1/character/{}"

def _umafy(text: str) -> str:
    return text.replace("horsegirl", "Umamusume").replace("Horsegirl", "Umamusume")

def _import_gametora_skills(pp_api: PeraPeraAPI):
    pp_api.log.info(f"Fetching skill data from GameTora...")
    try:
        response = requests.get(GAMETORA_SKILLS_URL, timeout=10)
        response.raise_for_status()
        gt_data = response.json()
    except requests.exceptions.RequestException as e:
        pp_api.log.error(f"Failed to fetch data from GameTora: {e}")
        return

    gt_name_dict = {data['name_ja']: _umafy(data['name_en']) for data in gt_data if data.get('name_en')}
    gt_desc_dict = {str(data['id']): _umafy(data['desc_en']) for data in gt_data if data.get('desc_en')}

    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first using the 'dump' command.")
        return

    names_filled = 0
    descs_filled = 0

    if "47" in text_data:
        key_to_source_map = pp_api.mdb.get_text_data_category(47)
        for skill_id, skill_entry in text_data["47"].items():
            if isinstance(skill_entry, str) and not skill_entry:
                source_text = key_to_source_map.get(int(skill_id))
                if source_text and source_text in gt_name_dict:
                    text_data["47"][skill_id] = gt_name_dict[source_text]
                    names_filled += 1

    if "48" in text_data:
        for skill_id, skill_entry in text_data["48"].items():
            if isinstance(skill_entry, str) and not skill_entry:
                if skill_id in gt_desc_dict:
                    text_data["48"][skill_id] = gt_desc_dict[skill_id]
                    descs_filled += 1

    if names_filled > 0 or descs_filled > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Import complete. Filled {names_filled} skill names and {descs_filled} skill descriptions.")
    else:
        pp_api.log.info("No new skill translations to import from GameTora.")

def _import_umapyoi_profiles(pp_api: PeraPeraAPI):
    pp_api.log.info("Fetching character data from umapyoi.net...")

    PROFILE_CATEGORY_MAP = {
        "profile": "163", "slogan": "144", "ears_fact": "166",
        "tail_fact": "167", "strengths": "164", "weaknesses": "165",
        "family_fact": "169"
    }

    try:
        response = requests.get(UMAPYOI_CHARA_LIST_URL, timeout=15)
        response.raise_for_status()
        chara_list = response.json()
        chara_ids = [chara["game_id"] for chara in chara_list if chara.get("game_id")]
        pp_api.log.info(f"Found {len(chara_ids)} characters to process.")

        text_data = pp_api.load_dict("text_data_dict.json")
        filled_count = 0

        for chara_id in chara_ids:
            try:
                detail_response = requests.get(UMAPYOI_CHARA_DETAIL_URL.format(chara_id), timeout=10)
                if not detail_response.ok: continue

                profile_data = detail_response.json()

                for api_field, category_id in PROFILE_CATEGORY_MAP.items():
                    if category_id in text_data and str(chara_id) in text_data[category_id]:
                        if not text_data[category_id][str(chara_id)] and profile_data.get(api_field):
                            text_data[category_id][str(chara_id)] = _umafy(profile_data[api_field])
                            filled_count += 1
            except requests.exceptions.RequestException as e:
                pp_api.log.warn(f"Could not fetch profile for chara_id {chara_id}: {e}")
                continue

        if filled_count > 0:
            pp_api.save_dict("text_data_dict.json", text_data)
            pp_api.log.info(f"Successfully imported {filled_count} profile entries from umapyoi.net.")
        else:
            pp_api.log.info("No new profile entries to import.")

    except requests.exceptions.RequestException as e:
        pp_api.log.error(f"Failed to fetch data from umapyoi.net: {e}")
        return
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

def run(args):
    with PeraPeraAPI() as pp_api:
        if args.gametora_skills:
            _import_gametora_skills(pp_api)
        elif args.umapyoi_profiles:
            _import_umapyoi_profiles(pp_api)
        else:
            pp_api.log.warn("No import target specified.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "import-external",
        help="Imports community translations from external sources like GameTora.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--gametora-skills", action="store_true",
        help="Import skill names and descriptions from gametora.com."
    )
    group.add_argument(
        "--umapyoi-profiles", action="store_true",
        help="Import character profile details from umapyoi.net."
    )
    return parser