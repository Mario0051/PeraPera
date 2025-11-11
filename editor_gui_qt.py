import os
import sys
import json
from pathlib import Path
from functools import lru_cache
from collections import defaultdict
import traceback

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTextEdit, QLabel,
    QFormLayout, QToolBar, QFileDialog, QMessageBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QLineEdit, QTabWidget, QScrollArea, QDialog, QListWidget,
    QListWidgetItem, QHBoxLayout, QPushButton, QTreeWidgetItemIterator, QScroller, QFrame,
    QStatusBar, QCheckBox, QComboBox, QGroupBox, QDialogButtonBox, QMenu
)
from PySide6.QtGui import QAction, QCloseEvent, QPainter, QColor, QPen, QFontMetrics, QPaintEvent, QKeySequence, QContextMenuEvent
from PySide6.QtCore import Qt, QThread, Signal

from gui_font_manager import get_gui_font
from font_manager import get_text_width
from postprocess import POSTPROCESS_RULES

try:
    from PyCriCodecsEx.hca import HCACodec
    from PyCriCodecsEx.awb import AWB
    from PyCriCodecsEx.acb import ACB
except ImportError:
    print("CRITICAL: 'PyCriCodecsEx' not found. Voice playback will be disabled.")
    HCACodec = None

from asset_loader import AssetManager
from common import StoryId, MDB_TABLE_SCHEMAS
from mdb_dumper import dump_table
from builder import build_hachimi_directory
import autofill
from config import WORKSPACE_DIR, MOD_DIR, GAME_DATA_DIR
from extractor import extract_asset_data, PARSER_MAP
from playsound3 import playsound
from ipc_client import story_goto_block, reload_localized_data
from hachimi_converter import convert_to_hachimi_format
from mdb_patcher import generate_sql_patch
from mdb_dumper import dump_table
from gui_gacha_comment_tab import GachaCommentTab
from api import PeraPeraAPI
from gui_worker import Worker
from gui_find_replace import FindReplaceDialog
from gui_uianimation_tab import UIAnimationEditorTab

class RedlineTextEdit(QTextEdit):
    def __init__(self, max_pixel_width, parent=None):
        super().__init__(parent)
        self.max_pixel_width = max_pixel_width
        self.line_is_red = False

    def contextMenuEvent(self, event: QContextMenuEvent):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        color_action = menu.addAction("Add Color Tag...")
        color_action.triggered.connect(self._prompt_for_color)

        if not self.textCursor().hasSelection():
            color_action.setEnabled(False)

        menu.exec(event.globalPos())

    def _prompt_for_color(self):
        cursor = self.textCursor()
        if not cursor.hasSelection(): return

        color_id, ok = QInputDialog.getText(self, "Add Color Tag", "Enter Color ID (e.g., 1, 2):")
        if ok and color_id.isdigit():
            selected_text = cursor.selectedText()
            cursor.insertText(f"[c={color_id}]{selected_text}[/c]")

    def update_width_status(self, is_over_limit: bool):
        if self.line_is_red != is_over_limit:
            self.line_is_red = is_over_limit
            self.viewport().update()

    def paintEvent(self, event: QPaintEvent):
        super().paintEvent(event)

        if self.max_pixel_width > 0:
            painter = QPainter(self.viewport())
            color = QColor("red") if self.line_is_red else QColor("lightgray")
            pen = QPen(color, 2)
            painter.setPen(pen)

            x_position = self.max_pixel_width - self.horizontalScrollBar().value()
            painter.drawLine(x_position, 0, x_position, self.viewport().height())

class SpeakerManagerDialog(QDialog):
    def __init__(self, speakers: list, parent=None):
        super().__init__(parent)
        self.speakers = speakers
        self.setWindowTitle("Manage Speakers")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        self.line_edits = []

        for speaker in self.speakers:
            jp_name = speaker.get("jpName")
            en_name = speaker.get("enName")

            group_box = QGroupBox(jp_name)
            form_layout = QFormLayout(group_box)

            en_name_edit = QLineEdit(en_name)
            self.line_edits.append(en_name_edit)

            form_layout.addRow("English Name:", en_name_edit)
            self.scroll_layout.addWidget(group_box)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.layout.addWidget(self.scroll_area)
        self.layout.addWidget(self.buttons)

    def accept(self):
        for i, line_edit in enumerate(self.line_edits):
            self.speakers[i]["enName"] = line_edit.text()
        super().accept()

