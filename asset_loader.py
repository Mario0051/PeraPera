import apsw
import UnityPy
import os
import sys
import csv
import requests
from tqdm import tqdm
from functools import lru_cache
from pathlib import Path
import traceback

from config import GAME_DATA_DIR, AUTO_DOWNLOAD_ASSETS

META_DB_PATH = GAME_DATA_DIR / "meta"
MASTER_DB_PATH = GAME_DATA_DIR / "master" / "master.mdb"
ASSET_DIR = GAME_DATA_DIR / "dat"

ASSET_BASE_KEY = bytes.fromhex("532b4631e4a7b9473e7cfb")

DB_BASE_KEY_FOR_DB_DECRYPT = bytes([
    0xF1, 0x70, 0xCE, 0xA4, 0xDF, 0xCE, 0xA3, 0xE1,
    0xA5, 0xD8, 0xC7, 0x0B, 0xD1, 0x00, 0x00, 0x00
])

DB_KEY = bytes([
    0x6D, 0x5B, 0x65, 0x33, 0x63, 0x36, 0x63, 0x25, 0x54, 0x71, 0x2D, 0x73,
    0x50, 0x53, 0x63, 0x38, 0x6D, 0x34, 0x37, 0x7B, 0x35, 0x63, 0x70, 0x23,
    0x37, 0x34, 0x53, 0x29, 0x73, 0x43, 0x36, 0x33
])

def derive_db_decryption_key(key, base_key):
    if len(base_key) < 13:
        raise ValueError("Invalid Base Key length. Must be at least 13 bytes.")
    final_key = bytearray()
    for i in range(len(key)):
        final_key.append(key[i] ^ base_key[i % 13])
    return final_key

def create_asset_final_key(bundle_key_int):
    base_key = ASSET_BASE_KEY
    bundle_key_bytes = bundle_key_int.to_bytes(8, byteorder="little", signed=True)

    base_len = len(base_key)
    final_key = bytearray(base_len * 8)

    for i, b in enumerate(base_key):
        baseOffset = i << 3
        for j, k in enumerate(bundle_key_bytes):
            final_key[baseOffset + j] = b ^ k
    return bytes(final_key)

def decrypt_asset_data(data:bytes, final_key:bytes):
    decrypted_data = bytearray(data)
    key_len = len(final_key)
    for i in range(256, len(decrypted_data)):
        decrypted_data[i] ^= final_key[i % key_len]
    return bytes(decrypted_data)

