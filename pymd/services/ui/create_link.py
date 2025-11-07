from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtGui import QKeySequence, QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout, QWidget, QApplication,
)


# -------------------------
# Ports / Model / Service
# -------------------------

class EditorPort(Protocol):
    def textCursor(self) -> QTextCursor: ...
    def setTextCursor(self, c: QTextCursor) -> None: ...
    def document(self): ...


class CreateLinkDialog(QDialog):
    def __init__(self, editor: EditorPort, parent=None):
        super().__init__(parent)
        self._ed = editor
        self.setWindowTitle("Create Link")
        self.setModal(False)

        # Widgets
        self.url_edit = QLineEdit()
        self.link_title = QLineEdit()

        self.create_link_btn = QPushButton("Create")
        self.close_btn = QPushButton("Close")

        # Layout
        form = QGridLayout()
        form.addWidget(QLabel("Link URL:"), 0, 0)
        form.addWidget(self.url_edit, 0, 1, 1, 3)
        form.addWidget(QLabel("Link Title:"), 1, 0)
        form.addWidget(self.link_title, 1, 1, 1, 3)

        buttons = QHBoxLayout()
        buttons.addWidget(self.create_link_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(buttons)

        # Signals
        self.create_link_btn.clicked.connect(lambda: self.create_link(self.url_edit.text(), self.link_title.text()))
        self.close_btn.clicked.connect(QApplication.instance().quit)

    # Public API used by MainWindow wiring (simple and explicit)
    def show_create_link(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.url_edit.setFocus()
        self.url_edit.selectAll()

    def create_link(self) -> None:
        cur = self._ed.textCursor()
        cur.insertText(f"[{self.link_title.text()}]({self.url_edit.text()})")
        self._ed.setTextCursor(cur)