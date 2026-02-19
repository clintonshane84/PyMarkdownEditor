from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from pymd.plugins.api import IAppAPI


class PluginAppAPI(IAppAPI):
    def __init__(self, *, window) -> None:
        self._w = window

    def get_current_text(self) -> str:
        return self._w.editor.toPlainText()

    def set_current_text(self, text: str) -> None:
        self._w.editor.setPlainText(text)

    def insert_text_at_cursor(self, text: str) -> None:
        c = self._w.editor.textCursor()
        c.insertText(text)
        self._w.editor.setTextCursor(c)

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self._w, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self._w, title, message)