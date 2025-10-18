import argparse
import json
from pathlib import Path
import sys

from config import WORKSPACE_DIR
from common import MDB_TABLE_SCHEMAS
from postprocess import apply_postprocess

def generate_sql_patch(table_name: str, input_json_path: Path, output_sql_path: Path) -> bool:
    if not input_json_path.exists():
        print(f"Error: Input JSON file not found at '{input_json_path}'")
        return False

    print(f"Loading translations from '{input_json_path.name}'...")
    with open(input_json_path, 'r', encoding='utf-8-sig') as f:
        try:
            translation_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON file. {e}")
            return False

    schema = MDB_TABLE_SCHEMAS[table_name]
    key_columns = schema[:-1]
    value_column = schema[-1]

    print(f"Generating SQL UPDATE statements for table '{table_name}'...")
    sql_statements = []

    def flatten_and_generate_sql(data, keys=[]):
        if isinstance(data, dict):
            for key, value in data.items():
                flatten_and_generate_sql(value, keys + [key])
        else:
            if data is None or data == "":
                return

            category_id = keys[0] if table_name == "text_data" else table_name
            processed_text = apply_postprocess(table_name, category_id, data)

            sql_value = str(processed_text).replace("'", "''")
            where_clauses = []
            for i, key_col in enumerate(key_columns):
                key_val = keys[i]
                if isinstance(key_val, str) and not key_val.isdigit():
                    where_clauses.append(f'"{key_col}" = \'{key_val}\'')
                else:
                    where_clauses.append(f'"{key_col}" = {key_val}')
            where_str = " AND ".join(where_clauses)
            update_sql = f"UPDATE {table_name} SET \"{value_column}\" = '{sql_value}' WHERE {where_str};"
            sql_statements.append(update_sql)

    flatten_and_generate_sql(translation_data)

    if not sql_statements:
        print("No translated data found to generate a patch.")
        return True

    print(f"Writing {len(sql_statements)} statements to '{output_sql_path}'...")
    try:
        output_sql_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_sql_path, 'w', encoding='utf-8') as f:
            f.write("BEGIN TRANSACTION;\n")
            for stmt in sql_statements:
                f.write(stmt + "\n")
            f.write("COMMIT;\n")
        print("SQL patch generated successfully.")
        return True
    except Exception as e:
        print(f"Error writing to SQL file: {e}")
        return False

def run_cli(args):
    input_path = Path(args.input) if args.input else WORKSPACE_DIR / f"{args.table_name}_dict.json"
    output_path = Path(args.output) if args.output else WORKSPACE_DIR / f"{args.table_name}_patch.sql"
    generate_sql_patch(args.table_name, input_path, output_path)

def add_parser(subparsers):
    parser = subparsers.add_parser(
        "patch",
        help="Generates a .sql patch file from a translated MDB JSON dump.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.set_defaults(func=run_cli)

    parser.add_argument(
        "table_name", 
        choices=MDB_TABLE_SCHEMAS.keys(),
        help="The name of the database table this patch is for."
    )
    parser.add_argument(
        "-i", "--input", 
        help="Path to the input JSON file. Defaults to '{WORKSPACE_DIR}/table_name_dict.json'."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Path for the output .sql file. Defaults to '{WORKSPACE_DIR}/table_name_patch.sql'."
    )

    return parser

if __name__ == "__main__":
    main_parser = argparse.ArgumentParser()
    subparsers = main_parser.add_subparsers(dest="command")
    add_parser(subparsers)

    args = main_parser.parse_args(['patch'] + sys.argv[1:])
    if hasattr(args, 'func'):
        args.func(args)