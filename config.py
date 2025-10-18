import configparser
import os
import sys
from pathlib import Path

CONFIG_FILENAME = "perapera_config.ini"

def find_game_data_dir():
    if sys.platform == "win32":
        local_low = Path(os.environ.get("USERPROFILE", "")) / "AppData" / "LocalLow"
        potential_path = local_low / "Cygames" / "umamusume"
        if (potential_path / "meta").exists() and (potential_path / "master" / "master.mdb").exists():
            return str(potential_path)
    return ""

def create_default_config(config_path):
    print(f"Configuration file not found. Creating a default '{config_path}'...")
    config = configparser.ConfigParser()

    config.add_section("Paths")
    game_dir = find_game_data_dir()
    config.set("Paths", "game_data_directory", game_dir)

    config.set("Paths", "workspace_directory", "translations")
    
    config.set("Paths", "mod_directory", "build/localized_data")

    config.add_section("Settings")
    config.set("Settings", "auto_download_assets", "true")

    with open(config_path, 'w', encoding='utf-8') as f:
        for section in config.sections():
            f.write(f"[{section}]\n")
            for key, value in config.items(section):
                f.write(f"{key} = {value}\n")
            f.write("\n")
    print("Default config created. Please verify the 'game_data_directory' path is correct.")

config = configparser.ConfigParser()
if not Path(CONFIG_FILENAME).exists():
    create_default_config(CONFIG_FILENAME)

try:
    config.read(CONFIG_FILENAME, encoding='utf-8-sig')

    GAME_DATA_DIR = Path(config.get("Paths", "game_data_directory", fallback=""))
    WORKSPACE_DIR = Path(config.get("Paths", "workspace_directory", fallback="translations")).resolve()
    MOD_DIR = Path(config.get("Paths", "mod_directory", fallback="build/localized_data")).resolve()

    if not GAME_DATA_DIR or not GAME_DATA_DIR.is_dir():
        print(f"Error: The 'game_data_directory' path specified in '{CONFIG_FILENAME}' is invalid or missing.")
        print("Please correct the path and try again.")
        sys.exit(1)

    AUTO_DOWNLOAD_ASSETS = config.getboolean("Settings", "auto_download_assets", fallback=True)

except (configparser.Error, KeyError) as e:
    print(f"Error reading '{CONFIG_FILENAME}': {e}")
    sys.exit(1)