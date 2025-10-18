import argparse
import json
import shutil
import sys
from pathlib import Path

from common import StoryId
from config import WORKSPACE_DIR

def import_zokuzoku_project(zokuzoku_dir: Path, perapera_dir: Path, dry_run: bool):
    if not zokuzoku_dir.is_dir():
        print(f"Error: The specified ZokuZoku directory does not exist: {zokuzoku_dir}")
        return

    print(f"Scanning ZokuZoku project at: '{zokuzoku_dir}'")
    print(f"Output will be placed in: '{perapera_dir}'")
    if dry_run:
        print("--- RUNNING IN DRY RUN MODE: No files will be copied. ---")

    files_processed = 0
    files_copied = 0
    files_skipped = 0

    for filepath in zokuzoku_dir.rglob("*.json"):
        files_processed += 1
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            asset_name = data.get("asset_name")
            asset_type = data.get("type")

            if not asset_name or not asset_type:
                files_skipped += 1
                continue

            story_id = StoryId.parse_from_path(asset_type, asset_name)

            if data.get("group_name"):
                 story_id.group_name = data.get("group_name")

            new_relative_path = story_id.get_output_path()
            new_filename = f"{story_id.get_filename_prefix()}.json"

            destination_path = perapera_dir / new_relative_path / new_filename

            print(f"\n'{filepath.relative_to(zokuzoku_dir)}' -> '{destination_path.relative_to(perapera_dir)}'")

            if not dry_run:
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(filepath, destination_path)

            files_copied += 1

        except (json.JSONDecodeError, Exception) as e:
            print(f"  - WARNING: Could not process file {filepath.name}. Error: {e}")
            files_skipped += 1

    print("\n--- Import Summary ---")
    print(f"Total files scanned: {files_processed}")
    print(f"Translation files processed: {files_copied}")
    print(f"Files skipped (non-translation or error): {files_skipped}")
    if dry_run:
        print("Dry run complete. No files were changed.")
    else:
        print("Import complete.")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "import",
        help="Imports a project from a ZokuZoku / Hachimi 'localized_data' directory into the PeraPera workspace structure.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    parser.add_argument(
        "source_dir", 
        help="The path to the source 'localized_data' directory you want to import."
    )
    parser.add_argument(
        "-o", "--output_dir", 
        default=str(WORKSPACE_DIR), 
        help=f"The PeraPera output directory. Defaults to '{WORKSPACE_DIR}'."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what actions would be taken without actually copying any files."
    )

    return parser

def run(args):
    zokuzoku_path = Path(args.source_dir)
    perapera_path = Path(args.output_dir)

    import_zokuzoku_project(zokuzoku_path, perapera_path, args.dry_run)

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['import'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)