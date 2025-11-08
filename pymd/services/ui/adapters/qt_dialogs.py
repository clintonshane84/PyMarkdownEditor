from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6 import QtWidgets
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QTextDocument
from PyQt6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QLabel,
    QFormLayout,
    QGroupBox,
    QComboBox,
    QButtonGroup,
    QDialog,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QTextEdit,
    QCheckBox,
    QGridLayout,
)

from pymd.services.ui.adapters import QtMessageService
from pymd.services.ui.ports.dialogs import IFileDialogService


class QtFileDialogService(IFileDialogService):
    """Qt-backed implementation of file dialogs."""

    def get_open_file(
        self,
        parent: Any | None,
        caption: str,
        start_dir: str | None,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getOpenFileName(
            parent,
            caption,
            start_dir or "",
            filter_str,
        )
        return Path(path_str) if path_str else None

    def get_save_file(
        self,
        parent: Any | None,
        caption: str,
        start_path: str | None,
        filter_str: str,
    ) -> Path | None:
        path_str, _ = QFileDialog.getSaveFileName(
            parent,
            caption,
            start_path or "",
            filter_str,
        )
        return Path(path_str) if path_str else None


class QtFindReplaceDialogService(QtWidgets.QDialog):
    """Qt-backed implementation of find replace dialog."""

    # Define signals to communicate with the main application
    find_next_signal = pyqtSignal(str, bool, bool)
    replace_signal = pyqtSignal(str, str, bool, bool)
    replace_all_signal = pyqtSignal(str, str, bool, bool)

    def __init__(self, parent: Any, editor: QTextEdit) -> None:
        super().__init__(parent)
        self.parent = parent
        self.editor = editor
        self.setWindowTitle("Find and Replace")
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()

        # Widgets
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_cb = QCheckBox("Match case")
        self.word_cb = QCheckBox("Whole words")
        self.wrap_cb = QCheckBox("Wrap around")
        self.wrap_cb.setChecked(True)

        self.find_prev_btn = QPushButton("Previous")
        self.find_next_btn = QPushButton("Next")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn = QPushButton("Close")

        # Layout
        form = QGridLayout()
        form.addWidget(QLabel("Find:"), 0, 0)
        form.addWidget(self.find_edit, 0, 1, 1, 3)
        form.addWidget(QLabel("Replace:"), 1, 0)
        form.addWidget(self.replace_edit, 1, 1, 1, 3)

        opts = QHBoxLayout()
        opts.addWidget(self.case_cb)
        opts.addWidget(self.word_cb)
        opts.addWidget(self.wrap_cb)
        opts.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.find_prev_btn)
        buttons.addWidget(self.find_next_btn)
        buttons.addWidget(self.replace_btn)
        buttons.addWidget(self.replace_all_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(opts)
        root.addLayout(buttons)

    def connect_signals(self):
        self.find_next_btn.click().connect(self.find_next_signal)
        self.find_prev_btn.click().connect(self.find_prev_btn)
        self.replace_btn.click().connect(self.replace_btn)
        self.replace_all_btn.click().connect(self.replace_all_btn)

    def find_next(self):
        if self.editor and self.find_input.text():
            search_string = self.find_input.text()
            flags = QTextDocument.FindFlag(0)  # No flags for now, can add case-sensitivity etc
            found = self.editor.find(search_string, flags)
            if not found:
                QtMessageService().info(
                    None, "No results", f"Could not find text: '{search_string}'"
                )