def parse_story_timeline(env, manager: 'AssetManager', group_name: str | None = None):
    if not env:
        print("Error: Invalid UnityPy environment provided.")
        return None

    objects_by_path_id = {obj.path_id: obj for obj in env.objects if hasattr(obj, 'path_id')}

    timeline_data_asset = None
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if isinstance(tree, dict) and 'BlockList' in tree:
                    timeline_data_asset = tree
                    print(f"Found timeline data asset (PathID: {obj.path_id})")
                    break
            except Exception:
                continue

    if not timeline_data_asset:
        print("Error: Could not find timeline MonoBehaviour asset in the bundle.")
        return None

    char_names = manager.get_text_data_category(6)

    extracted_data = {"text_blocks": []}

    title = timeline_data_asset.get("Title")
    if title and title != "0":
        extracted_data["title"] = title

    block_list = timeline_data_asset.get("BlockList", [])

    global_cue_offset = 0

    for block_idx, block in enumerate(block_list[1:], start=1):
        if not (isinstance(block, dict)
                and (text_track := block.get("TextTrack")) and isinstance(text_track, dict)
                and (clip_list := text_track.get("ClipList")) and isinstance(clip_list, list) and clip_list):
            print(f"Warning: Skipping block {block_idx-1} due to malformed TextTrack or ClipList.")
            continue

        clip_info = clip_list[0]
        path_id = clip_info.get('m_PathID') if isinstance(clip_info, dict) else getattr(clip_info, 'path_id', None)

        if path_id is None:
            print(f"Warning: Could not determine path_id for block {block_idx-1}. Skipping.")
            continue

        text_clip_obj = objects_by_path_id.get(path_id)
        if not text_clip_obj:
            print(f"Warning: TextClip object with PathID {path_id} not found for block {block_idx-1}. Skipping.")
            continue

        try:
            text_clip_data = text_clip_obj.read_typetree()
            if not isinstance(text_clip_data, dict):
                 print(f"Warning: Typetree for PathID {path_id} is not a dictionary. Skipping block {block_idx-1}.")
                 continue

            jp_name = text_clip_data.get("Name", "")
            looked_up_name = char_names.get(int(jp_name)) if jp_name.isdigit() else jp_name

            original_cue_id = text_clip_data.get("CueId")
            final_cue_id = original_cue_id

            difference_flag = text_clip_data.get("DifferenceFlag", 0)
            local_cue_offset = 0

            if difference_flag == 2:
                local_cue_offset = 1

            if original_cue_id is not None and original_cue_id != -1:
                final_cue_id = original_cue_id + local_cue_offset + global_cue_offset

            if difference_flag == 4 and original_cue_id is not None and original_cue_id != -1:
                global_cue_offset += 1

            block_data = {
                "block_index": block_idx - 1,
                "path_id": path_id,
                "jpName": looked_up_name or jp_name,
                "enName": "",
                "jpText": text_clip_data.get("Text", ""),
                "enText": "",
                "voiceIdx": text_clip_data.get("CueId"),
                "cueSheet": text_clip_data.get("VoiceSheetId"),
                "choices": [],
                "coloredText": [],
                "nextBlock": text_clip_data.get("NextBlock", 0),
                "differenceFlag": text_clip_data.get("DifferenceFlag", 0)
            }

            for choice in text_clip_data.get("ChoiceDataList", []):
                if isinstance(choice, dict):
                    block_data["choices"].append({
                        "jpText": choice.get("Text", ""), "enText": "",
                        "nextBlock": choice.get("NextBlock", 0),
                        "differenceFlag": choice.get("DifferenceFlag", 0)
                    })

            for color_info in text_clip_data.get("ColorTextInfoList", []):
                 if isinstance(color_info, dict):
                      block_data["coloredText"].append({
                          "jpText": color_info.get("Text", ""), "enText": ""
                      })

            extracted_data["text_blocks"].append(block_data)

        except Exception as e:
            print(f"Error processing TextClip (PathID: {path_id}) for block {block_idx-1}: {e}")
            traceback.print_exc()
            continue

    return extracted_data

