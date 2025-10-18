import argparse
import sys
import traceback
from pathlib import Path

from api import PeraPeraAPI

def run(args):
    script_path = Path(args.script_path)
    if not script_path.exists() or not script_path.is_file():
        print(f"Error: Script file not found at '{script_path}'", file=sys.stderr)
        return

    print(f"--- Running automation script: {script_path.name} ---")

    try:
        with PeraPeraAPI() as pp_api:
            script_globals = {
                "pp_api": pp_api,
                "__file__": str(script_path),
            }

            with open(script_path, 'r', encoding='utf-8-sig') as f:
                script_code = f.read()

            exec(script_code, script_globals)

    except Exception:
        print(f"\n--- A critical error occurred during script execution ---", file=sys.stderr)
        traceback.print_exc()
    finally:
        print(f"--- Script '{script_path.name}' finished ---")

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "run",
        help="Runs a Python automation script for batch processing.",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Executes a .py script, providing it with a global 'pp_api' object to interact with the toolkit."
    )
    parser.set_defaults(func=run)
    parser.add_argument(
        "script_path",
        help="The path to the .py script to execute."
    )
    return parser