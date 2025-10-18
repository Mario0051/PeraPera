import argparse
import unicodedata
from pathlib import Path
import hashlib

from api import PeraPeraAPI
from config import WORKSPACE_DIR

def _autofill_pieces(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Character Pieces...")

    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first using the 'dump' command.")
        return

    chara_names = {}
    if "170" in text_data:
        for chara_id, entry in text_data["170"].items():
            if isinstance(entry, str) and entry:
                chara_names[chara_id] = entry

    if not chara_names:
        pp_api.log.warn("No translated character names found in category 170. Cannot autofill pieces.")
        return

    filled_count = 0
    if "113" in text_data:
        for piece_id, piece_entry in text_data["113"].items():
            if isinstance(piece_entry, str) and not piece_entry:
                chara_id = piece_id[:4]
                if chara_id in chara_names:
                    translated_name = chara_names[chara_id]
                    text_data["113"][piece_id] = f"{translated_name} Piece"
                    filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} character piece names.")
    else:
        pp_api.log.info("No new character piece names to autofill.")

def _autofill_duplicates(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for duplicate text entries...")

    try:
        text_data = pp_api.load_dict("text_data_dict.json")
        source_data = pp_api.mdb.get_text_data_category(0)
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first using the 'dump' command.")
        return

    pp_api.log.info("Scanning for existing translations...")
    hash_to_translation = {}
    all_source_text = {}
    for cat_id in text_data.keys():
        all_source_text.update(pp_api.mdb.get_text_data_category(int(cat_id)))

    for cat_id, entries in text_data.items():
        for item_id, translated_text in entries.items():
            if isinstance(translated_text, str) and translated_text:
                source_text = all_source_text.get(int(item_id))
                if source_text:
                    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
                    if source_hash not in hash_to_translation:
                        hash_to_translation[source_hash] = translated_text

    pp_api.log.info(f"Found {len(hash_to_translation)} unique translated strings.")

    pp_api.log.info("Applying translations to duplicates...")
    filled_count = 0
    for cat_id, entries in text_data.items():
        for item_id, translated_text in entries.items():
            if not translated_text:
                source_text = all_source_text.get(int(item_id))
                if source_text:
                    source_hash = hashlib.sha256(source_text.encode('utf-8')).hexdigest()
                    if source_hash in hash_to_translation:
                        entries[item_id] = hash_to_translation[source_hash]
                        filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} duplicate text entries.")
    else:
        pp_api.log.info("No new duplicate entries to fill.")

def _autofill_birthdays(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Birthdays...")
    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

    months = { "1": "January", "2": "February", "3": "March", "4": "April", "5": "May", 
               "6": "June", "7": "July", "8": "August", "9": "September", "10": "October", 
               "11": "November", "12": "December" }

    if "157" not in text_data:
        pp_api.log.warn("Category 157 (Birthdays) not found in text_data_dict.json.")
        return

    filled_count = 0
    source_birthdays = pp_api.mdb.get_text_data_category(157)
    for bday_id, bday_entry in text_data["157"].items():
        if isinstance(bday_entry, str) and not bday_entry:
            source_jp = source_birthdays.get(int(bday_id))
            if source_jp:
                try:
                    month_jp, day_jp = source_jp.split("月")
                    day = unicodedata.normalize('NFKC', day_jp[:-1])
                    month_en = months[unicodedata.normalize('NFKC', month_jp)]
                    text_data["157"][bday_id] = f"{month_en} {day}"
                    filled_count += 1
                except (ValueError, KeyError):
                    pp_api.log.warn(f"Could not parse birthday: {source_jp}")

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} birthdays.")
    else:
        pp_api.log.info("No new birthdays to autofill.")

def _autofill_support_card_combos(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Support Card Combos...")
    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

    support_titles = text_data.get("76", {})
    chara_names = text_data.get("77", {})

    if "75" not in text_data:
        pp_api.log.warn("Category 75 (Support Combos) not found.")
        return

    filled_count = 0
    for combo_id, combo_entry in text_data["75"].items():
        if isinstance(combo_entry, str) and not combo_entry:
            support_title = support_titles.get(combo_id)
            chara_name = chara_names.get(combo_id)
            if support_title and chara_name:
                text_data["75"][combo_id] = f"{support_title} {chara_name}"
                filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} support card combos.")
    else:
        pp_api.log.info("No new support card combos to autofill.")