def parse_race_story(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as race story...")
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if "textData" in tree:
                    extracted_data = {"text_blocks": []}
                    for item in tree["textData"]:
                        if isinstance(item, dict) and "text" in item:
                            extracted_data["text_blocks"].append({
                                "block_index": item.get("key"),
                                "jpText": item.get("text"),
                                "enText": ""
                            })
                    return extracted_data
            except Exception as e:
                print(f"Error reading MonoBehaviour in race story: {e}")
    return None

def parse_race_story(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as race story...")
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if "textData" in tree:
                    extracted_data = {"text_blocks": []}
                    for item in tree["textData"]:
                        if isinstance(item, dict) and "text" in item:
                            extracted_data["text_blocks"].append({
                                "block_index": item.get("key"),
                                "jpText": item.get("text"),
                                "enText": ""
                            })
                    return extracted_data
            except Exception as e:
                print(f"Error reading MonoBehaviour in race story: {e}")
    return None

def parse_lyrics(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as lyrics...")
    for obj in env.objects:
        if obj.type.name == "TextAsset":
            try:
                tree = obj.read_typetree()
                script_content = tree.get("m_Script")

                if not script_content:
                    continue

                if isinstance(script_content, bytes):
                    script_content = script_content.decode('utf-8')

                lines = script_content.splitlines()[2:]
                reader = csv.reader(lines, skipinitialspace=True)

                extracted_data = {"text_blocks": []}
                for row in reader:
                    if not row or not row[0]: continue
                    time, text, *_ = row
                    extracted_data["text_blocks"].append({
                        "time": time,
                        "jpText": text.strip(),
                        "enText": ""
                    })

                if extracted_data["text_blocks"]:
                    return extracted_data

            except Exception as e:
                print(f"Error processing TextAsset for lyrics (PathID: {obj.path_id}): {e}")

    print("Warning: No valid TextAsset with lyrics content found in the bundle.")
    return None

def parse_home_timeline(env, manager: 'AssetManager', group_name: str | None = None):
    print("Parsing as home timeline...")

    timeline_data_asset = None
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if isinstance(tree, dict) and 'BlockList' in tree:
                    timeline_data_asset = tree
                    break
            except Exception:
                continue

    if not timeline_data_asset:
        print("Error: Could not find home timeline data asset in the bundle.")
        return None

    char_names = manager.get_text_data_category(6)

    extracted_data = {"text_blocks": []}

    for block_index, block in enumerate(timeline_data_asset.get("BlockList", [])):
        if not (isinstance(block, dict) and (text_track := block.get("TextTrack")) and isinstance(text_track, dict) and (clip_list := text_track.get("ClipList")) and isinstance(clip_list, list) and clip_list):
            continue

        clip_info = clip_list[0]
        path_id = clip_info.get('m_PathID') if isinstance(clip_info, dict) else getattr(clip_info, 'path_id', None)
        if path_id is None: continue

        text_clip_obj = next((obj for obj in env.objects if hasattr(obj, 'path_id') and obj.path_id == path_id), None)
        if not text_clip_obj: continue

        try:
            text_clip_data = text_clip_obj.read_typetree()
            if not isinstance(text_clip_data, dict) or not text_clip_data.get("Text"):
                continue

            jp_name = text_clip_data.get("Name", "")
            looked_up_name = char_names.get(int(jp_name)) if jp_name.isdigit() else None

            block_data = {
                "block_index": block_index,
                "jpName": looked_up_name or jp_name,
                "jpText": text_clip_data.get("Text", ""), "enText": "",
                "choices": [], "voiceIdx": text_clip_data.get("CueId"),
            }

            choice_list = text_clip_data.get("ChoiceDataList", [])
            if isinstance(choice_list, list):
                 for choice in filter(lambda c: isinstance(c, dict), choice_list):
                      block_data["choices"].append({"jpText": choice.get("Text", ""), "enText": "", "nextBlock": choice.get("NextBlock", 0)})

            extracted_data["text_blocks"].append(block_data)
        except Exception as e:
            print(f"Error processing TextClip data for home timeline (PathID: {path_id}): {e}")
            continue

    return extracted_data if extracted_data["text_blocks"] else None

def parse_preview(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as preview...")
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if "DataArray" in tree and isinstance(tree["DataArray"], list):
                    extracted_data = {"text_blocks": []}
                    for i, item in enumerate(tree["DataArray"]):
                        if isinstance(item, dict) and item.get("Text"):
                            extracted_data["text_blocks"].append({
                                "block_index": i,
                                "jpName": item.get("Name", ""), "enName": "",
                                "jpText": item.get("Text", ""), "enText": ""
                            })
                    return extracted_data if extracted_data["text_blocks"] else None
            except Exception as e:
                print(f"Error reading MonoBehaviour in preview: {e}")
    return None

def parse_generic(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as generic asset. No text extraction will be performed.")
    for obj in env.objects:
        if obj.type.name:
            return {"text_blocks": []}
    return None

def parse_uianimation(env, manager: 'AssetManager' = None, group_name: str | None = None):
    print("Parsing as UI animation...")

    main_mono = None
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            try:
                tree = obj.read_typetree()
                if "_motionParameterGroup" in tree:
                    main_mono = tree
                    break
            except Exception:
                continue

    if not main_mono:
        print("Warning: No MonoBehaviour with a '_motionParameterGroup' was found in this asset.")
        return None

    motion_param_list = main_mono.get("_motionParameterGroup", {}).get("_motionParameterList", [])
    if not motion_param_list:
        return {"text_blocks": []}

    motion_map = {motion.get("_id"): motion for motion in motion_param_list}
    motion_index_map = {motion.get("_id"): i for i, motion in enumerate(motion_param_list)}

    extracted_data = {"text_blocks": []}
    processed_motion_ids = set()

    def find_text_recursively(motion_id):
        if not motion_id or motion_id in processed_motion_ids:
            return

        processed_motion_ids.add(motion_id)
        motion_param = motion_map.get(motion_id)
        if not motion_param:
            return

        motion_idx = motion_index_map.get(motion_id, -1)

        direct_text_params = motion_param.get("_textParamList", [])
        for text_idx, text_param in enumerate(direct_text_params):
            if text_param and text_param.get("_text", "").strip():
                extracted_data["text_blocks"].append({
                    "motion_index": motion_idx,
                    "text_index": text_idx,
                    "motion_name": motion_param.get("_name"),
                    "object_name": text_param.get("_objectName"),
                    "jpText": text_param.get("_text"),
                    "enText": ""
                })

        for param_list_name in ["_objectParamList", "_planeParamList"]:
            for item_param in motion_param.get(param_list_name, []):
                child_motion_id = item_param.get("_childMotionID")
                if child_motion_id:
                    find_text_recursively(child_motion_id)

    root_motion_id = main_mono.get("_rootMotionID")
    if root_motion_id:
        find_text_recursively(root_motion_id)
    else:
        for motion_id in motion_map.keys():
            find_text_recursively(motion_id)

    return extracted_data

class AssetManager:
    def __init__(self, meta_path=META_DB_PATH, master_path=MASTER_DB_PATH, asset_dir=ASSET_DIR):
        self.asset_dir = str(asset_dir)
        self.meta_db = None
        self.master_db = None
        self.platform = "Windows"

        try:
            db_decryption_key = derive_db_decryption_key(DB_KEY, DB_BASE_KEY_FOR_DB_DECRYPT)
            hex_key = db_decryption_key.hex()

            meta_uri_string = f"file:{meta_path}?mode=ro&hexkey={hex_key}"
            self.meta_db = apsw.Connection(meta_uri_string,
                                          flags=apsw.SQLITE_OPEN_URI | apsw.SQLITE_OPEN_READONLY)
            cursor = self.meta_db.cursor()
            try:
                row = cursor.execute("SELECT n FROM c WHERE n = '//Windows' OR n = '//Android' LIMIT 1;").fetchone()
                if row and row[0]:
                    self.platform = row[0][2:]
                    print(f"Auto-detected platform: {self.platform}")
            except Exception as e:
                print(f"Could not auto-detect platform, defaulting to '{self.platform}'. Error: {e}")
            cursor.execute("PRAGMA cipher='chacha20'")
            cursor.execute("SELECT 1 FROM a LIMIT 1;")
            print("Meta DB connected and decrypted (using APSW).")

            master_uri_string = f"file:{master_path}?mode=ro"
            self.master_db = apsw.Connection(master_uri_string,
                                            flags=apsw.SQLITE_OPEN_URI | apsw.SQLITE_OPEN_READONLY)
            self.master_db.cursor().execute("SELECT 1 FROM text_data LIMIT 1;")
            print("Master DB connected.")

        except Exception as e:
            print(f"Error initializing AssetManager: {e}", file=sys.stderr)
            if self.meta_db: self.meta_db.close()
            if self.master_db: self.master_db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_asset_info(self, name_pattern):
        cursor = self.meta_db.cursor()

        try:
            exact_query = "SELECT h, e FROM a WHERE n = ?"
            row = cursor.execute(exact_query, (name_pattern,)).fetchone()
            if row:
                return row[0], int(row[1]) if row[1] else 0
        except Exception as e:
            print(f"Error during exact match query for '{name_pattern}': {e}")

        try:
            prefix_query = "SELECT h, e FROM a WHERE n LIKE ?"
            row = cursor.execute(prefix_query, (name_pattern + '%',)).fetchone()
            if row:
                return row[0], int(row[1]) if row[1] else 0
        except Exception as e:
            print(f"Error during prefix match query for '{name_pattern}': {e}")

        return None, None

    def get_asset_path(self, hash_str):
        asset_subdir = hash_str[:2]
        return os.path.join(self.asset_dir, asset_subdir, hash_str)

    def download_asset(self, hash_str: str, category: str = 'bundle'):
        if not AUTO_DOWNLOAD_ASSETS:
            print(f"Skipping download for {hash_str} because 'auto_download_assets' is false in config.")
            return False

        asset_path = self.get_asset_path(hash_str)
        asset_dir = os.path.dirname(asset_path)

        if category == 'bundle':
            url = f"https://prd-storage-game-umamusume.akamaized.net/dl/resources/{self.platform}/assetbundles/{hash_str[:2]}/{hash_str}"
        elif category == 'generic':
            url = f"https://prd-storage-game-umamusume.akamaized.net/dl/resources/Generic/{hash_str[:2]}/{hash_str}"
        else:
            print(f"ERROR: Unknown asset download category: '{category}'")
            return False

        print(f"Asset not found locally. Downloading from URL...")

        try:
            os.makedirs(asset_dir, exist_ok=True)
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(asset_path, 'wb') as f, tqdm(
                desc=f"Downloading {hash_str[:12]}...",
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    bar.update(size)

            print(f"Download complete: {asset_path}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error downloading asset {hash_str}: {e}")
            if os.path.exists(asset_path):
                os.remove(asset_path)
            return False

    def ensure_asset_is_ready(self, asset_name: str, category: str = 'bundle') -> Path | None:
        hash_str, _ = self.get_asset_info(asset_name)
        if not hash_str:
            print(f"WARNING: Asset '{asset_name}' not found in meta DB.")
            return None

        local_path = Path(self.get_asset_path(hash_str))

        if not local_path.exists():
            print(f"Local asset not found for '{asset_name}'. Attempting to download...")
            if not self.download_asset(hash_str, category=category):
                print(f"ERROR: Failed to download asset '{asset_name}'.")
                return None

        return local_path

    def load_bundle(self, asset_name):
        bundle_path = self.ensure_asset_is_ready(asset_name, category='bundle')
        if not bundle_path:
            print(f"Error: Could not find or download asset bundle: {asset_name}")
            return None

        _, encryption_key_int = self.get_asset_info(asset_name)

        try:
            raw_data = Path(bundle_path).read_bytes()

            processed_data = raw_data
            if encryption_key_int and encryption_key_int != 0 and len(raw_data) > 256:
                final_key = create_asset_final_key(encryption_key_int)
                processed_data = decrypt_asset_data(raw_data, final_key)

            env = UnityPy.load(processed_data)
            return env
        except Exception as e:
            print(f"Error loading/processing asset {asset_name}: {e}")
            return None

    @lru_cache(maxsize=32)
    def get_text_data_category(self, category_id):
        print(f"Loading text category {category_id} from DB...")
        cursor = self.master_db.cursor()
        query = 'SELECT "index", "text" FROM text_data WHERE "category" = ?'
        try:
            return {int(row[0]): row[1] for row in cursor.execute(query, (category_id,)).fetchall()}
        except Exception as e:
            print(f"Error querying master DB: {e}")
            return {}

    def query_asset_names(self, asset_type: str) -> list:
        print(f"Querying database for all '{asset_type}' assets...")
        cursor = self.meta_db.cursor()

        patterns = {
            "story": r"story/data/%/%/storytimeline_%%%%%%%%%",
            "home": r"home/data/%/%/hometimeline_%%_%%_%%%%%%%",
            "race": r"race/storyrace/text/storyrace_%%%%%%%%%",
            "lyrics": r"live/musicscores/m%%%%/m%%%%_lyrics",
            "preview": r"outgame/announceevent/loguiasset/ast_announce_event_log_ui_asset_%%%%%",
            "gacha-charaname": r"gacha/charaname/chara_name_%%%%_%",
            "gacha-supportname": r"gacha/supportname/support_name_%%%%%_%",
            "uianimation": r"uianimation/%",
            "generic": r"%"
        }
        pattern = patterns.get(asset_type)
        if not pattern:
            print(f"Warning: No query pattern defined for type '{asset_type}'.")
            return []

        query = r"SELECT n FROM a WHERE n LIKE ? ESCAPE '\';"
        try:
            rows = cursor.execute(query, (pattern,)).fetchall()
            names = [row[0] for row in rows]
            print(f"Found {len(names)} assets.")
            return names
        except Exception as e:
            print(f"Error querying meta DB for asset type '{asset_type}': {e}")
            return []

    def get_group_name(self, asset_type: str, group_id: str) -> str | None:
        category_id = None
        if asset_type == "story":
            prefix = group_id[:2]
            if prefix == "04":
                 category_id = 6
            elif prefix == "40":
                 category_id = 119
            elif prefix == "50":
                 category_id = 6
        elif asset_type == "home":
            category_id = 6

        if category_id:
            try:
                name_dict = self.get_text_data_category(category_id)
                return name_dict.get(int(group_id))
            except ValueError:
                print(f"Warning: Could not convert group_id '{group_id}' to int for lookup.")
                return None
        return None

    def close(self):
        if self.meta_db: self.meta_db.close()
        if self.master_db: self.master_db.close()
        print("Database connections closed.")