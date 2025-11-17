from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit


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

    def find(self, text: str, flags) -> bool:
        return self._e.find(text, flags)
