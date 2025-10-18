import json
from pathlib import Path
from api import PeraPeraAPI
from common import StoryId
import argparse

def _merge_dictionaries(pp_api: PeraPeraAPI, source_dir: Path):
    dict_files = [
        "text_data_dict.json",
        "character_system_text_dict.json",
        "race_jikkyo_comment_dict.json",
        "race_jikkyo_message_dict.json"
    ]

    total_merged = 0

    pp_api.log.info("Starting dictionary merge...")

    for filename in dict_files:
        source_path = source_dir / filename
        dest_path = pp_api.workspace_dir / filename

        if not source_path.exists():
            continue

        if not dest_path.exists():
            pp_api.log.warn(f"Cannot merge '{filename}': file not found in your workspace. Please dump it first.")
            continue

        pp_api.log.info(f"Merging translations from '{filename}'...")

        source_data = pp_api.load_dict(source_path)
        dest_data = pp_api.load_dict(dest_path)

        file_merged_count = 0

        def merge_level(source_level, dest_level):
            nonlocal file_merged_count
            for key, source_value in source_level.items():
                if key not in dest_level:
                    continue

                dest_value = dest_level[key]

                if isinstance(source_value, dict) and isinstance(dest_value, dict):
                    merge_level(source_value, dest_value)
                elif isinstance(source_value, str) and isinstance(dest_value, str):
                    if source_value and not dest_value:
                        dest_level[key] = source_value
                        file_merged_count += 1

        merge_level(source_data, dest_data)

        if file_merged_count > 0:
            pp_api.save_dict(dest_path, dest_data)
            pp_api.log.info(f"Merged {file_merged_count} new translations into '{filename}'.")
            total_merged += file_merged_count

    if total_merged > 0:
        pp_api.log.info(f"Total dictionary entries merged: {total_merged}")
    else:
        pp_api.log.info("No new dictionary entries to merge.")

def _merge_stories(pp_api: PeraPeraAPI, source_dir: Path):
    source_assets_dir = source_dir / "assets"
    if not source_assets_dir.is_dir():
        pp_api.log.info("No 'assets' directory found in source, skipping story merge.")
        return

    pp_api.log.info("Starting story file merge...")

    total_merged = 0

    for source_path in source_assets_dir.rglob("*.json"):
        try:
            asset_name = str(source_path.relative_to(source_assets_dir).with_suffix(''))
            asset_name = asset_name.replace('\\', '/')

            asset_type = asset_name.split('/')[0]
            if asset_type not in ["story", "home", "race", "lyrics", "preview"]:
                asset_type = "generic"

            story_id = StoryId.parse_from_path(asset_type, asset_name)
            dest_path = pp_api.workspace_dir / story_id.get_output_path() / f"{story_id.get_filename_prefix()}.json"

            if not dest_path.exists():
                continue

            with open(source_path, 'r', encoding='utf-8-sig') as f:
                source_data = json.load(f)

            dest_data = pp_api.load_dict(dest_path)

            file_changed = False

            if source_data.get("title") and not dest_data.get("enTitle"):
                dest_data["enTitle"] = source_data["title"]
                file_changed = True

            source_blocks = source_data.get("text_block_list", [])
            dest_blocks = dest_data.get("text_blocks", [])

            for i, source_block in enumerate(source_blocks):
                if i >= len(dest_blocks): break
                dest_block = dest_blocks[i]

                if source_block.get("name") and not dest_block.get("enName"):
                    dest_block["enName"] = source_block["name"]
                    file_changed = True

                if source_block.get("text") and not dest_block.get("enText"):
                    dest_block["enText"] = source_block["text"]
                    file_changed = True

                source_choices = source_block.get("choice_data_list", [])
                dest_choices = dest_block.get("choices", [])
                for j, source_choice_text in enumerate(source_choices):
                    if j >= len(dest_choices): break
                    dest_choice = dest_choices[j]
                    if source_choice_text and not dest_choice.get("enText"):
                        dest_choice["enText"] = source_choice_text
                        file_changed = True

            if file_changed:
                pp_api.save_dict(dest_path, dest_data)
                total_merged += 1

        except Exception as e:
            pp_api.log.warn(f"Could not process story file {source_path.name}. Error: {e}")

    if total_merged > 0:
        pp_api.log.info(f"Successfully merged translations into {total_merged} story files.")
    else:
        pp_api.log.info("No new story file translations to merge.")

def run(args):
    source_dir = Path(args.source_dir)
    if not source_dir.is_dir():
        print(f"Error: Source directory not found at '{source_dir}'")
        return

    with PeraPeraAPI() as pp_api:
        _merge_dictionaries(pp_api, source_dir)
        _merge_stories(pp_api, source_dir)

    print("\nImport merge complete.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "import-hachimi",
        help="Merges translations from a Hachimi 'localized_data' directory into the PeraPera workspace.",
        description="This command will only fill in untranslated text in your workspace; it will not overwrite existing translations.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)
    parser.add_argument(
        "source_dir", 
        help="The path to the source Hachimi-formatted 'localized_data' directory you want to import from."
    )
    return parser