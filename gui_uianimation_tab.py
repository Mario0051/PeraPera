import json
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QSplitter, QTreeWidget,
                               QTreeWidgetItem, QFormLayout, QTextEdit, QMessageBox, QApplication)
from PySide6.QtCore import Qt, Signal
from hachimi_converter import convert_to_hachimi_format
from config import MOD_DIR, WORKSPACE_DIR
from gui_font_manager import get_gui_font
from asset_loader import AssetManager
from extractor import extract_asset_data

class UIAnimationEditorTab(QWidget):
    dirty_state_changed = Signal(bool)

    def __init__(self, filepath: Path, asset_name: str, display_name: str, tree_item, parent=None):
        super().__init__(parent)
        self.workspace_path = filepath
        self.asset_name = asset_name
        self.asset_type = "uianimation"
        self.display_name = display_name
        self.tree_item = tree_item
        self._is_dirty = False
        self.data = None
        self.current_block_index = None

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Motion Name", "Object Name"])
        self.tree.currentItemChanged.connect(self.on_item_changed)
        splitter.addWidget(self.tree)

        editor_widget = QWidget()
        form_layout = QFormLayout(editor_widget)
        self.jp_text = QTextEdit()
        self.jp_text.setReadOnly(True)
        self.en_text = QTextEdit()
        self.en_text.textChanged.connect(self.on_en_text_changed)
        form_layout.addRow("Japanese Text:", self.jp_text)
        form_layout.addRow("English Text:", self.en_text)
        editor_widget.setLayout(form_layout)
        splitter.addWidget(editor_widget)
        splitter.setSizes([400, 600])

        self.jp_text.setFont(get_gui_font(16))
        self.en_text.setFont(get_gui_font(16))

    def load(self):
        if not self.workspace_path.exists():
            reply = QMessageBox.question(self, "Extract New File?",
                                         f"The file does not exist in your workspace:\n\n{self.workspace_path.relative_to(WORKSPACE_DIR)}\n\nWould you like to extract it from the game data now?")
            if reply != QMessageBox.StandardButton.Yes:
                return False

            try:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                with AssetManager() as manager:
                    workspace_data = extract_asset_data(manager, self.asset_type, self.asset_name, workspace_path=None)

                if workspace_data is None:
                    raise RuntimeError("The extractor failed to parse the asset. It may be an unsupported format.")

                self.workspace_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.workspace_path, 'w', encoding='utf-8') as f:
                    json.dump(workspace_data, f, indent=4, ensure_ascii=False)

                if self.tree_item:
                    current_text = self.tree_item.text(0).replace(" *", "")
                    if not current_text.endswith("[✓]"):
                        self.tree_item.setText(0, f"{current_text} [✓]")

            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Extraction Failed", f"Could not extract the asset data:\n{e}")
                return False
            finally:
                QApplication.restoreOverrideCursor()

        with open(self.workspace_path, 'r', encoding='utf-8-sig') as f:
            self.data = json.load(f)

        if not self.data.get("text_blocks"):
            QMessageBox.information(self, "No Text Found",
                                    "This UI animation asset was extracted successfully, but it does not contain any translatable text fields.")

        self.populate_tree()
        return True

    def populate_tree(self):
        self.tree.clear()
        text_blocks = self.data.get("text_blocks", [])
        for block_idx, block in enumerate(text_blocks):
            motion_name = block.get("motion_name", f"Motion {block.get('motion_index')}")
            obj_name = block.get("object_name", f"Text {block.get('text_index')}")

            item = QTreeWidgetItem(self.tree, [motion_name, obj_name])
            item.setData(0, Qt.ItemDataRole.UserRole, block_idx)

            if block.get("enText", "").strip():
                item.setForeground(1, Qt.GlobalColor.gray)

        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)

    def on_item_changed(self, item, previous):
        if not item:
            self.jp_text.clear()
            self.en_text.clear()
            self.en_text.setReadOnly(True)
            self.current_block_index = None
            return

        block_idx = item.data(0, Qt.ItemDataRole.UserRole)
        if block_idx is None:
            self.jp_text.clear()
            self.en_text.clear()
            self.en_text.setReadOnly(True)
            self.current_block_index = None
            return

        self.current_block_index = block_idx
        text_data = self.data["text_blocks"][block_idx]

        self.jp_text.setPlainText(text_data.get("jpText", "").replace("\\n", "\n"))

        self.en_text.blockSignals(True)
        self.en_text.setPlainText(text_data.get("enText", "").replace("\\n", "\n"))
        self.en_text.blockSignals(False)
        self.en_text.setReadOnly(False)

    def on_en_text_changed(self):
        if self.current_block_index is None: return
        self.data["text_blocks"][self.current_block_index]["enText"] = self.en_text.toPlainText().replace('\n', '\\n')
        self._mark_as_dirty()

    def save(self):
        if not self.data: return False
        try:
            with open(self.workspace_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)

            mod_path = MOD_DIR / "assets" / f"{self.asset_name}.json"
            mod_path.parent.mkdir(parents=True, exist_ok=True)
            hachimi_data = convert_to_hachimi_format(self.data)

            if hachimi_data:
                with open(mod_path, 'w', encoding='utf-8') as f:
                    json.dump(hachimi_data, f, indent=4, ensure_ascii=False)
            elif mod_path.exists():
                mod_path.unlink()

            self._is_dirty = False
            self.dirty_state_changed.emit(False)
            self.populate_tree()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save the file:\n{e}")
            return False

    def is_dirty(self):
        return self._is_dirty

    def _mark_as_dirty(self):
        if not self._is_dirty:
            self._is_dirty = True
            self.dirty_state_changed.emit(True)