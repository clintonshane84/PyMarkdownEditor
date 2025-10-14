from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QTextEdit


@dataclass(frozen=True)
class PrefixLines:
    """
    Command: prefix each selected line (or the current line if no selection) with `prefix`.
    """

    edit: QTextEdit
    prefix: str

    def execute(self) -> None:
        doc = self.edit.document()
        c = self.edit.textCursor()
        start = c.selectionStart()
        end = c.selectionEnd()

        if start == end:
            # No selection -> just prefix current block
            block = doc.findBlock(c.position())
            tc = self.edit.textCursor()
            tc.beginEditBlock()
            tc.setPosition(block.position())
            tc.insertText(self.prefix)
            tc.endEditBlock()
            return

        # Multi-line selection: prefix every block touched by the selection
        tc = self.edit.textCursor()
        tc.beginEditBlock()
        blk = doc.findBlock(start)
        last_pos = max(end - 1, start)
        last_block = doc.findBlock(last_pos)
        while blk.isValid():
            ins = self.edit.textCursor()
            ins.setPosition(blk.position())
            ins.insertText(self.prefix)
            if blk == last_block:
                break
            blk = blk.next()
        tc.endEditBlock()