def _autofill_race_commentary(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Race Commentary...")

    TITLES = {
        "三冠ウマ娘": "Triple Crown winner", "秋の三冠ウマ娘": "Autumn Triple Crown winner",
        "トリプルティアラのウマ娘": "Triple Tiara winner", "春の三冠ウマ娘": "Spring Triple Crown winner",
        "二冠ウマ娘": "Double Crown winner", "2大マイル戦覇者": "2 Major Mile champion",
        "2大スプリント覇者": "2 Major Sprint champion", "2大ダート戦覇者": "2 Major Dirt champion",
        "グランプリウマ娘": "Grand Prix champion", "ダービーウマ娘": "Derby champion",
        "天皇賞ウマ娘": "Tenno Sho champion", "皐月賞ウマ娘": "Satsuki Sho champion",
        "菊花賞ウマ娘": "Kikka Sho champion", "オークスウマ娘": "Oaks champion",
        "桜花賞ウマ娘": "Oka Sho champion", "秋華賞ウマ娘": "Shuka Sho champion",
        "ジュニア王者": "Junior champion", "春の天皇賞ウマ娘": "Spring Tenno Sho champion",
        "前年の覇者": "last year's champion", "ニエル賞を制した": "Prix Niel winner",
        "フォワ賞を制した": "Prix Foy winner", "ここまで無敗三冠ウマ娘": "undefeated Triple Crown winner",
        "ここまで無敗秋の三冠ウマ娘": "undefeated Autumn Triple Crown winner",
        "ここまで無敗トリプルティアラのウマ娘": "undefeated Triple Tiara winner",
        "ここまで無敗春の三冠ウマ娘": "undefeated Spring Triple Crown winner",
        "ここまで無敗二冠ウマ娘": "undefeated Double Crown winner",
        "ここまで無敗2大マイル戦覇者": "undefeated 2 Major Mile champion",
        "ここまで無敗2大スプリント覇者": "undefeated 2 Major Sprint champion",
        "ここまで無敗2大ダート戦覇者": "undefeated 2 Major Dirt champion",
        "ここまで無敗グランプリウマ娘": "undefeated Grand Prix champion",
        "ここまで無敗ダービーウマ娘": "undefeated Derby champion",
        "ここまで無敗天皇賞ウマ娘": "undefeated Tenno Sho champion",
        "ここまで無敗皐月賞ウマ娘": "undefeated Satsuki Sho champion",
        "ここまで無敗菊花賞ウマ娘": "undefeated Kikka Sho champion",
        "ここまで無敗オークスウマ娘": "undefeated Oaks champion",
        "ここまで無敗桜花賞ウマ娘": "undefeated Oka Sho champion",
        "ここまで無敗秋華賞ウマ娘": "undefeated Shuka Sho champion",
        "ここまで無敗ジュニア王者": "undefeated Junior champion",
        "ここまで無敗春の天皇賞ウマ娘": "undefeated Spring Tenno Sho champion",
        "ここまで無敗前年の覇者": "last year's undefeated champion",
        "ここまで無敗ニエル賞を制した": "undefeated Prix Niel winner",
        "ここまで無敗フォワ賞を制した": "undefeated Prix Foy winner",
    }

    TEMPLATES = [
        ("見事な勝利！これが{}の走り！", "A stunning victory! This is the run of a {}!"),
        ("見事な勝利！これが{}の実力だ！", "A stunning victory! This is the skill of a {}!"),
        ("強い！まさに{}！見事な勝利です！", "So strong! Truly a {}! A brilliant victory!"),
        ("素晴らしい走りでした！ {}、見事な勝利です！", "A wonderful run! {}, a brilliant victory!"),
        ("見事な差し切り勝ち！これが{}の実力だ！", "A stunning late surge victory! This is the skill of a {}!"),
    ]

    try:
        jikkyo_data = pp_api.load_dict("race_jikkyo_message_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'race_jikkyo_message_dict.json' not found. Please dump the table first.")
        return

    pp_api.log.info("Generating commentary permutations...")
    translation_map = {}
    for jp_template, en_template in TEMPLATES:
        for jp_title, en_title in TITLES.items():
            jp_full = jp_template.format(jp_title)
            en_full = en_template.format(en_title)
            translation_map[jp_full] = en_full
    pp_api.log.info(f"Generated {len(translation_map)} possible commentary lines.")

    filled_count = 0
    source_map = pp_api.mdb.get_text_data_category(32)
    for entry_id, translated_text in jikkyo_data.items():
        if isinstance(translated_text, str) and not translated_text:
            source_text = source_map.get(int(entry_id))
            if source_text in translation_map:
                jikkyo_data[entry_id] = translation_map[source_text]
                filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("race_jikkyo_message_dict.json", jikkyo_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} race commentary lines.")
    else:
        pp_api.log.info("No new race commentary lines to autofill.")

def _autofill_chara_secret_headers(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Character Secret Headers...")
    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

    chara_names = {
        source_text: translated_text
        for item_id, translated_text in text_data.get("6", {}).items()
        if translated_text and (source_text := pp_api.mdb.get_text_data_category(6).get(int(item_id)))
    }

    if not chara_names:
        pp_api.log.warn("No translated character names found in category 6. Cannot autofill secrets.")
        return

    filled_count = 0
    if "68" in text_data:
        source_secrets = pp_api.mdb.get_text_data_category(68)
        for secret_id, secret_entry in text_data["68"].items():
            if not secret_entry:
                source_jp = source_secrets.get(int(secret_id))
                if not source_jp: continue

                try:
                    num_char = source_jp[-1]
                    num = unicodedata.normalize('NFKC', num_char)

                    if not num.isnumeric(): continue

                    base_text = source_jp[:-1]
                    is_secret = False
                    if base_text.endswith("のヒミツ"):
                        base_text = base_text[:-4]
                        is_secret = True

                    char_name_en = chara_names.get(base_text)
                    if not char_name_en: continue

                    result = f"{char_name_en} "
                    if is_secret:
                        result += "Secret "
                    result += f"#{num}"

                    text_data["68"][secret_id] = result
                    filled_count += 1
                except Exception as e:
                    pp_api.log.warn(f"Could not parse secret header: {source_jp} ({e})")

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} secret headers.")
    else:
        pp_api.log.info("No new secret headers to autofill.")

def _autofill_support_effects(pp_api: PeraPeraAPI):
    pp_api.log.info("Running autofill for Support Card Effects...")
    try:
        text_data = pp_api.load_dict("text_data_dict.json")
    except FileNotFoundError:
        pp_api.log.error("'text_data_dict.json' not found. Please dump the table first.")
        return

    effect_dict = {
        source_text: translated_text
        for item_id, translated_text in text_data.get("151", {}).items()
        if translated_text and (source_text := pp_api.mdb.get_text_data_category(151).get(int(item_id)))
    }

    if not effect_dict:
        pp_api.log.warn("No translated support effects found in category 151. Cannot autofill.")
        return

    fill_ids = ['298', '329']
    filled_count = 0

    for cat_id in fill_ids:
        if cat_id in text_data:
            source_effects = pp_api.mdb.get_text_data_category(int(cat_id))
            for item_id, item_entry in text_data[cat_id].items():
                if not item_entry:
                    source_text = source_effects.get(int(item_id))
                    if source_text in effect_dict:
                        text_data[cat_id][item_id] = effect_dict[source_text]
                        filled_count += 1

    if filled_count > 0:
        pp_api.save_dict("text_data_dict.json", text_data)
        pp_api.log.info(f"Successfully autofilled {filled_count} support card effects.")
    else:
        pp_api.log.info("No new support card effects to autofill.")

def run(args):
    with PeraPeraAPI() as pp_api:
        if args.pieces:
            _autofill_pieces(pp_api)
        elif args.duplicates:
            _autofill_duplicates(pp_api)
        elif args.birthdays:
            _autofill_birthdays(pp_api)
        elif args.support_cards:
            _autofill_support_card_combos(pp_api)
        elif args.race_commentary:
            _autofill_race_commentary(pp_api)
        elif args.secrets:
            _autofill_chara_secret_headers(pp_api)
        elif args.support_effects:
            _autofill_support_effects(pp_api)
        else:
            pp_api.log.warn("No autofill target specified.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "autofill",
        help="Automatically generates translations based on simple rules and existing data.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--pieces", action="store_true",
        help="Autofill translations for character pieces (e.g., 'Special Week Piece')."
    )
    group.add_argument(
        "--duplicates", action="store_true",
        help="Fills untranslated text with existing translations of the same text."
    )
    group.add_argument(
        "--birthdays", action="store_true",
        help="Autofill birthday translations (e.g., '5月2日' -> 'May 2')."
    )
    group.add_argument(
        "--support-cards", action="store_true",
        help="Autofill support card + character name combos (e.g., 'SSR Tazuna')."
    )
    group.add_argument(
        "--race-commentary", action="store_true",
        help="Autofill dynamic race commentary lines using templates."
    )
    group.add_argument(
        "--secrets", action="store_true",
        help="Autofill character secret headers (e.g., 'Special Week Secret #1')."
    )
    group.add_argument(
        "--support-effects", action="store_true",
        help="Autofill reused support card effect descriptions."
    )
    return parser