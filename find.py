import argparse
import json
import sys
from pathlib import Path
from config import WORKSPACE_DIR

def search_content_generator(search_dir: Path, term: str, case_sensitive: bool):
    if not search_dir.is_dir():
        print(f"Error: Directory does not exist: {search_dir}", file=sys.stderr)
        return

    search_term = term if case_sensitive else term.lower()

    for filepath in search_dir.rglob("*.json"):
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            text_blocks = data.get("text_blocks", [])
            if not isinstance(text_blocks, list): continue

            for i, block in enumerate(text_blocks):
                jp_text = block.get("jpText")
                if isinstance(jp_text, str):
                    haystack = jp_text if case_sensitive else jp_text.lower()
                    if search_term in haystack:
                        yield {
                            "filepath": str(filepath.resolve()),
                            "jpName": block.get("jpName", "N/A"),
                            "jpText": jp_text.strip(),
                            "block_index": block.get("block_index", i)
                        }
                for choice in block.get("choices", []):
                    jp_choice_text = choice.get("jpText")
                    if isinstance(jp_choice_text, str):
                        haystack = jp_choice_text if case_sensitive else jp_choice_text.lower()
                        if search_term in haystack:
                            yield {
                                "filepath": str(filepath.resolve()),
                                "jpName": "Choice",
                                "jpText": jp_choice_text.strip(),
                                "block_index": block.get("block_index", i)
                            }
        except Exception:
            continue

def run(args):
    search_directory = Path(args.directory)

    try:
        search_content_generator(search_directory, args.term, args.case_sensitive)
    except Exception as e:
        print(f"\n--- A critical error occurred ---")
        import traceback
        traceback.print_exc()

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "find",
        help="Searches for Japanese text within your workspace files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)

    parser.add_argument("term", help="The text to search for. Wrap in quotes if it contains spaces.")
    parser.add_argument("-c", "--case-sensitive", action="store_true", help="Perform a case-sensitive search.")
    parser.add_argument("-d", "--directory", default=str(WORKSPACE_DIR), help=f"The directory to search in. Defaults to your workspace ('{WORKSPACE_DIR}').")

    return parser

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['find'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)