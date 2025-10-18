from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QPushButton, QListWidget, QListWidgetItem, QWidget,
                               QLabel, QCheckBox, QMessageBox, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal
from pathlib import Path
from find import search_content_generator
from gui_worker import Worker 
import json
import re

class SearchResultWidget(QWidget):
    def __init__(self, result_data):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        filepath_str = str(Path(result_data["filepath"]).name)
        path_label = QLabel(f"<b>File:</b> {filepath_str}")
        name_label = QLabel(f"<b>Speaker:</b> {result_data['jpName']}")
        content_label = QLabel(f"<b>Text:</b> {result_data['jpText']}")
        content_label.setWordWrap(True)

        layout.addWidget(path_label)
        layout.addWidget(name_label)
        layout.addWidget(content_label)

class FindReplaceDialog(QDialog):
    def __init__(self, workspace_dir, parent=None):
        super().__init__(parent)
        self.workspace_dir = workspace_dir
        self.worker = None
        self.setWindowTitle("Find and Replace in Files")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        find_layout = QHBoxLayout()
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.find_button = QPushButton("Find All")
        find_layout.addWidget(QLabel("Find:"))
        find_layout.addWidget(self.find_input)
        find_layout.addWidget(self.find_button)
        layout.addLayout(find_layout)

        replace_layout = QHBoxLayout()
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")
        replace_layout.addWidget(QLabel("Replace:"))
        replace_layout.addWidget(self.replace_input)
        layout.addLayout(replace_layout)

        self.case_sensitive_check = QCheckBox("Case Sensitive")
        layout.addWidget(self.case_sensitive_check)

        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.results_list)

        self.status_label = QLabel("Ready.")
        self.replace_button = QPushButton("Replace Selected")
        self.replace_button.setEnabled(False)

        button_box = QDialogButtonBox()
        button_box.addButton(self.replace_button, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.status_label)
        layout.addWidget(button_box)

        self.find_button.clicked.connect(self._start_search)
        self.replace_button.clicked.connect(self._start_replace)
        self.find_input.returnPressed.connect(self._start_search)

    def _start_search(self):
        if self.worker and self.worker.isRunning(): return

        term = self.find_input.text()
        if not term: return

        self.results_list.clear()
        self.replace_button.setEnabled(False)
        self.status_label.setText("Searching...")

        def search_task():
            generator = search_content_generator(
                self.workspace_dir, term, self.case_sensitive_check.isChecked()
            )
            return list(generator)

        self.worker = Worker(search_task)
        self.worker.finished.connect(self._on_search_finished)
        self.worker.start()

    def _on_search_finished(self, results):
        if "failed" in results:
            self.status_label.setText(f"Error: {results}")
            return

        for result in json.loads(results):
            item_widget = SearchResultWidget(result)
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setData(Qt.ItemDataRole.UserRole, result)
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)

        self.status_label.setText(f"Found {self.results_list.count()} result(s).")
        self.replace_button.setEnabled(self.results_list.count() > 0)

    def _start_replace(self):
        selected_items = self.results_list.selectedItems()
        if not selected_items: return

        find_term = self.find_input.text()
        replace_term = self.replace_input.text()
        case_sensitive = self.case_sensitive_check.isChecked()

        reply = QMessageBox.question(self, "Confirm Replace",
            f"Are you sure you want to replace '{find_term}' with '{replace_term}' in {len(selected_items)} places?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

        if reply != QMessageBox.StandardButton.Yes: return

        files_to_modify = {}
        for item in selected_items:
            data = item.data(Qt.ItemDataRole.UserRole)
            filepath = data['filepath']
            if filepath not in files_to_modify:
                files_to_modify[filepath] = []
            files_to_modify[filepath].append(data)

        def replace_task():
            count = 0
            for filepath, results in files_to_modify.items():
                with open(filepath, 'r+', encoding='utf-8') as f:
                    file_data = json.load(f)
                    for result in results:
                        block = file_data["text_blocks"][result['block_index']]

                        original_text = block['enText'] if 'enText' in block else ""

                        if case_sensitive:
                            block['enText'] = original_text.replace(find_term, replace_term)
                        else:
                            flags = 0 if case_sensitive else re.IGNORECASE
                            block['enText'] = re.sub(find_term, replace_term, original_text, flags=flags)

                        count += 1

                    f.seek(0)
                    json.dump(file_data, f, indent=4, ensure_ascii=False)
                    f.truncate()
            return f"Replaced {count} occurrence(s)."

        self.worker = Worker(replace_task)
        self.worker.finished.connect(self._on_replace_finished)
        self.worker.start()

    def _on_replace_finished(self, message):
        QMessageBox.information(self, "Replace Complete", message)
        self.status_label.setText(message)
        self._start_search()