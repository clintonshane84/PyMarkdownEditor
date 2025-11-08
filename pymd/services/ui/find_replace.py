from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PyQt6.QtGui import QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QCheckBox,
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
    def find(self, text: str, flags) -> bool: ...


@dataclass(frozen=True)
class SearchOptions:
    text: str
    replace: str = ""
    case_sensitive: bool = False
    whole_words: bool = False
    wrap: bool = True
    forward: bool = True


class SearchEngine(Protocol):
    def find_once(self, opt: SearchOptions) -> bool: ...
    def replace_one(self, opt: SearchOptions) -> bool: ...
    def replace_all(self, opt: SearchOptions) -> int: ...


class PlainTextSearchService:
    """Pure search/replace policy; UI-agnostic."""

    def __init__(self, editor: EditorPort):
        self._ed = editor

    def _flags(self, opt: SearchOptions):
        f = QTextDocument.FindFlag(0)
        if opt.case_sensitive:
            f |= QTextDocument.FindFlag.FindCaseSensitively
        if opt.whole_words:
            f |= QTextDocument.FindFlag.FindWholeWords
        if not opt.forward:
            f |= QTextDocument.FindFlag.FindBackward
        return f

    def find_once(self, opt: SearchOptions) -> bool:
        if not opt.text:
            return False
        if self._ed.find(opt.text, self._flags(opt)):
            return True
        if opt.wrap:
            cur = self._ed.textCursor()
            cur.movePosition(
                QTextCursor.MoveOperation.Start if opt.forward else QTextCursor.MoveOperation.End
            )
            self._ed.setTextCursor(cur)
            return self._ed.find(opt.text, self._flags(opt))
        return False

    def replace_one(self, opt: SearchOptions) -> bool:
        if not opt.text:
            return False
        cur = self._ed.textCursor()
        sel = cur.selectedText()
        # Whole-word is enforced by find; here we honor case-sensitivity only.
        if sel and ((sel == opt.text) if opt.case_sensitive else (sel.lower() == opt.text.lower())):
            cur.insertText(opt.replace)
            self._ed.setTextCursor(cur)
            return True
        return False

    def replace_all(self, opt: SearchOptions) -> int:
        if not opt.text:
            return 0

        # Start deterministically at beginning (or end if backward),
        # but do NOT allow wrap during the loop to avoid re-hitting replaced text.
        cur = self._ed.textCursor()
        cur.movePosition(
            QTextCursor.MoveOperation.Start if opt.forward else QTextCursor.MoveOperation.End
        )
        self._ed.setTextCursor(cur)

        # Use a no-wrap copy of options inside the loop.
        opt_nowrap = SearchOptions(
            text=opt.text,
            replace=opt.replace,
            case_sensitive=opt.case_sensitive,
            whole_words=opt.whole_words,
            wrap=False,  # <-- critical
            forward=opt.forward,
        )

        block = QTextCursor(self._ed.document())
        block.beginEditBlock()
        try:
            count = 0
            # Find next occurrence without wrapping
            while self._ed.find(opt_nowrap.text, self._flags(opt_nowrap)):
                cur = self._ed.textCursor()
                if not cur.hasSelection():
                    break
                # Replace current selection; cursor ends after inserted text
                cur.insertText(opt_nowrap.replace)
                self._ed.setTextCursor(cur)
                count += 1
            return count
        finally:
            block.endEditBlock()


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


# -------------------------
# Dialog (View/Controller)
# -------------------------


class FindReplaceDialog(QDialog):
    """Non-modal find/replace dialog backed by PlainTextSearchService."""

    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find / Replace")
        self.setModal(False)

        self._engine: SearchEngine = PlainTextSearchService(QtTextEditorAdapter(editor))

        # Widgets
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_cb = QCheckBox("Match case")
        self.word_cb = QCheckBox("Whole words")
        self.wrap_cb = QCheckBox("Wrap around")
        self.wrap_cb.setChecked(True)

        self.find_prev_btn = QPushButton("Find Previous")
        self.find_next_btn = QPushButton("Find Next")
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

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(opts)
        root.addLayout(buttons)

        # Signals
        self.find_next_btn.clicked.connect(lambda: self.find(forward=True))
        self.find_prev_btn.clicked.connect(lambda: self.find(forward=False))
        self.replace_btn.clicked.connect(self.replace_one)
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.close_btn.clicked.connect(self.close)

        # Enter-to-find/replace (predictable UX; no live keystroke scanning)
        self.find_edit.returnPressed.connect(lambda: self.find(forward=True))
        self.replace_edit.returnPressed.connect(self.replace_one)

        # Handy shortcuts (work while dialog focused)
        self.find_edit.setPlaceholderText("Find text… (Ctrl/Cmd+G to find next)")
        self.replace_edit.setPlaceholderText("Replace with…")

    # Public API used by MainWindow wiring (simple and explicit)
    def show_find(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def show_replace(self) -> None:
        self.show_find()
        self.replace_edit.setFocus()
        self.replace_edit.selectAll()

    # Internal helpers
    def _options(self, *, forward: bool) -> SearchOptions:
        return SearchOptions(
            text=self.find_edit.text(),
            replace=self.replace_edit.text(),
            case_sensitive=self.case_cb.isChecked(),
            whole_words=self.word_cb.isChecked(),
            wrap=self.wrap_cb.isChecked(),
            forward=forward,
        )

    def find(self, *, forward: bool):
        self._engine.find_once(self._options(forward=forward))

    def replace_one(self):
        opt = self._options(forward=True)
        # If the current selection is not a match, find next (do not replace arbitrary text).
        if not self._engine.replace_one(opt):
            self._engine.find_once(opt)

    def replace_all(self):
        count = self._engine.replace_all(self._options(forward=True))
        self.setWindowTitle(f"Find / Replace — {count} replaced")
