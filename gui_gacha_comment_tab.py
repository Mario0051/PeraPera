import json
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QGroupBox,
                               QHBoxLayout, QLabel, QTextEdit, QPushButton, QMessageBox)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from api import PeraPeraAPI
from config import WORKSPACE_DIR
from asset_generator import generate_gacha_comment_img

class GachaCommentTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pp_api = PeraPeraAPI()
        self.comment_data_path = WORKSPACE_DIR / "gacha_comments.json"
        self.text_edits = {}

        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        save_btn = QPushButton("Save Translations")
        save_btn.clicked.connect(self.save_texts)
        generate_btn = QPushButton("Save & Generate Images")
        generate_btn.clicked.connect(self.save_and_generate)
        top_bar.addWidget(save_btn)
        top_bar.addWidget(generate_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        self.load_comments()

    def load_comments(self):
        try:
            text_data = self.pp_api.load_dict("text_data_dict.json")
            source_comments = self.pp_api.mdb.get_text_data_category(122)

            if self.comment_data_path.exists():
                translated_comments = self.pp_api.load_dict(self.comment_data_path)
            else:
                translated_comments = {}

            for asset_id, jp_text in source_comments.items():
                if not jp_text: continue

                en_text = translated_comments.get(str(asset_id), "")

                group_box = QGroupBox(f"Gacha Comment ID: {asset_id}")
                vbox = QVBoxLayout(group_box)

                jp_label = QLabel(f"<b>JP:</b> {jp_text.replace('##', '')}")
                jp_label.setWordWrap(True)

                en_edit = QTextEdit(en_text)
                en_edit.setPlaceholderText("Enter English translation here...")
                en_edit.setMinimumHeight(60)

                vbox.addWidget(jp_label)
                vbox.addWidget(en_edit)

                self.scroll_layout.addWidget(group_box)
                self.text_edits[str(asset_id)] = en_edit

        except FileNotFoundError:
            label = QLabel("Could not find 'text_data_dict.json'. Please run 'Dump All Tables' first.")
            self.scroll_layout.addWidget(label)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load comments: {e}")

    def save_texts(self):
        data_to_save = {asset_id: editor.toPlainText() for asset_id, editor in self.text_edits.items()}
        self.pp_api.save_dict(self.comment_data_path, data_to_save)
        QMessageBox.information(self, "Success", "Gacha comment translations have been saved.")

    def save_and_generate(self):
        self.save_texts()
        try:
            self.pp_api.log.info("Triggering gacha comment image generation...")
            from asset_generator import _generate_gacha_comments
            _generate_gacha_comments(self.pp_api)
            QMessageBox.information(self, "Success", "Gacha comment images have been generated!")
        except Exception as e:
            QMessageBox.critical(self, "Generation Failed", f"Could not generate images: {e}")