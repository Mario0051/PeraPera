import argparse
import json
import apsw
from pathlib import Path

from config import GAME_DATA_DIR, WORKSPACE_DIR
from common import MDB_TABLE_SCHEMAS

def dump_table(master_db_path: Path, table_name: str, output_path: Path):
    if table_name not in MDB_TABLE_SCHEMAS:
        print(f"Error: No schema defined for table '{table_name}'. Please update MDB_TABLE_SCHEMAS.")
        return

    print(f"Connecting to database at '{master_db_path}'...")
    try:
        connection = apsw.Connection(f"file:{master_db_path}?mode=ro", flags=apsw.SQLITE_OPEN_URI | apsw.SQLITE_OPEN_READONLY)
        cursor = connection.cursor()
    except Exception as e:
        print(f"Error: Could not connect to the master database. {e}")
        return

    schema = MDB_TABLE_SCHEMAS[table_name]
    columns_str = ", ".join(f'"{col}"' for col in schema)
    query = f"SELECT {columns_str} FROM {table_name}"

    print(f"Executing query for table '{table_name}'...")
    try:
        results = cursor.execute(query).fetchall()
    except Exception as e:
        print(f"Error: Failed to query table '{table_name}'. {e}")
        connection.close()
        return

    connection.close()
    print(f"Found {len(results)} rows.")

    dump_data = {}
    if len(schema) == 2:
        for key, value in results:
            dump_data[key] = value
    elif len(schema) > 2:
        for row in results:
            keys = row[:-1]
            value = row[-1]

            current_level = dump_data
            for i, key in enumerate(keys[:-1]):
                if key not in current_level:
                    current_level[key] = {}
                current_level = current_level[key]
            current_level[keys[-1]] = value

    output_file = output_path / f"{table_name}_dict.json"
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Writing structured data to '{output_file}'...")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dump_data, f, indent=4, ensure_ascii=False)
        print("Dump complete.")
    except Exception as e:
        print(f"Error: Could not write to output file. {e}")

def run(args):
    master_db_path = GAME_DATA_DIR / "master" / "master.mdb"
    output_directory = Path(args.output_dir)

    dump_table(master_db_path, args.table_name, output_directory)

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "dump",
        help="Dumps MDB table text to a JSON file in your workspace."
    )
    parser.set_defaults(func=run)

    parser.add_argument("table_name", choices=MDB_TABLE_SCHEMAS.keys(), help="The name of the database table to dump.")
    parser.add_argument("-o", "--output_dir", default=str(WORKSPACE_DIR), help=f"The directory to save the JSON dump. Defaults to your workspace ('{WORKSPACE_DIR}').")

    return parser

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['dump'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)