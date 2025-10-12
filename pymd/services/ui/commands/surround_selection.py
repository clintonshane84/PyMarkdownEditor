from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QTextEdit


@dataclass(frozen=True)
class SurroundSelection:
    """
    Command: surround current selection with prefix/suffix.
    If no selection, insert the pair and place the cursor between them.
    """

    edit: QTextEdit
    prefix: str
    suffix: str

    def execute(self) -> None:
        c = self.edit.textCursor()
        if c.hasSelection():
            selected = c.selectedText().replace("\u2029", "\n")  # Qt uses U+2029 for line breaks
            c.insertText(f"{self.prefix}{selected}{self.suffix}")
        else:
            c.insertText(f"{self.prefix}{self.suffix}")
            # move cursor left by len(suffix) to end up between the pair
            for _ in range(len(self.suffix)):
                c.movePosition(c.MoveOperation.Left)
            self.edit.setTextCursor(c)
