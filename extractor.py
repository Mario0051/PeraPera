import argparse
import json
from pathlib import Path
import os
import sys
from Levenshtein import ratio as similarity
from asset_loader import AssetManager
from config import WORKSPACE_DIR, MOD_DIR
from common import StoryId
from hachimi_converter import convert_to_hachimi_format

PARSER_MAP = {
    "story": "parse_story_timeline",
    "race": "parse_race_story",
    "lyrics": "parse_lyrics",
    "home": "parse_home_timeline",
    "preview": "parse_preview",
    "uianimation": "parse_uianimation",
    "generic": "parse_generic",
}

def merge_translations(new_data, existing_tl_path: Path | None):
    if not existing_tl_path or not existing_tl_path.exists():
        return new_data

    print(f"Merging with existing file: '{existing_tl_path.name}'...")
    with open(existing_tl_path, 'r', encoding='utf-8-sig') as f:
        old_data = json.load(f)

    old_blocks = old_data.get("text_blocks", [])
    new_blocks = new_data.get("text_blocks", [])

    match_count = 0
    old_text_lookup = {block.get("jpText", "").strip(): block for block in old_blocks if block.get("jpText")}

    for new_block in new_blocks:
        jp_text = new_block.get("jpText")
        if not jp_text: continue

        best_match = old_text_lookup.get(jp_text.strip())

        if not best_match:
            best_match = max(
                old_blocks,
                key=lambda old_block: similarity(jp_text, old_block.get("jpText", "")),
                default=None
            )

        if best_match and similarity(jp_text, best_match.get("jpText", "")) > 0.85:
            match_count += 1
            new_block["enText"] = best_match.get("enText", "")
            if "enName" in best_match:
                new_block["enName"] = best_match.get("enName", "")
            if "choices" in new_block and "choices" in best_match:
                for i, new_choice in enumerate(new_block["choices"]):
                    if i < len(best_match["choices"]):
                        new_choice["enText"] = best_match["choices"][i].get("enText", "")

    print(f"  -> Merge complete. Matched {match_count}/{len(new_blocks)} blocks.")
    return new_data

def extract_asset_data(manager: AssetManager, asset_type: str, asset_name: str, workspace_path: Path | None):
    story_id = StoryId.parse_from_path(asset_type, asset_name)
    group_name = manager.get_group_name(asset_type, story_id.group)
    if group_name:
        story_id.group_name = group_name

    env = manager.load_bundle(asset_name)
    if not env:
        raise RuntimeError(f"Failed to load bundle for {asset_name}.")

    import asset_loader
    parser_func = getattr(asset_loader, PARSER_MAP[asset_type])
    extracted_data = parser_func(env, manager, story_id.group_name)

    if extracted_data is None:
        raise RuntimeError("Parsing failed: The asset does not contain the expected data structure.")
    extracted_data["asset_name"] = asset_name
    if story_id.group_name: extracted_data["group_name"] = story_id.group_name
    extracted_data["type"] = asset_type

    if asset_type == "uianimation":
        hash_str, _ = manager.get_asset_info(asset_name)
        if hash_str:
            extracted_data["bundle_hashes"] = {
                manager.platform.lower(): hash_str
            }

    final_data = extracted_data
    if asset_type != "uianimation":
        final_data = merge_translations(extracted_data, workspace_path)
        
    return final_data

def process_asset(manager, asset_type, asset_name, workspace_dir, mod_dir, update=False, overwrite=False):
    story_id = StoryId.parse_from_path(asset_type, asset_name)
    workspace_full_path = workspace_dir / story_id.get_output_path() / f"{story_id.get_filename_prefix()}.json"

    mod_full_path = mod_dir / "assets" / f"{asset_name}.json"

    if workspace_full_path.exists() and not update and not overwrite:
        print(f"Skipped: {workspace_full_path.name} (already exists). Use --update or --overwrite.")
        return "skipped"

    try:
        final_data = extract_asset_data(manager, asset_type, asset_name, workspace_full_path if update else None)

        workspace_full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(workspace_full_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"Saved to workspace: {workspace_full_path}")

        hachimi_data = convert_to_hachimi_format(workspace_data)

        mod_full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mod_full_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"Built for Hachimi: {mod_full_path}")

        return "success"
    except Exception as e:
        print(f"ERROR processing {asset_name}: {e}")
        import traceback
        traceback.print_exc()
        return "failed"

def run(args):
    manager = None
    try:
        manager = AssetManager()

        assets_to_process = []
        if args.asset:
            print(f"Processing single specified asset: {args.asset}")
            assets_to_process.append(args.asset)
        else:
            print("--- Running in Batch Mode ---")
            print(f"Finding assets of type '{args.type}' (Group: {args.group or 'Any'}, ID: {args.id or 'Any'})...")
            all_assets = manager.query_asset_names(args.type)

            if args.group or args.id:
                filtered_assets = []
                for name in all_assets:
                    temp_story_id = StoryId.parse_from_path(args.type, name)
                    if temp_story_id.matches_filter(args.group, args.id):
                        filtered_assets.append(name)
                assets_to_process = filtered_assets
                print(f"Filtered down to {len(assets_to_process)} assets.")
            else:
                assets_to_process = all_assets

        if not assets_to_process:
            print("No assets found to process with the given criteria.")
            return

        results = {"success": 0, "failed": 0, "skipped": 0}
        total = len(assets_to_process)
        print(f"\nStarting processing for {total} assets...")

        for i, asset_name in enumerate(assets_to_process):
            print(f"\n--- [{i+1}/{total}] ---")
            status = process_asset(manager, args.type, asset_name, WORKSPACE_DIR, MOD_DIR, args.update, args.overwrite)
            results[status] += 1

        print("\n--- Batch Process Summary ---")
        print(f"Successful: {results['success']}")
        print(f"Skipped:    {results['skipped']}")
        print(f"Failed:     {results['failed']}")

    except Exception as e:
        print(f"\n--- A critical error occurred ---")
        import traceback
        traceback.print_exc()
    finally:
        if manager:
            print("\nClosing database connections.")
            manager.close()

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "extract",
        help="Extracts/updates game assets into the workspace and builds to the Hachimi-compatible directory.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    parser.add_argument("type", choices=PARSER_MAP.keys(), help="The type of asset to process.")
    parser.add_argument("-g", "--group", help="Filter by Group ID (e.g., character or event ID).")
    parser.add_argument("-i", "--id", help="Filter by specific Story ID or Index/Part.")
    parser.add_argument("--asset", help="Specify a single asset name to process (ignores other filters).")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--update", action="store_true", help="Re-extract assets and merge with existing translations.")
    mode_group.add_argument("--overwrite", action="store_true", help="Re-extract assets and discard existing translations.")

    return parser