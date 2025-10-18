import argparse
from asset_loader import AssetManager
from common import StoryId

SEARCH_CATEGORY_MAP = {
    "story": {
        "character": 6,
        "event": 119
    },
    "home": {
        "character": 6
    }
}

def search_assets(manager: AssetManager, asset_type: str, search_term: str):
    print(f"Searching for '{asset_type}' assets matching '{search_term}'...")

    search_categories = SEARCH_CATEGORY_MAP.get(asset_type)
    if not search_categories:
        print(f"Error: No search configuration defined for asset type '{asset_type}'.")
        return

    master_cursor = manager.master_db.cursor()
    found_ids = {}
    for name_type, category_id in search_categories.items():
        query = 'SELECT "index", "text" FROM text_data WHERE "category" = ? AND "text" LIKE ?'
        try:
            results = master_cursor.execute(query, (category_id, f'%{search_term}%')).fetchall()
            if results:
                for r_id, r_name in results:
                    found_ids[str(r_id)] = r_name
        except Exception as e:
            print(f"Error querying master DB for category {category_id}: {e}")
            continue

    if not found_ids:
        print("No matching names found in the master database.")
        return

    print(f"Found {len(found_ids)} potential name matches. Now searching for associated assets...")

    meta_cursor = manager.meta_db.cursor()
    all_found_assets = []

    for item_id, item_name in found_ids.items():
        pattern = ""
        if asset_type == "story":
            group_prefix = item_id[:2] if len(item_id) > 2 else "%"
            pattern = f"story/data/{group_prefix}/{item_id}/storytimeline_%%%%%%%%%"
        elif asset_type == "home":
            pattern = f"home/data/%/%/hometimeline_%_%_{item_id}%"

        if not pattern:
            continue

        query = "SELECT n FROM a WHERE n LIKE ?"
        try:
            asset_results = meta_cursor.execute(query, (pattern,)).fetchall()
            for (asset_name,) in asset_results:
                all_found_assets.append((asset_name, item_name))
        except Exception as e:
            print(f"Error querying meta DB with pattern '{pattern}': {e}")

    if not all_found_assets:
        print("No asset files found for the matched names.")
        return

    print("\n--- Search Results ---")
    print(f"Found {len(all_found_assets)} asset files:")
    for asset_name, group_name in sorted(all_found_assets, key=lambda x: x[0]):
        story_id = StoryId.parse_from_path(asset_type, asset_name, group_name=group_name)
        print(f"  - Group: '{story_id.group_name}' (ID: {story_id.group}), Path: {asset_name}")
    print("--- End of Results ---\n")
    print("You can use the 'Path' with 'extractor.py --asset <path>' to extract a specific file.")

def run(args):
    manager = None
    try:
        manager = AssetManager()
        search_assets(manager, args.type, args.term)
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
        "query",
        help="Queries the game's database to find assets by name (e.g., character name)."
    )
    parser.set_defaults(func=run)

    parser.add_argument("type", choices=SEARCH_CATEGORY_MAP.keys(), help="The type of asset to search for.")
    parser.add_argument("term", help="The search term (e.g., 'Oguri Cap').")

    return parser

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['query'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)