class AssetLoaderThread(QThread):
    item_loaded = Signal(list, dict)
    finished = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def stop(self):
        print("AssetLoaderThread: Stop requested.")
        self._is_running = False

    def run(self):
        print("AssetLoaderThread: Starting definitive asset scan...")
        try:
            with AssetManager() as self.manager:
                if not self._is_running: return
                self._cache_text_data_categories([6, 16, 92, 93, 94, 119, 181])

                if not self._is_running: return
                self._load_mdb_tables()

                if not self._is_running: return
                self._load_main_stories()

                if not self._is_running: return
                self._load_stories()

                if not self._is_running: return
                self._load_home_stories()

                if not self._is_running: return
                self._load_race_stories()

                if not self._is_running: return
                self._load_lyrics()

                if not self._is_running: return
                self._load_ui_animations()

            if self._is_running:
                print("AssetLoaderThread: Scan complete.")
                self.finished.emit(None)

        except Exception as e:
            if self._is_running:
                print(f"AssetLoaderThread: CRITICAL ERROR - {e}")
                import traceback
                traceback.print_exc()
                self.finished.emit(str(e))

    @lru_cache(maxsize=None)
    def _get_text_cat(self, cat_id):
        return self.manager.get_text_data_category(cat_id)

    def _cache_text_data_categories(self, cat_ids):
        for cat_id in cat_ids:
            self._get_text_cat(cat_id)

    def _get_group_name(self, category_id_str: str, group_id_str: str) -> str | None:
        cat_id, group_id = int(category_id_str), int(group_id_str)
        if cat_id in (4, 50): return self._get_text_cat(6).get(group_id)
        if cat_id == 40:
            name = self._get_text_cat(119).get(group_id)
            return name.replace("\\n", " ") if name else None
        return None

    def _get_story_name(self, category_id_str: str, story_id_str: str) -> str | None:
        cat_id, story_id = int(category_id_str), int(story_id_str)
        if cat_id == 4: return self._get_text_cat(92).get(story_id)
        return self._get_text_cat(181).get(story_id)

    def _load_and_emit_item(self, path_parts, item_data):
        if Path(item_data["workspace_path"]).exists():
            item_data["display_name"] += " [✓]"
        self.item_loaded.emit(path_parts, item_data)

    def _load_mdb_tables(self):
        print("AssetLoaderThread: Loading MDB Tables...")
        for table_name in MDB_TABLE_SCHEMAS.keys():
            if not self._is_running: return
            workspace_path = WORKSPACE_DIR / f"{table_name}_dict.json"
            self._load_and_emit_item(["Database Tables"], {
                "display_name": table_name,
                "workspace_path": str(workspace_path),
                "asset_name": table_name,
                "data_type": "mdb"
            })

    def _load_stories(self):
        print("AssetLoaderThread: Loading Stories (Optimized)...")
        category_names = { "04": "Character Stories", "40": "Training Scenario Events", "50": "Training Character Events" }
        cursor = self.manager.meta_db.cursor()

        rows = cursor.execute("SELECT n FROM a WHERE n LIKE 'story/data/__/____/storytimeline\\__________' ESCAPE '\\'").fetchall()

        story_tree = defaultdict(lambda: defaultdict(list))
        for (asset_name,) in rows:
            if not self._is_running: return
            parts = asset_name.split('/')
            cat_id, group_id = parts[2], parts[3]
            if cat_id in category_names:
                story_tree[cat_id][group_id].append(asset_name)

        for cat_id, groups in sorted(story_tree.items()):
            if not self._is_running: return
            cat_label = category_names[cat_id]
            for group_id, assets in sorted(groups.items()):
                if not self._is_running: return
                group_name = self._get_group_name(cat_id, group_id)
                group_label = f"{group_id} - {group_name}" if group_name else group_id
                for asset_name in sorted(assets):
                    if not self._is_running: return
                    story_id_str = asset_name.split('_')[-1]
                    story_name = self._get_story_name(cat_id, story_id_str)
                    story_part = story_id_str[6:]
                    story_label = f"Part {story_part} - {story_name}" if story_name else f"Part {story_part}"
                    sid = StoryId.parse_from_path("story", asset_name, group_name=group_name)
                    workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"
                    self._load_and_emit_item([cat_label, group_label], {
                        "display_name": story_label, "asset_name": asset_name, "workspace_path": str(workspace_path), "data_type": "story"
                    })

    def _load_main_stories(self):
        print("AssetLoaderThread: Loading Main Story...")
        cursor = self.manager.master_db.cursor()
        chapter_rows = cursor.execute('SELECT DISTINCT "part_id" FROM main_story_data ORDER BY "part_id"').fetchall()
        if not chapter_rows: return
        last_chapter = int(chapter_rows[-1][0])
        act_count = (last_chapter // 10) if last_chapter > 10 else 1
        chapter_names, episode_names = self._get_text_cat(93), self._get_text_cat(94)
        for i in range(1, act_count + 1):
            if not self._is_running: return
            act_label = f"Main Story Act {i}"
            act_chapter_rows = [r for r in chapter_rows if (i-1)*10 < int(r[0]) <= i*10]
            for (part_id,) in act_chapter_rows:
                if not self._is_running: return
                chapter_label = chapter_names.get(int(part_id), f"Chapter {part_id}")
                episode_rows = cursor.execute('SELECT "id", "episode_index" FROM main_story_data WHERE "part_id" = ? ORDER BY "episode_index"', (part_id,)).fetchall()
                for (ep_id, ep_idx) in episode_rows:
                    if not self._is_running: return
                    episode_label = f"E{ep_idx} - {episode_names.get(int(ep_id), 'Unknown')}"
                    story_parts = cursor.execute('SELECT "story_type_1", "story_id_1", "story_type_2", "story_id_2", "story_type_3", "story_id_3" FROM main_story_data WHERE "id" = ?', (ep_id,)).fetchone()
                    for j in range(0, 6, 2):
                        if not self._is_running: return
                        story_type, story_id = story_parts[j], story_parts[j+1]
                        if not story_type: continue
                        story_id_str, part_num = str(story_id).zfill(9), (j // 2) + 1
                        if story_type == 1:
                            asset_type, group1, group2 = "story", story_id_str[:2], story_id_str[2:6]
                            asset_name, display_name = f"story/data/{group1}/{group2}/storytimeline_{story_id_str}", f"Part {part_num} (Story)"
                        elif story_type == 3:
                            asset_type, asset_name, display_name = "race", f"race/storyrace/text/storyrace_{story_id_str}", f"Part {part_num} (Race)"
                        else: continue
                        sid = StoryId.parse_from_path(asset_type, asset_name)
                        workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"
                        self._load_and_emit_item([act_label, chapter_label, episode_label], {
                            "display_name": display_name, "asset_name": asset_name, "workspace_path": str(workspace_path), "data_type": asset_type
                        })

    def _load_home_stories(self):
        print("AssetLoaderThread: Loading Home Stories (Optimized)...")
        cursor = self.manager.meta_db.cursor()

        rows = cursor.execute("SELECT n FROM a WHERE n LIKE 'home/data/_____/__/hometimeline\\______\\___\\________' ESCAPE '\\'").fetchall()
        if not rows: return

        chara_names = self._get_text_cat(6)

        home_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for (asset_name,) in rows:
            if not self._is_running: return
            try:
                parts = asset_name.split('/')
                cat_id, group_id = parts[2], parts[3]
                story_id = asset_name.split('_')[-1]
                chara_id = story_id[:4]
                home_tree[cat_id][group_id][chara_id].append(asset_name)
            except IndexError:
                continue

        for cat_id, groups in sorted(home_tree.items()):
            if not self._is_running: return
            for group_id, charas in sorted(groups.items()):
                if not self._is_running: return
                group_label = f"Group {group_id}"
                for chara_id, assets in sorted(charas.items()):
                    if not self._is_running: return
                    chara_name = chara_names.get(int(chara_id))
                    chara_label = f"{chara_id} - {chara_name}" if chara_name else chara_id
                    for asset_name in sorted(assets):
                        if not self._is_running: return
                        story_id_str = asset_name.split('_')[-1]
                        sid = StoryId.parse_from_path("home", asset_name, group_name=chara_name)
                        workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"
                        self._load_and_emit_item(["Home Screen", cat_id, group_label, chara_label], {
                            "display_name": f"ID {story_id_str[4:]}", "asset_name": asset_name, "workspace_path": str(workspace_path), "data_type": "home"
                        })

    def _load_race_stories(self):
        print("AssetLoaderThread: Loading Race Stories...")
        rows = self.manager.meta_db.cursor().execute("SELECT n FROM a WHERE n LIKE 'race/storyrace/text/storyrace_%'").fetchall()
        if not rows: return

        for (asset_name,) in sorted(rows):
            if not self._is_running: return
            sid = StoryId.parse_from_path("race", asset_name)
            workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"
            self._load_and_emit_item(["Standalone Race Stories"], {
                "display_name": f"Race {sid.id}", "asset_name": asset_name, "workspace_path": str(workspace_path), "data_type": "race"
            })

    def _load_lyrics(self):
        print("AssetLoaderThread: Loading Lyrics...")
        rows = self.manager.meta_db.cursor().execute("SELECT n FROM a WHERE n LIKE 'live/musicscores/%\\_lyrics' ESCAPE '\\'").fetchall()
        if not rows: return
        song_names = self._get_text_cat(16)
        for (path,) in sorted(rows):
            if not self._is_running: return
            song_id_str = path.split("/")[-1][1:5]
            song_name = song_names.get(int(song_id_str))
            label = f"{song_id_str} - {song_name}" if song_name else song_id_str
            asset_name = f"live/musicscores/m{song_id_str}/m{song_id_str}_lyrics"
            sid = StoryId.parse_from_path("lyrics", asset_name)
            workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"
            self._load_and_emit_item(["Lyrics"], {
                "display_name": label, "asset_name": asset_name, "workspace_path": str(workspace_path), "data_type": "lyrics"
            })

    def _load_ui_animations(self):
        print("AssetLoaderThread: Loading UI Animations...")
        rows = self.manager.meta_db.cursor().execute("SELECT n FROM a WHERE n LIKE 'uianimation/%'").fetchall()
        if not rows: return

        for (asset_name,) in sorted(rows):
            if not self._is_running: return

            sid = StoryId.parse_from_path("uianimation", asset_name)
            workspace_path = WORKSPACE_DIR / sid.get_output_path() / f"{sid.get_filename_prefix()}.json"

            path_parts = ["UI Animations"] + list(Path(asset_name).parts[1:-1])

            self._load_and_emit_item(path_parts, {
                "display_name": Path(asset_name).name,
                "asset_name": asset_name,
                "workspace_path": str(workspace_path),
                "data_type": "uianimation"
            })

class AudioEngine:
    def __init__(self):
        self.cache_dir = Path("./perapera_cache/audio").resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_thread = None
        self.hca_base_key = 75923756697503

    def play_voice(self, cue_sheet_id: str, cue_id: int):
        if HCACodec is None: return
        if not cue_sheet_id: return

        voice_acb_name = f"sound/c/snd_voi_story_{cue_sheet_id}.acb"
        cached_wav_path = self.cache_dir / f"{cue_sheet_id}_{cue_id}.wav"

        if cached_wav_path.exists():
            self._play_sound_threaded(cached_wav_path)
            return

        print(f"Decoding voice: {voice_acb_name}, Cue ID: {cue_id}")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        manager = None
        try:
            manager = AssetManager()
            acb_path = manager.ensure_asset_is_ready(voice_acb_name, category='generic')

            if not acb_path or not acb_path.exists():
                raise FileNotFoundError(f"Voice archive '{voice_acb_name}' could not be found or downloaded.")

            awb_obj = None
            acb = ACB(str(acb_path))

            if acb.view.AwbFile:
                awb_stream = BytesIO(acb.view.AwbFile)
                awb_obj = AWB(awb_stream)
            else:
                voice_awb_name = f"sound/c/snd_voi_story_{cue_sheet_id}.awb"
                awb_path = manager.ensure_asset_is_ready(voice_awb_name, category='generic')
                if awb_path and awb_path.exists():
                    awb_obj = AWB(str(awb_path))

            if not awb_obj:
                raise FileNotFoundError("Could not locate the required internal or external AWB audio data.")

            awb_index = cue_id

            if awb_index >= awb_obj.numfiles:
                raise IndexError(
                    f"Data inconsistency: Story file is asking for audio track {awb_index}, "
                    f"but the corresponding AWB archive only contains {awb_obj.numfiles} tracks."
                )

            raw_hca_data = awb_obj.get_file_at(awb_index)

            codec = HCACodec(raw_hca_data, key=self.hca_base_key, subkey=awb_obj.subkey)
            wav_bytes = codec.decode()

            with open(cached_wav_path, 'wb') as f:
                f.write(wav_bytes)

            self._play_sound_threaded(cached_wav_path)

        except Exception as e:
            error_msg = f"Error decoding audio: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            QMessageBox.critical(None, "Audio Error", error_msg)
        finally:
            if manager:
                manager.close()
            QApplication.restoreOverrideCursor()

    def _play_sound_threaded(self, path):
        class AudioPlayer(QThread):
            def run(self):
                try:
                    playsound(str(path))
                except Exception as e:
                    print(f"Error playing sound: {e}")

        self.audio_player = AudioPlayer()
        self.audio_player.start()

class TextBlockWidget(QWidget):
    def __init__(self, index, block_data, story_asset_name, audio_engine, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(400)
        self.max_pixel_width = 720

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        jp_label = QLabel("JP:")
        self.jp_text_edit = QTextEdit()
        self.jp_text_edit.setPlainText(block_data.get("jpText", "").replace("\\n", "\n"))
        self.jp_text_edit.setReadOnly(True)
        self.jp_text_edit.setFont(get_gui_font(16))
        self.jp_text_edit.setMinimumHeight(120)
        self.jp_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.jp_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(jp_label)
        layout.addWidget(self.jp_text_edit)

        en_label = QLabel("EN:")
        self.en_text_edit = RedlineTextEdit(self.max_pixel_width)
        self.en_text_edit.setPlainText(block_data.get("enText", "").replace("\\n", "\n"))
        self.en_text_edit.setFont(get_gui_font(16))
        self.en_text_edit.setMinimumHeight(120)
        self.en_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.en_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(en_label)
        layout.addWidget(self.en_text_edit)

        self.en_text_edit.textChanged.connect(self.update_length_marker)
        self.update_length_marker()

    def update_length_marker(self):
        if self.max_pixel_width <= 0:
            return

        text = self.en_text_edit.toPlainText()
        font_metrics = self.en_text_edit.fontMetrics()
        longest_line_width = max((font_metrics.horizontalAdvance(line) for line in text.split('\n')), default=0)

        self.en_text_edit.update_width_status(longest_line_width > self.max_pixel_width)

    def get_en_text(self):
        return self.en_text_edit.toPlainText().replace('\n', '\\n')

    def set_en_text(self, text):
        self.en_text_edit.setPlainText(text.replace("\\n", "\n"))

class EditorTab(QWidget):
    dirty_state_changed = Signal(bool)

    def __init__(self, filepath: Path, asset_name: str, asset_type: str, display_name: str, audio_engine, tree_item, parent=None):
        super().__init__(parent)
        self.tree_item = tree_item
        self.audio_engine = audio_engine
        self.filepath = filepath
        self.workspace_path = filepath
        self.asset_name = asset_name
        self.asset_type = asset_type
        self.display_name = display_name
        self.block_widgets = []
        self._is_dirty = False
        self.story_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        formatting_bar = QHBoxLayout()
        bold_btn = QPushButton("Bold")
        bold_btn.setShortcut(QKeySequence.StandardKey.Bold)
        bold_btn.clicked.connect(lambda: self._toggle_text_format(bold=True))

        italic_btn = QPushButton("Italic")
        italic_btn.setShortcut(QKeySequence.StandardKey.Italic)
        italic_btn.clicked.connect(lambda: self._toggle_text_format(italic=True))

        formatting_bar.addWidget(bold_btn)
        formatting_bar.addWidget(italic_btn)
        formatting_bar.addStretch()

        top_bar_layout = QHBoxLayout()

        self.story_nav_combo = QComboBox()
        self.story_nav_combo.setMinimumHeight(45)
        self.story_nav_combo.currentIndexChanged.connect(self._on_block_selected)
        top_bar_layout.addWidget(self.story_nav_combo, stretch=1)

        self.goto_dialogue_btn = QPushButton("Next Dialogue")
        self.goto_dialogue_btn.setToolTip("Go to the next untranslated dialogue block.")
        self.goto_dialogue_btn.clicked.connect(self._action_goto_next_dialogue)
        top_bar_layout.addWidget(self.goto_dialogue_btn)

        self.goto_choice_btn = QPushButton("Next Choice")
        self.goto_choice_btn.setToolTip("Go to the next block with an untranslated choice.")
        self.goto_choice_btn.clicked.connect(self._action_goto_next_choice)
        top_bar_layout.addWidget(self.goto_choice_btn)

        layout.addLayout(top_bar_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        QScroller.grabGesture(scroll_area.viewport(), QScroller.ScrollerGestureType.TouchGesture)

        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)

        self.scroll_layout = QVBoxLayout(scroll_content_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_layout.addLayout(formatting_bar)

        layout.addWidget(scroll_area)

        bottom_bar_layout = QHBoxLayout()

        speaker_btn = QPushButton("Manage Speakers")
        speaker_btn.clicked.connect(self._action_manage_speakers)
        bottom_bar_layout.addWidget(speaker_btn)

        bottom_bar_layout.addStretch()

        self.sync_game_check = QCheckBox("Sync Game")
        self.sync_game_check.setToolTip("Automatically sync to game when changing blocks.")
        bottom_bar_layout.addWidget(self.sync_game_check)

        goto_game_btn = QPushButton("Goto Game")
        goto_game_btn.setToolTip("Tell the running game to jump to this story block.")
        goto_game_btn.clicked.connect(self._action_goto_game)
        bottom_bar_layout.addWidget(goto_game_btn)

        layout.addLayout(bottom_bar_layout)

    def _toggle_text_format(self, bold=False, italic=False):
        if not self.block_widgets: return
        editor = self.block_widgets[0].en_text_edit

        cursor = editor.textCursor()
        if not cursor.hasSelection(): return

        current_format = cursor.charFormat()

        if bold:
            current_format.setFontWeight(QFont.Weight.Bold if current_format.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)
        if italic:
            current_format.setFontItalic(not current_format.fontItalic())

        cursor.mergeCharFormat(current_format)

    def load(self):
        if not self.filepath.exists():
            if not self.asset_name or not self.asset_type:
                QMessageBox.critical(self, "Cannot Extract", "File does not exist and cannot be extracted because asset information is missing.")
                return False

            reply = QMessageBox.question(self, "Extract New File?", f"The file does not exist:\n\n{self.filepath.name}\n\nWould you like to extract it now?")
            if reply != QMessageBox.StandardButton.Yes:
                return False
            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                manager = AssetManager()
                workspace_data = extract_asset_data(manager, self.asset_type, self.asset_name, workspace_path=None)
                manager.close()

                if not workspace_data:
                    raise RuntimeError("Extractor returned no data.")

                self.filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(self.filepath, 'w', encoding='utf-8') as f:
                    json.dump(workspace_data, f, indent=4, ensure_ascii=False)

                mod_path = MOD_DIR / "assets" / f"{self.asset_name}.json"
                mod_path.parent.mkdir(parents=True, exist_ok=True)

                hachimi_data = convert_to_hachimi_format(workspace_data)
                with open(mod_path, 'w', encoding='utf-8') as f:
                    json.dump(hachimi_data, f, indent=4, ensure_ascii=False)

                QApplication.restoreOverrideCursor()
            except Exception as e:
                QApplication.restoreOverrideCursor()
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Extraction Failed", f"Could not extract asset data:\n{e}")
                return False

        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)

        self.story_data = data

        self.populate_editor(data.get("text_blocks", []))
        return True

    def _mark_as_dirty(self):
        if not self._is_dirty:
            self._is_dirty = True
            self.dirty_state_changed.emit(True)

    def is_dirty(self):
        return self._is_dirty

    def _on_block_selected(self, index: int):
        if index == -1:
            while self.scroll_layout.count():
                child = self.scroll_layout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            self.block_widgets = []
            return

        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        block_data = data["text_blocks"][index]

        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        widget = TextBlockWidget(index, block_data, self.asset_name, self.audio_engine)
        widget.en_text_edit.textChanged.connect(self._mark_as_dirty)
        self.scroll_layout.addWidget(widget)
        self.block_widgets = [widget]

        if self.sync_game_check.isChecked():
            self._action_goto_game()

    def populate_editor(self, text_blocks):
        self.story_nav_combo.blockSignals(True)
        self.story_nav_combo.clear()

        for i, block in enumerate(text_blocks):
            jp_name = block.get("jpName", "Narrator")
            jp_text_preview = block.get("jpText", "").replace("\\n", " ").strip()[:40]
            self.story_nav_combo.addItem(f"{i:03d}: [{jp_name}] {jp_text_preview}...")
            if block.get("enText", "").strip():
                self.story_nav_combo.model().item(i).setForeground(QColor("gray"))

        self.story_nav_combo.blockSignals(False)

        if text_blocks:
            self.story_nav_combo.setCurrentIndex(0)
            self._on_block_selected(0)

        self._update_goto_buttons()

    def save(self):
        if not self.story_data: return False

        self._update_in_memory_data_from_widget()

        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.story_data, f, indent=4, ensure_ascii=False)

            asset_name = self.story_data.get("asset_name")
            if not asset_name:
                QMessageBox.critical(self, "Save Error", "Could not find 'asset_name'...")
                return False

            mod_path = MOD_DIR / "assets" / f"{asset_name}.json"
            mod_path.parent.mkdir(parents=True, exist_ok=True)

            hachimi_data = convert_to_hachimi_format(self.story_data)
            with open(mod_path, 'w', encoding='utf-8') as f:
                json.dump(hachimi_data, f, indent=4, ensure_ascii=False)

            self._is_dirty = False
            self.dirty_state_changed.emit(False)
            self._update_goto_buttons()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save the file:\n{e}")
            return False

    def _find_next_untranslated_block(self, test_func):
        if not self.story_data or not self.block_widgets:
            return None

        current_idx = self.story_nav_combo.currentIndex()
        num_blocks = len(self.story_data["text_blocks"])

        indices_to_check = list(range(current_idx + 1, num_blocks)) + list(range(current_idx + 1))

        for i in indices_to_check:
            block = self.story_data["text_blocks"][i]
            if test_func(block):
                return i
        return None

    def _action_goto_next_dialogue(self):
        self._update_in_memory_data_from_widget()

        def test(block):
            return block.get("jpText") and not block.get("enText", "").strip()

        next_idx = self._find_next_untranslated_block(test)
        if next_idx is not None:
            self.story_nav_combo.setCurrentIndex(next_idx)

    def _action_goto_next_choice(self):
        self._update_in_memory_data_from_widget()

        def test(block):
            for choice in block.get("choices", []):
                if choice.get("jpText") and not choice.get("enText", "").strip():
                    return True
            return False

        next_idx = self._find_next_untranslated_block(test)
        if next_idx is not None:
            self.story_nav_combo.setCurrentIndex(next_idx)

    def _update_goto_buttons(self):
        dialogue_next = self._find_next_untranslated_block(lambda b: b.get("jpText") and not b.get("enText"))
        self.goto_dialogue_btn.setEnabled(dialogue_next is not None)

        choice_next = self._find_next_untranslated_block(lambda b: any(c.get("jpText") and not c.get("enText") for c in b.get("choices", [])))
        self.goto_choice_btn.setEnabled(choice_next is not None)

    def _action_manage_speakers(self):
        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            full_data = json.load(f)

        speakers = {}
        for i, block in enumerate(full_data["text_blocks"]):
            jp_name = block.get("jpName")
            if jp_name:
                if jp_name not in speakers:
                    speakers[jp_name] = {"jpName": jp_name, "enName": block.get("enName", ""), "indices": []}
                speakers[jp_name]["indices"].append(i)

        speaker_list = list(speakers.values())
        if not speaker_list:
            QMessageBox.information(self, "No Speakers", "No speakers found in this story file.")
            return

        dialog = SpeakerManagerDialog(speaker_list, self)
        if dialog.exec():
            for speaker_data in dialog.speakers:
                for block_idx in speaker_data["indices"]:
                    full_data["text_blocks"][block_idx]["enName"] = speaker_data["enName"]

            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(full_data, f, indent=4, ensure_ascii=False)

            self._mark_as_dirty()
            self.populate_editor(full_data.get("text_blocks", []))

    def _action_goto_game(self):
        current_idx = self.story_nav_combo.currentIndex()
        if current_idx == -1: return

        with open(self.filepath, 'r', encoding='utf-8-sig') as f:
            full_data = json.load(f)

        block = full_data["text_blocks"][current_idx]
        block_index_in_story = block.get("block_index")

        if block_index_in_story is not None:
            story_goto_block(block_index_in_story)
        else:
            QMessageBox.warning(self, "Missing Data", "This story block is missing the 'block_index' field.")

    def _update_in_memory_data_from_widget(self):
        if not self.story_data or not self.block_widgets:
            return

        current_idx = self.story_nav_combo.currentIndex()
        if current_idx == -1:
            return

        current_widget = self.block_widgets[0]
        self.story_data["text_blocks"][current_idx]["enText"] = current_widget.get_en_text()

class SearchWorker(QThread):
    result_found = Signal(dict)
    finished = Signal()

    def __init__(self, search_term, parent=None):
        super().__init__(parent)
        self.search_term = search_term

    def run(self):
        from find import search_content_generator
        for result in search_content_generator(WORKSPACE_DIR, self.search_term, case_sensitive=False):
            self.result_found.emit(result)
        self.finished.emit()

class SearchResultWidget(QWidget):
    def __init__(self, result_data, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)

        filepath = Path(result_data["filepath"])

        try:
            relative_path_str = str(filepath.relative_to(WORKSPACE_DIR))
        except ValueError:
            relative_path_str = filepath.name

        path_label = QLabel(f"<b>{relative_path_str}</b>")

        content_label = QLabel(f"<b>{result_data['jpName']}:</b> {result_data['jpText']}")
        content_label.setWordWrap(True)

        layout.addWidget(path_label)
        layout.addWidget(content_label)

class SearchDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Find in Files")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter Japanese text to find...")
        self.search_input.returnPressed.connect(self.start_search)
        layout.addWidget(self.search_input)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_result_activated)
        layout.addWidget(self.results_list)

        self.status_label = QLabel("Ready.")
        layout.addWidget(self.status_label)

        self.search_worker = None

    def start_search(self):
        search_term = self.search_input.text()
        if not search_term or len(search_term) < 2:
            self.status_label.setText("Please enter at least 2 characters.")
            return

        self.results_list.clear()
        self.status_label.setText("Searching...")

        self.search_worker = SearchWorker(search_term)
        self.search_worker.result_found.connect(self.add_result)
        self.search_worker.finished.connect(self.finish_search)
        self.search_worker.start()

    def add_result(self, result_data):
        item_widget = SearchResultWidget(result_data)
        list_item = QListWidgetItem(self.results_list)
        list_item.setSizeHint(item_widget.sizeHint())
        list_item.setData(Qt.ItemDataRole.UserRole, result_data)
        self.results_list.addItem(list_item)
        self.results_list.setItemWidget(list_item, item_widget)

    def finish_search(self):
        count = self.results_list.count()
        self.status_label.setText(f"Found {count} result(s).")

    def on_result_activated(self, item):
        result_data = item.data(Qt.ItemDataRole.UserRole)
        filepath = Path(result_data["filepath"])

        iterator = QTreeWidgetItemIterator(self.main_window.asset_tree)
        found_item_data = None
        while iterator.value():
            tree_item = iterator.value()
            item_data = tree_item.data(0, Qt.ItemDataRole.UserRole)
            if item_data and Path(item_data["workspace_path"]).resolve() == filepath.resolve():
                found_item_data = item_data
                break
            iterator += 1

        if found_item_data:
            self.main_window.open_file(filepath, found_item_data.get("asset_name"), found_item_data.get("data_type"))
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Could not find this file in the asset tree.")

