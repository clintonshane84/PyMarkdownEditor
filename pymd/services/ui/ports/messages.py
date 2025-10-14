from __future__ import annotations

from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable


class Question(Enum):
    """Kind of question to ask the user (maps easily to QMessageBox buttons)."""

    YES_NO = auto()


@runtime_checkable
class IMessageService(Protocol):
    """
    Abstract UI port for showing messages. Decouples business logic from Qt widgets.
    """

    def info(self, parent: Any | None, title: str, text: str) -> None: ...
    def warning(self, parent: Any | None, title: str, text: str) -> None: ...
    def error(self, parent: Any | None, title: str, text: str) -> None: ...

    def ask(
        self,
        parent: Any | None,
        title: str,
        text: str,
        kind: Question = Question.YES_NO,
    ) -> bool:
        """
        Ask a question, returning True for a positive/affirmative response (e.g. Yes),
        False for negative/Cancel.
        """
        ...
