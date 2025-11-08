from __future__ import annotations

from typing import Protocol

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

# -------------------------
# Ports / Model / Service
# -------------------------


class EditorPort(Protocol):
    def textCursor(self) -> QTextCursor: ...
    def setTextCursor(self, c: QTextCursor) -> None: ...
    def document(self): ...


class QtTextEditorAdapter:
    """Narrow adapter to satisfy EditorPort; isolates service from full QTextEdit API."""

    def __init__(self, edit: QTextEdit):
        self._e = edit

    def textCursor(self) -> QTextCursor:
        return self._e.textCursor()

    def setTextCursor(self, c: QTextCursor) -> None:
        self._e.setTextCursor(c)

    def document(self):
        return self._e.document()


class CreateLinkDialog(QDialog):
    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Link")
        self.setModal(False)
        self._ed = QtTextEditorAdapter(editor)

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

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(buttons)

        # Signals
        self.create_link_btn.clicked.connect(lambda: self.create_link(self._ed))
        self.close_btn.clicked.connect(self.close)

    # Public API used by MainWindow wiring (simple and explicit)
    def show_create_link(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.url_edit.setFocus()
        self.url_edit.selectAll()

    def create_link(self, editor: EditorPort) -> None:
        cur = editor.textCursor()
        cur.insertText(f"[{self.link_title.text()}]({self.url_edit.text()})")
        editor.setTextCursor(cur)
        self.close()