class MdbEditorTab(QWidget):
    dirty_state_changed = Signal(bool)

    def __init__(self, table_name, display_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.asset_name = table_name
        self.asset_type = "mdb"
        self.display_name = display_name
        self.workspace_path = WORKSPACE_DIR / f"{self.table_name}_dict.json"
        self._is_dirty = False
        self.original_data = {}
        self.translated_data = {}

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Entries")
        self.tree.currentItemChanged.connect(self.on_item_changed)
        splitter.addWidget(self.tree)

        editor_widget = QWidget()
        form_layout = QFormLayout(editor_widget)
        self.jp_text = QTextEdit()
        self.jp_text.setReadOnly(True)
        self.en_text = QTextEdit()
        self.en_text.textChanged.connect(self.on_en_text_changed)
        form_layout.addRow("Japanese:", self.jp_text)
        form_layout.addRow("English:", self.en_text)
        splitter.addWidget(editor_widget)
        splitter.setSizes([400, 600])

        self.current_item_path = None

        self.jp_text.setFont(get_gui_font(16))
        self.en_text.setFont(get_gui_font(16))

    def on_en_text_changed(self):
        if self.current_item_path is None: return

        current_level = self.translated_data
        for key in self.current_item_path[:-1]:
            if key not in current_level:
                current_level[key] = {}
            current_level = current_level[key]

        current_level[self.current_item_path[-1]] = self.en_text.toPlainText()
        self._mark_as_dirty()

    def on_item_changed(self, item, previous):
        if not item or not item.childCount() == 0:
            self.jp_text.clear()
            self.en_text.clear()
            self.en_text.setReadOnly(True)
            self.current_item_path = None
            return

        self.en_text.setReadOnly(False)
        item_path = item.data(0, Qt.ItemDataRole.UserRole)
        self.current_item_path = item_path

        jp_val = self.original_data
        for key in item_path: jp_val = jp_val.get(key, {})

        en_val = self.translated_data
        for key in item_path:
             if hasattr(en_val, 'get'):
                en_val = en_val.get(key, "")
             else:
                en_val = ""
                break

        self.jp_text.setText(str(jp_val))
        self.en_text.blockSignals(True)
        self.en_text.setText(str(en_val))
        self.en_text.blockSignals(False)

    def load(self):
        if not self.workspace_path.exists():
            reply = QMessageBox.question(self, "Dump Table?", f"'{self.workspace_path.name}' does not exist. Would you like to dump it from the database now?")
            if reply == QMessageBox.StandardButton.Yes:
                master_db_path = GAME_DATA_DIR / "master" / "master.mdb"
                dump_table(master_db_path, self.table_name, WORKSPACE_DIR)
            else:
                return False

        with open(self.workspace_path, 'r', encoding='utf-8-sig') as f:
            self.translated_data = json.load(f)

        try:
            with AssetManager() as manager:
                schema = MDB_TABLE_SCHEMAS[self.table_name]
                cols = '", "'.join(schema)
                rows = manager.master_db.cursor().execute(f'SELECT "{cols}" FROM {self.table_name}').fetchall()

                self.original_data = {}
                if len(schema) > 2:
                    for row in rows:
                        current_level = self.original_data
                        for key in row[:-2]:
                            if key not in current_level: current_level[key] = {}
                            current_level = current_level[key]
                        current_level[row[-2]] = row[-1]
                else:
                    self.original_data = {row[0]: row[1] for row in rows}
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Could not load original data from master.mdb:\n{e}")
            return False

        self.populate_tree()
        return True

    def populate_tree(self):
        self.tree.clear()

        def recursive_populate(parent_item, data, path):
            for key, value in sorted(data.items(), key=lambda x: str(x[0])):
                new_path = path + [key]
                if isinstance(value, dict):
                    child_item = QTreeWidgetItem(parent_item, [str(key)])
                    recursive_populate(child_item, value, new_path)
                else:
                    child_item = QTreeWidgetItem(parent_item, [str(key)])
                    child_item.setData(0, Qt.ItemDataRole.UserRole, new_path)

        recursive_populate(self.tree, self.original_data, [])

    def save(self):
        try:
            with open(self.workspace_path, 'w', encoding='utf-8') as f:
                json.dump(self.translated_data, f, indent=4, ensure_ascii=False)

            patch_path = WORKSPACE_DIR / f"{self.table_name}_patch.sql"
            if generate_sql_patch(self.table_name, self.workspace_path, patch_path):
                print(f"Successfully generated SQL patch: {patch_path}")
            else:
                QMessageBox.warning(self, "Patch Failed", "Could not generate the SQL patch file.")

            self._is_dirty = False
            self.dirty_state_changed.emit(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save MDB data: {e}")
            return False

    def is_dirty(self): return self._is_dirty
    def _mark_as_dirty(self):
        if not self._is_dirty:
            self._is_dirty = True
            self.dirty_state_changed.emit(True)

class PeraPeraQTGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PeraPera GUI Editor"); self.setGeometry(100, 100, 1200, 800)
        self.open_tabs = {}
        self.tree_nodes = {}
        self.worker = None

        self.audio_engine = AudioEngine()

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        open_action = QAction("Open File...", self)
        open_action.triggered.connect(self.open_file_dialog)
        toolbar.addAction(open_action)

        self.save_action = QAction("Save", self)
        self.save_action.triggered.connect(self.save_current_file)
        self.save_action.setEnabled(False)
        toolbar.addAction(self.save_action)

        save_all_action = QAction("Save All", self)
        save_all_action.triggered.connect(self.save_all_files)
        toolbar.addAction(save_all_action)

        toolbar.addSeparator()

        search_action = QAction("Search...", self)
        search_action.triggered.connect(self.open_search_dialog)
        toolbar.addAction(search_action)

        find_replace_action = QAction("Find and Replace...", self)
        find_replace_action.triggered.connect(self._action_open_find_replace)
        toolbar.addAction(find_replace_action)

        hot_reload_action = QAction("Hot Reload", self)
        hot_reload_action.setToolTip("Tell Hachimi to reload all translation files from disk.")
        hot_reload_action.triggered.connect(reload_localized_data)
        toolbar.addAction(hot_reload_action)

        toolbar.addSeparator()

        dump_action = QAction("Dump All Tables", self)
        dump_action.setToolTip("Dumps all text tables from master.mdb to your workspace.")
        dump_action.triggered.connect(self._action_dump_all_tables)
        toolbar.addAction(dump_action)

        autofill_action = QAction("Run All Autofills", self)
        autofill_action.setToolTip("Runs all available autofill routines on your workspace.")
        autofill_action.triggered.connect(self._action_run_all_autofills)
        toolbar.addAction(autofill_action)

        build_action = QAction("Build for Hachimi", self)
        build_action.setToolTip(f"Builds a Hachimi-ready 'localized_data' folder in '{MOD_DIR}'.")
        build_action.triggered.connect(self._action_build_hachimi)
        toolbar.addAction(build_action)

        self.file_label = QLabel("  No file opened.")
        toolbar.addWidget(self.file_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        explorer_container = QWidget()
        explorer_layout = QVBoxLayout(explorer_container)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search assets...")
        self.search_bar.textChanged.connect(self.filter_tree)
        explorer_layout.addWidget(self.search_bar)
        self.asset_tree = QTreeWidget()
        self.asset_tree.setHeaderLabel("Assets")
        self.asset_tree.itemActivated.connect(self.open_file_from_tree)
        explorer_layout.addWidget(self.asset_tree)
        splitter.addWidget(explorer_container)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        splitter.addWidget(self.tab_widget)

        self.gacha_comment_tab = GachaCommentTab()
        self.tab_widget.addTab(self.gacha_comment_tab, "Gacha Comments")

        splitter.setSizes([300, 900])

        self.asset_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.asset_tree.customContextMenuRequested.connect(self._on_asset_tree_context_menu)

        self.setStatusBar(QStatusBar(self))

        self.asset_tree.clear()
        loading_item = QTreeWidgetItem(self.asset_tree, ["Loading assets..."])
        loading_item.setDisabled(True)

        self.asset_loader_thread = AssetLoaderThread()
        self.asset_loader_thread.item_loaded.connect(self.add_tree_item)
        self.asset_loader_thread.finished.connect(self.on_asset_load_finished)
        self.asset_loader_thread.start()

    def _action_open_find_replace(self):
        dialog = FindReplaceDialog(WORKSPACE_DIR, self)
        dialog.exec()

    def _on_asset_tree_context_menu(self, position):
        item = self.asset_tree.itemAt(position)
        if not item: return

        menu = QMenu()

        action_open_explorer = menu.addAction("Open Containing Folder")
        action_open_explorer.triggered.connect(lambda: self._action_open_in_explorer(item))

        menu.exec(self.asset_tree.viewport().mapToGlobal(position))

    def _action_open_in_explorer(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.ItemDataRole.UserRole)

        if not data or "workspace_path" not in data:
            iterator = QTreeWidgetItemIterator(item)
            while iterator.value():
                child_item = iterator.value()
                child_data = child_item.data(0, Qt.ItemDataRole.UserRole)
                if child_data and "workspace_path" in child_data:
                    data = child_data
                    break
                iterator += 1

        if not data:
            self.statusBar().showMessage("Cannot open folder for a category with no extractable items.", 4000)
            return

        filepath = Path(data["workspace_path"])
        folder_path = filepath.parent

        if not folder_path.exists():
            QMessageBox.information(self, "Folder Not Found",
                                    f"The folder does not exist yet because this asset has not been extracted.\n\nExpected path: {folder_path}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Folder", f"Could not open the file explorer:\n{e}")

    def _run_task(self, func, *args, **kwargs):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "A background task is already running.")
            return

        self.worker = Worker(func, *args, **kwargs)
        self.worker.finished.connect(self._on_task_finished)

        self.statusBar().showMessage(f"Running: {func.__name__}...")
        self.worker.start()

    def _on_task_finished(self, message: str):
        self.statusBar().showMessage(message.split('\n')[0], 5000)
        if "failed" in message:
            QMessageBox.critical(self, "Task Failed", message)
        else:
            QMessageBox.information(self, "Task Complete", message)
        self.worker = None

    def _action_dump_all_tables(self):
        def task():
            master_db_path = GAME_DATA_DIR / "master" / "master.mdb"
            for table_name in MDB_TABLE_SCHEMAS.keys():
                print(f"Dumping table: {table_name}...")
                dump_table(master_db_path, table_name, WORKSPACE_DIR)

        task.__name__ = "Dump All Tables"
        self._run_task(task)

    def _action_build_hachimi(self):
        def task():
            build_hachimi_directory(WORKSPACE_DIR, MOD_DIR, clean=False)

        task.__name__ = "Build for Hachimi"
        self._run_task(task)

    def _action_run_all_autofills(self):
        def task():
            with PeraPeraAPI() as pp_api:
                autofill._autofill_pieces(pp_api)
                autofill._autofill_duplicates(pp_api)
                autofill._autofill_birthdays(pp_api)
                autofill._autofill_support_card_combos(pp_api)
                autofill._autofill_race_commentary(pp_api)
                autofill._autofill_chara_secret_headers(pp_api)
                autofill._autofill_support_effects(pp_api)

        task.__name__ = "Run All Autofills"
        self._run_task(task)

    def add_tree_item(self, path_parts, item_data):
        parent = self.asset_tree.invisibleRootItem()
        current_path = ""

        for part in path_parts:
            current_path += f"/{part}"
            if current_path in self.tree_nodes:
                parent = self.tree_nodes[current_path]
            else:
                new_parent = QTreeWidgetItem(parent, [part])
                self.tree_nodes[current_path] = new_parent
                parent = new_parent

        child_item = QTreeWidgetItem(parent, [item_data["display_name"]])
        child_item.setData(0, Qt.ItemDataRole.UserRole, item_data)

    def on_asset_load_finished(self, error_str):
        if self.asset_tree.topLevelItemCount() > 0:
            self.asset_tree.takeTopLevelItem(0)
        if error_str:
            QTreeWidgetItem(self.asset_tree, [f"Error loading assets:", error_str])

    def open_search_dialog(self):
        dialog = SearchDialog(self)
        dialog.exec()

    def open_file_from_tree(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return

        asset_type = data.get("data_type")
        filepath = Path(data["workspace_path"])
        asset_name = data["asset_name"]
        display_name = data["display_name"]

        if asset_type == "mdb":
            self.open_mdb_tab(asset_name, filepath, display_name)
        elif asset_type == "uianimation":
            self.open_uianimation_tab(filepath, asset_name, display_name, item)
        else:
            self.open_story_tab(filepath, asset_name, asset_type, display_name, item)

    def open_story_tab(self, filepath: Path, asset_name: str, asset_type: str, display_name: str, tree_item: QTreeWidgetItem):
        tab_key = f"{filepath.resolve()}_{display_name}"

        if tab_key in self.open_tabs:
            self.tab_widget.setCurrentIndex(self.open_tabs[tab_key])
            return

        new_tab = EditorTab(filepath, asset_name, asset_type, display_name, self.audio_engine, tree_item)
        new_tab.dirty_state_changed.connect(self.on_tab_dirty_state_changed)
        if new_tab.load():
            index = self.tab_widget.addTab(new_tab, display_name)
            filepath_str = str(filepath.resolve())
            self.tab_widget.setTabToolTip(index, filepath_str)
            self.tab_widget.setCurrentIndex(index)
            self.open_tabs[tab_key] = index
            self.sync_tree_to_current_tab()

    def open_mdb_tab(self, table_name: str, filepath: Path, display_name: str):
        tab_key = str(filepath.resolve())
        if tab_key in self.open_tabs:
            self.tab_widget.setCurrentIndex(self.open_tabs[tab_key])
            return

        new_tab = MdbEditorTab(table_name, display_name)
        new_tab.dirty_state_changed.connect(self.on_tab_dirty_state_changed)
        if new_tab.load():
            index = self.tab_widget.addTab(new_tab, f"DB: {table_name}")
            self.tab_widget.setTabToolTip(index, str(filepath))
            self.tab_widget.setCurrentIndex(index)
            self.open_tabs[tab_key] = index
            self.sync_tree_to_current_tab()

    def open_uianimation_tab(self, filepath: Path, asset_name: str, display_name: str, tree_item: QTreeWidgetItem):
        tab_key = str(filepath.resolve())
        if tab_key in self.open_tabs:
            self.tab_widget.setCurrentIndex(self.open_tabs[tab_key])
            return

        new_tab = UIAnimationEditorTab(filepath, asset_name, display_name, tree_item)
        new_tab.dirty_state_changed.connect(self.on_tab_dirty_state_changed)
        if new_tab.load():
            index = self.tab_widget.addTab(new_tab, display_name)
            self.tab_widget.setTabToolTip(index, str(filepath))
            self.tab_widget.setCurrentIndex(index)
            self.open_tabs[tab_key] = index
            self.sync_tree_to_current_tab()

    def filter_tree(self, text):
        iterator = QTreeWidgetItemIterator(self.asset_tree)
        while iterator.value():
            item = iterator.value()
            is_match = text.lower() in item.text(0).lower()
            item.setHidden(not is_match)
            if is_match:
                parent = item.parent()
                while parent:
                    parent.setHidden(False)
                    parent = parent.parent()
            iterator += 1

    def open_file_dialog(self):
        filepath_str, _ = QFileDialog.getOpenFileName(self, "Open Translation File", str(WORKSPACE_DIR), "JSON Files (*.json)")
        if filepath_str:
            self.open_file(Path(filepath_str))

    def open_file(self, filepath: Path, asset_name: str = None, asset_type: str = None):
        if not asset_type:
            try:
                derived_type = filepath.relative_to(WORKSPACE_DIR).parts[0]
                if derived_type in PARSER_MAP:
                    asset_type = derived_type
            except (ValueError, IndexError):
                pass

        if not asset_type:
            asset_type = "story"

        if not asset_name and not filepath.exists():
            QMessageBox.warning(self, "Unsupported Action", "Cannot create a new file via the 'Open File...' dialog.\nPlease extract it from the Asset Tree first.")
            return

        display_name = filepath.name
        self.open_story_tab(filepath, asset_name, asset_type, display_name)

    def on_tab_dirty_state_changed(self, is_dirty):
        tab = self.sender()
        if not tab:
            return

        index = self.tab_widget.indexOf(tab)
        if index == -1:
            return

        if hasattr(tab, 'display_name'):
            tab_text = tab.display_name
            self.tab_widget.setTabText(index, f"{tab_text}*" if is_dirty else tab_text)

        if hasattr(tab, 'tree_item') and tab.tree_item:
            tree_item = tab.tree_item
            tree_text = tree_item.text(0)

            clean_text = tree_text.replace(" *", "").strip()

            if is_dirty:
                tree_item.setText(0, f"{clean_text} *")
            else:
                tree_item.setText(0, clean_text)

    def save_current_file(self):
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'save'):
            if current_tab.save():
                QMessageBox.information(self, "Success", "File saved successfully.")

    def save_all_files(self):
        saved_count = 0
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'is_dirty') and tab.is_dirty():
                if hasattr(tab, 'save') and tab.save():
                    saved_count += 1

        if saved_count > 0:
            QMessageBox.information(self, "Success", f"Saved {saved_count} file(s).")

    def close_tab(self, index):
        tab_to_close = self.tab_widget.widget(index)

        if hasattr(tab_to_close, 'is_dirty') and tab_to_close.is_dirty():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"You have unsaved changes in {tab_to_close.display_name}.\n\nDo you want to save them?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                if not tab_to_close.save():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.tab_widget.removeTab(index)
        self.rebuild_open_tabs_dict()

    def rebuild_open_tabs_dict(self):
        self.open_tabs.clear()
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'workspace_path'):
                 if isinstance(tab, EditorTab):
                     key = f"{tab.workspace_path.resolve()}_{tab.display_name}"
                 else:
                     key = str(tab.workspace_path.resolve())
                 self.open_tabs[key] = i

    def closeEvent(self, event: QCloseEvent):
        if self.asset_loader_thread.isRunning():
            print("Shutdown: Asset loader is still running. Requesting stop...")
            self.asset_loader_thread.stop()
            self.asset_loader_thread.wait()
            print("Shutdown: Asset loader finished.")

        dirty_tabs = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'is_dirty') and tab.is_dirty():
                dirty_tabs.append(self.tab_widget.tabText(i))

        if dirty_tabs:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before exiting?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save_all_files()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def on_tab_changed(self, index):
        is_tab_open = index != -1
        self.save_action.setEnabled(is_tab_open)
        if is_tab_open:
            current_tab = self.tab_widget.currentWidget()
            if hasattr(current_tab, 'display_name'):
                self.file_label.setText(f"  Editing: {current_tab.display_name}")
            self.sync_tree_to_current_tab()
        else:
            self.file_label.setText("  No file opened.")

    def sync_tree_to_current_tab(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab or not hasattr(current_tab, 'asset_name'):
            return

        iterator = QTreeWidgetItemIterator(self.asset_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if (data and
                data.get("asset_name") == current_tab.asset_name and
                data.get("data_type") == current_tab.asset_type and
                data.get("display_name") == current_tab.display_name):

                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()

                self.asset_tree.setCurrentItem(item)
                self.asset_tree.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)
                return
            iterator += 1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PeraPeraQTGUI()
    window.show()
    sys.exit(app.exec())