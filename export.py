import argparse
import shutil
from pathlib import Path
import sys

from asset_loader import AssetManager
from config import WORKSPACE_DIR

def export_asset(asset_name: str, output_path: Path):
    manager = None
    try:
        print(f"Attempting to export asset: {asset_name}")
        manager = AssetManager()

        local_asset_path = manager.ensure_asset_is_ready(asset_name)

        if not local_asset_path or not local_asset_path.exists():
            print(f"ERROR: Could not find or download asset '{asset_name}'.", file=sys.stderr)
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(local_asset_path, output_path)
        print(f"Successfully exported '{asset_name}' to '{output_path}'")

    except Exception as e:
        print(f"\n--- A critical error occurred during export ---", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        if manager:
            manager.close()

def run(args):
    if args.target == "font":
        asset_name = "font/dynamic01.otf"
        output_path = WORKSPACE_DIR / "font" / "dynamic01.otf"
        export_asset(asset_name, output_path)
    else:
        print(f"Unknown export target: {args.target}", file=sys.stderr)

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "export",
        help="Exports raw game assets (like fonts) into your workspace.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run)
    parser.add_argument(
        "target", 
        choices=["font"], 
        help="The predefined asset to export. 'font' will export the main game font."
    )
    return parser