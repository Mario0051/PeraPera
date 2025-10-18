import argparse
import sys
import shlex

import extractor
import find
import query
import validate
import mdb_dumper
import mdb_patcher
import importer
import builder
import automation
import export
import autofill
import importer_external
import asset_generator
import importer_web
import importer_hachimi

COMMAND_MODULES = {
    "extract": extractor,
    "find": find,
    "query": query,
    "validate": validate,
    "dump": mdb_dumper,
    "patch": mdb_patcher,
    "import": importer,
    "build": builder,
    "run": automation,
    "export": export,
    "autofill": autofill,
    "import-external": importer_external,
    "generate-assets": asset_generator,
    "import-web": importer_web,
    "import-hachimi": importer_hachimi,
}

def create_main_parser():
    parser = argparse.ArgumentParser(
        prog="perapera",
        description="PeraPera: An all-in-one translation toolkit for Umamusume.",
        epilog="Run 'perapera.py <command> --help' for more information on a specific command. Run without arguments to enter the interactive shell.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", title="Available Commands")

    for name, module in COMMAND_MODULES.items():
        module.add_parser(subparsers)

    return parser

def interactive_shell(main_parser):
    print("--- PeraPera Interactive Shell ---")
    print("Type a command (e.g., 'extract story -g 1001') or 'exit' to quit.")

    while True:
        try:
            input_line = input("(PeraPera) > ")
            if not input_line.strip():
                continue

            args_list = shlex.split(input_line)
            command = args_list[0].lower()

            if command in ["exit", "quit"]:
                print("Exiting...")
                break

            if command == "help":
                main_parser.print_help()
                continue

            try:
                args = main_parser.parse_args(args_list)
                if hasattr(args, 'func'):
                    args.func(args)
                else:
                    main_parser.parse_args([command, '--help'])
            except SystemExit:
                pass
            except Exception as e:
                print(f"Error executing command: {e}", file=sys.stderr)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

def main():
    main_parser = create_main_parser()

    if len(sys.argv) > 1:
        args = main_parser.parse_args()
        if hasattr(args, 'func'):
            args.func(args)
        else:
            main_parser.print_help()
    else:
        interactive_shell(main_parser)

if __name__ == "__main__":
    main()