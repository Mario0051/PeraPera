import json
from pathlib import Path
import sys

from asset_loader import AssetManager
from config import WORKSPACE_DIR

class PeraPeraAPI:
    def __init__(self):
        self._manager = None
        self.workspace_dir = WORKSPACE_DIR
        self.log = self._Log()
        self.mdb = self._Mdb(self)

    @property
    def manager(self) -> AssetManager:
        if self._manager is None:
            self.log.info("Initializing AssetManager for MDB access...")
            try:
                self._manager = AssetManager()
            except Exception as e:
                self.log.error(f"Failed to initialize AssetManager: {e}")
                raise
        return self._manager

    def load_dict(self, relative_path: str) -> dict | list:
        full_path = self.workspace_dir / relative_path
        if not full_path.exists():
            self.log.error(f"File not found: {full_path}")
            return {}
        try:
            with open(full_path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.log.error(f"Failed to decode JSON from {full_path}: {e}")
            return {}

    def save_dict(self, relative_path: str, data: dict | list) -> None:
        full_path = self.workspace_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.log.info(f"Saved file: {full_path}")
        except Exception as e:
            self.log.error(f"Failed to save file {full_path}: {e}")

    def close(self):
        if self._manager:
            self._manager.close()
            self.log.info("AssetManager connections closed.")

    class _Mdb:
        def __init__(self, parent: 'PeraPeraAPI'):
            self.parent = parent

        def get_text_data_category(self, category_id: int) -> dict[int, str]:
            if category_id == 0:
                print("Loading ALL text categories from DB...")
                cursor = self.parent.manager.master_db.cursor()
                query = 'SELECT "index", "text" FROM text_data'
                try:
                    return {int(row[0]): row[1] for row in cursor.execute(query).fetchall()}
                except Exception as e:
                    print(f"Error querying all of master DB: {e}")
                    return {}

            return self.parent.manager.get_text_data_category(category_id)

    class _Log:
        @staticmethod
        def info(message: str):
            print(f"[INFO] {message}")

        @staticmethod
        def warn(message: str):
            print(f"[WARN] {message}")

        @staticmethod
        def error(message: str):
            print(f"[ERROR] {message}", file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()