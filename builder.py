import argparse
import json
import shutil
from pathlib import Path

from config import WORKSPACE_DIR, MOD_DIR
from hachimi_converter import convert_to_hachimi_format
from common import StoryId, MDB_TABLE_SCHEMAS

HACHIMI_DEFAULT_CONFIG = {
    "use_text_wrapper": True,
    "line_width_multiplier": 1.0,
    "assets_dir": "assets",
    "text_data_dict": "text_data_dict.json",
    "character_system_text_dict": "character_system_text_dict.json",
    "race_jikkyo_comment_dict": "race_jikkyo_comment_dict.json",
    "race_jikkyo_message_dict": "race_jikkyo_message_dict.json",
    "line_width_multiplier": 1.9,
    "auto_adjust_story_clip_length": True,
    "text_frame_line_spacing_multiplier": 0.72,
    "text_frame_font_size_multiplier": 0.96
}

def _get_hachimi_asset_path(asset_type: str, asset_name: str) -> Path:
    if asset_type in ["story", "home", "race", "preview", "generic", "uianimation"]:
        return Path(asset_name)

    if asset_type == "lyrics":
        return Path("lyrics") / Path(asset_name).name

    return Path(asset_name)

def build_hachimi_directory(workspace_dir: Path, hachimi_output_dir: Path, clean: bool):
    if not workspace_dir.is_dir():
        print(f"Error: PeraPera workspace directory not found at '{workspace_dir}'")
        return

    if clean and hachimi_output_dir.exists():
        print(f"Cleaning existing build directory: '{hachimi_output_dir}'...")
        shutil.rmtree(hachimi_output_dir)

    hachimi_output_dir.mkdir(parents=True, exist_ok=True)
    assets_output_dir = hachimi_output_dir / "assets"
    assets_output_dir.mkdir(exist_ok=True)

    print(f"Building Hachimi-compatible directory at '{hachimi_output_dir}'...")

    files_processed = 0

    for filepath in workspace_dir.rglob("*.json"):
        if any(table_name in filepath.name for table_name in MDB_TABLE_SCHEMAS.keys()):
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            asset_name = data.get("asset_name")
            asset_type = data.get("type")

            if not asset_name or not asset_type:
                print(f"  - WARNING: Skipping file with missing 'asset_name' or 'type': {filepath.name}")
                continue

            hachimi_data = convert_to_hachimi_format(data)

            if not hachimi_data:
                continue

            hachimi_relative_path = _get_hachimi_asset_path(asset_type, asset_name)
            destination_path = assets_output_dir / f"{hachimi_relative_path}.json"

            destination_path.parent.mkdir(parents=True, exist_ok=True)
            with open(destination_path, 'w', encoding='utf-8') as f:
                json.dump(hachimi_data, f, indent=4, ensure_ascii=False)

            files_processed += 1

        except Exception as e:
            print(f"  - ERROR: Failed to process {filepath.name}: {e}")

    print(f"Processed {files_processed} asset files.")

    mdb_copied_count = 0
    for table_name in MDB_TABLE_SCHEMAS.keys():
        mdb_file = workspace_dir / f"{table_name}_dict.json"
        if mdb_file.exists():
            shutil.copy2(mdb_file, hachimi_output_dir / mdb_file.name)
            print(f"Copied MDB dictionary: {mdb_file.name}")
            mdb_copied_count += 1

    config_path = hachimi_output_dir / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(HACHIMI_DEFAULT_CONFIG, f, indent=4)
    print("Created default Hachimi config.json.")

    print("\n--- Build Summary ---")
    print(f"Successfully processed {files_processed} assets and {mdb_copied_count} MDB files.")
    print(f"Hachimi-ready directory created at: '{hachimi_output_dir}'")
    print("You can now point Hachimi to use this 'localized_data' folder.")

def run(args):
    workspace_path = Path(args.input_dir)
    hachimi_path = Path(args.output_dir)

    build_hachimi_directory(workspace_path, hachimi_path, args.clean)

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "build",
        help="Builds a Hachimi-compatible 'localized_data' directory from your PeraPera workspace.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    parser.add_argument(
        "-i", "--input_dir", 
        default=str(WORKSPACE_DIR),
        help=f"The PeraPera workspace to build from. Defaults to '{WORKSPACE_DIR}'."
    )
    parser.add_argument(
        "-o", "--output_dir", 
        default=str(MOD_DIR), 
        help=f"The mod directory to build to. Defaults to '{MOD_DIR}'."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Deletes the existing build directory before creating a new one."
    )

    return parser