import argparse
import json
import sys
from pathlib import Path
from config import WORKSPACE_DIR

def validate_files(directory: Path, asset_type_filter: str | None):
    if not directory.is_dir():
        print(f"Error: The specified translations directory does not exist: {directory}")
        return

    print(f"Starting validation scan in '{directory}'...")
    if asset_type_filter:
        print(f"Filtering for asset type: '{asset_type_filter}'")

    untranslated_files = {}
    total_untranslated_blocks = 0

    for filepath in sorted(directory.rglob("*.json")):
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            if asset_type_filter and data.get("type") != asset_type_filter:
                continue

            text_blocks = data.get("text_blocks")
            if not isinstance(text_blocks, list):
                continue

            file_has_untranslated = False
            untranslated_entries = []

            for block in text_blocks:
                jp_text = block.get("jpText")
                en_text = block.get("enText")
                if jp_text and not en_text:
                    file_has_untranslated = True
                    total_untranslated_blocks += 1
                    untranslated_entries.append({
                        "name": block.get("jpName", "N/A"),
                        "text": jp_text
                    })

                choices = block.get("choices", [])
                if isinstance(choices, list):
                    for choice in choices:
                        jp_choice = choice.get("jpText")
                        en_choice = choice.get("enText")
                        if jp_choice and not en_choice:
                            file_has_untranslated = True
                            total_untranslated_blocks += 1
                            untranslated_entries.append({
                                "name": "Choice",
                                "text": jp_choice
                            })

            if file_has_untranslated:
                untranslated_files[filepath.relative_to(directory)] = untranslated_entries

        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Could not process file {filepath.name}. Error: {e}")

    print("\n" + "="*30)
    print("  Validation Report: Untranslated Text  ")
    print("="*30)

    if not untranslated_files:
        print("\nSuccess! No untranslated text found.")
    else:
        print(f"\nFound {total_untranslated_blocks} untranslated block(s) in {len(untranslated_files)} file(s):\n")
        for file, entries in untranslated_files.items():
            print(f"--- File: {file} ---")
            for entry in entries:
                print(f"  - Name: {entry['name']}")
                print(f"    Text: {entry['text'].strip()}")
            print("-" * (len(str(file)) + 10))

    print("\n" + "="*30)

def run(args):
    scan_directory = Path(args.directory)

    try:
        validate_files(scan_directory, args.type)
    except Exception as e:
        print(f"\n--- A critical error occurred ---")
        import traceback
        traceback.print_exc()

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "validate",
        help="Scans your workspace for untranslated text and other issues."
    )
    parser.set_defaults(func=run)

    parser.add_argument("-t", "--type", help="Limit validation to a specific asset type (e.g., story, home).")
    parser.add_argument("-d", "--directory", default=str(WORKSPACE_DIR), help=f"The directory to scan. Defaults to your workspace ('{WORKSPACE_DIR}').")

    return parser

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['validate'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)