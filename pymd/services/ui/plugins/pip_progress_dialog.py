from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QTextEdit, QPushButton, QHBoxLayout


class PipProgressDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 420)

        layout = QVBoxLayout(self)

        self.label = QLabel("Working…", self)
        layout.addWidget(self.label)

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)  # indeterminate
        layout.addWidget(self.progress)

        self.log = QTextEdit(self)
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_close = QPushButton("Close", self)
        self.btn_close.setEnabled(False)
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

    def append(self, text: str) -> None:
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(self.log.textCursor().MoveOperation.End)

    def set_done(self, ok: bool, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.label.setText(message)
        self.btn_close.setEnabled(True)
        self.btn_cancel.setEnabled(False)