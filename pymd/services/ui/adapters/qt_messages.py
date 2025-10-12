from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QMessageBox

from pymd.services.ui.ports.messages import IMessageService, Question


class QtMessageService(IMessageService):
    """Qt-backed implementation for message dialogs."""

    def info(self, parent: Any | None, title: str, text: str) -> None:
        QMessageBox.information(parent, title, text)

    def warning(self, parent: Any | None, title: str, text: str) -> None:
        QMessageBox.warning(parent, title, text)

    def error(self, parent: Any | None, title: str, text: str) -> None:
        QMessageBox.critical(parent, title, text)

    def ask(
        self,
        parent: Any | None,
        title: str,
        text: str,
        kind: Question = Question.YES_NO,
    ) -> bool:
        if kind is Question.YES_NO:
            resp = QMessageBox.question(
                parent,
                title,
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            return resp == QMessageBox.StandardButton.Yes
        # Fallback: treat as Yes/No
        resp = QMessageBox.question(
            parent,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return resp == QMessageBox.StandardButton.Yes
