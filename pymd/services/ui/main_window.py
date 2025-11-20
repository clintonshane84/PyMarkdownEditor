from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QAction, QKeySequence, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QTextEdit,
    QToolBar,
)

from pymd.domain.interfaces import IFileService, IMarkdownRenderer, ISettingsService
from pymd.domain.models import Document
from pymd.services.exporters.base import ExporterRegistryInst, IExporterRegistry
from pymd.services.ui.create_link import CreateLinkDialog
from pymd.services.ui.find_replace import FindReplaceDialog
from pymd.services.ui.table_dialog import TableDialog
from pymd.utils.constants import MAX_RECENTS


class MainWindow(QMainWindow):
    """Thin PyQt window that delegates work to injected services (DIP)."""

    def __init__(
        self,
        renderer: IMarkdownRenderer,
        file_service: IFileService,
        settings: ISettingsService,
        *,
        exporter_registry: IExporterRegistry | None = None,
        start_path: Path | None = None,
        app_title: str = "PyMarkdownEditor",
    ) -> None:
        super().__init__()
        self.setWindowTitle(app_title)
        self.resize(1100, 700)

        self.renderer = renderer
        self.file_service = file_service
        self.settings = settings

        # Registry instance (defaults to singleton)
        self._exporters = exporter_registry or ExporterRegistryInst

        self.doc = Document(path=None, text="", modified=False)
        self.recents: list[str] = self.settings.get_recent()

        # Widgets
        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(False)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))

        # --- Preview: prefer QWebEngineView, fallback to QTextBrowser ---
        self.preview = self._create_preview_widget()

        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Non-modal Find/Replace dialog
        self.find_dialog = FindReplaceDialog(self.editor, self)

        self.link_dialog = CreateLinkDialog(self.editor, self)
        self.table_dialog = TableDialog(self.editor, self)

        # Signals
        self.editor.textChanged.connect(self._on_text_changed)

        # UI
        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self.setStatusBar(QStatusBar(self))

        # Restore UI state
        geo = self.settings.get_geometry()
        if isinstance(geo, (bytes, bytearray)):
            self.restoreGeometry(QByteArray(geo))
        split = self.settings.get_splitter()
        if isinstance(split, (bytes, bytearray)):
            self.splitter.restoreState(QByteArray(split))

        # Load starting content
        if start_path:
            self._open_path(start_path)
        else:
            self._render_preview()

        # DnD
        self.setAcceptDrops(True)

    # ---------- UI creation ----------
    def _build_actions(self):
        self.exit_action = QAction("&Exit")
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Exit application")
        self.exit_action.triggered.connect(QApplication.instance().quit)

        # File actions
        self.act_new = QAction(
            "New", self, shortcut=QKeySequence.StandardKey.New, triggered=self._new_file
        )
        self.act_open = QAction(
            "Open…",
            self,
            shortcut=QKeySequence.StandardKey.Open,
            triggered=self._open_dialog,
        )
        self.act_save = QAction(
            "Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self._save
        )
        self.act_save_as = QAction(
            "Save As…",
            self,
            shortcut=QKeySequence.StandardKey.SaveAs,
            triggered=self._save_as,
        )
        self.act_toggle_wrap = QAction(
            "Toggle Wrap",
            self,
            checkable=True,
            checked=True,
            triggered=self._toggle_wrap,
        )
        self.act_toggle_preview = QAction(
            "Toggle Preview",
            self,
            checkable=True,
            checked=True,
            triggered=self._toggle_preview,
        )

        # Export actions from registry
        self.export_actions: list[QAction] = []
        for exporter in self._exporters.all():
            act = QAction(
                exporter.label,
                self,
                triggered=lambda chk=False, e=exporter: self._export_with(e),
            )
            self.export_actions.append(act)

        self.recent_menu = QMenu("Open Recent", self)

        # Reintroduced formatting actions
        self.act_bold = QAction("B", self, triggered=lambda: self._surround("**", "**"))
        self.act_italic = QAction("i", self, triggered=lambda: self._surround("*", "*"))
        self.act_code = QAction("`code`", self, triggered=lambda: self._insert_inline_code())
        self.act_code_block = QAction(
            "codeblock", self, triggered=lambda: self._insert_code_block()
        )
        self.act_h1 = QAction("H1", self, triggered=lambda: self._prefix_line("# "))
        self.act_h2 = QAction("H2", self, triggered=lambda: self._prefix_line("## "))
        self.act_list = QAction("List", self, triggered=lambda: self._prefix_line("- "))
        self.act_img = QAction("Image", self, triggered=lambda: self._select_image())
        self.act_link = QAction("Link", self, triggered=lambda: self._create_link())
        self.act_table = QAction(
            "Table", self, shortcut="Ctrl+Shift+T", triggered=self._insert_table
        )

        # NEW: Find/Replace actions with standard shortcuts (portable)
        self.act_find = QAction("Find", self)
        self.act_find.setShortcut(QKeySequence.StandardKey.Find)
        self.act_find.triggered.connect(self._show_find)

        self.act_find_next = QAction("Find Next", self)
        self.act_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        self.act_find_next.triggered.connect(lambda: self.find_dialog.find(forward=True))

        self.act_find_prev = QAction("Find Previous", self)
        self.act_find_prev.setShortcut(QKeySequence.StandardKey.FindPrevious)
        self.act_find_prev.triggered.connect(lambda: self.find_dialog.find(forward=False))

        self.act_replace = QAction("Replace", self)
        self.act_replace.setShortcut(QKeySequence.StandardKey.Replace)
        self.act_replace.triggered.connect(self._show_replace)

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tbf = QToolBar("Formatting", self)
        tb.setMovable(False)
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            tb.addAction(a)
        for a in self.export_actions:
            tb.addAction(a)
        tb.addSeparator()

        # Find/Replace on toolbar for convenience
        for a in (self.act_find, self.act_find_prev, self.act_find_next, self.act_replace):
            tb.addAction(a)
        tb.addSeparator()

        tb.addAction(self.act_toggle_wrap)
        tb.addAction(self.act_toggle_preview)
        tb.addSeparator()

        # Quick formatting buttons (optional)
        for a in (
            self.act_bold,
            self.act_italic,
            self.act_code,
            self.act_code_block,
            self.act_h1,
            self.act_h2,
            self.act_list,
            self.act_img,
            self.act_link,
            self.act_table,
        ):
            tbf.addAction(a)
        tbf.addSeparator()

        self.addToolBar(tb)
        self.addToolBarBreak()
        self.addToolBar(tbf)

    def _build_menu(self):
        m = self.menuBar()
        filem = m.addMenu("&File")
        filem.addAction(self.act_new)
        filem.addAction(self.act_open)
        filem.addMenu(self.recent_menu)
        filem.addSeparator()
        filem.addAction(self.act_save)
        filem.addAction(self.act_save_as)

        for a in self.export_actions:
            filem.addAction(a)

        filem.addAction(self.exit_action)
        self._refresh_recent_menu()

        viewm = m.addMenu("&View")
        viewm.addAction(self.act_toggle_wrap)
        viewm.addAction(self.act_toggle_preview)

        editm = m.addMenu("&Edit")
        # Formatting helpers
        for a in (
            self.act_bold,
            self.act_italic,
            self.act_code,
            self.act_code_block,
            self.act_h1,
            self.act_h2,
            self.act_list,
            self.act_table,
        ):
            editm.addAction(a)
        editm.addSeparator()
        # Find/Replace
        for a in (self.act_find, self.act_find_prev, self.act_find_next, self.act_replace):
            editm.addAction(a)

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        if not self.recents:
            na = QAction("(empty)", self)
            na.setEnabled(False)
            self.recent_menu.addAction(na)
            return
        for p in self.recents[:MAX_RECENTS]:
            self.recent_menu.addAction(
                QAction(p, self, triggered=lambda chk=False, x=p: self._open_path(Path(x)))
            )

    # ---------- Actions ----------
    def _show_find(self):
        self.find_dialog.show_find()

    def _show_replace(self):
        self.find_dialog.show_replace()

    def _select_image(self) -> None:
        path_str = QFileDialog.getOpenFileName(
            self,
            "Select image to add",
            "",
            "PNG (*.png);;JPEG (*.jpeg *.jpg);;All files (*)",
        )
        c = self.editor.textCursor()
        c.insertText(f'<img src="{path_str[0]}" width="300" alt="Alt Text" />')
        self.editor.setTextCursor(c)

    def _create_link(self) -> None:
        """Show the link creation dialog"""
        self.link_dialog.show_create_link()

    def _insert_table(self) -> None:
        """Show the table insertion dialog."""
        self.table_dialog.show_table_dialog()

    def _surround(self, left: str, right: str) -> None:
        c = self.editor.textCursor()
        if not c.hasSelection():
            return
        sel = c.selectedText()
        c.insertText(f"{left}{sel}{right}")
        self.editor.setTextCursor(c)

    def _insert_inline_code(self) -> None:
        """
        If there is a selection: surround it with a single backtick each side.
        If there isn't: insert a single backtick at the caret (open inline code).
        """
        c = self.editor.textCursor()
        if c.hasSelection():
            sel = c.selectedText()
            c.insertText(f"`{sel}`")
        else:
            c.insertText("`")
        self.editor.setTextCursor(c)

    def _insert_code_block(self) -> None:
        """
        Ask for a language; insert a fenced code block on new lines:
            ```<lang-if-chosen>

            ```
        Place caret on the blank line inside the block.
        """
        languages = [
            "",  # (none)
            "php",
            "javascript",
            "typescript",
            "java",
            "c",
            "cpp",
            "csharp",
            "python",
            "ruby",
            "scala",
        ]

        lang, ok = QInputDialog.getItem(
            self, "Code block language", "Select language (optional):", languages, 0, False
        )
        if not ok:
            return

        lang_suffix = lang.strip()
        if lang_suffix:
            first_line = f"```{lang_suffix}"
        else:
            first_line = "```"

        c = self.editor.textCursor()
        c.beginEditBlock()
        try:
            # Ensure we start on a new line for the opening fence
            # If we're not already at start of a line, insert a newline.
            if c.position() > 0:
                # Peek previous char; save pos, read, then restore pos before inserting
                original_pos = c.position()
                c.movePosition(c.MoveOperation.Left, c.MoveMode.KeepAnchor, 1)
                prev = c.selectedText()
                c.clearSelection()
                c.setPosition(original_pos)
                if prev != "\u2029" and prev != "\n":  # Qt block sep or newline
                    c.insertText("\n")

            # Insert fenced block:
            # ```<lang>
            #
            # ```
            c.insertText(first_line + "\n\n```\n")

            # Move caret back to the blank line between fences
            # After insert caret is at end; go up two blocks:
            c.movePosition(c.MoveOperation.PreviousBlock)  # closing fence
            c.movePosition(c.MoveOperation.PreviousBlock)  # blank line
            # Put caret at end of the blank line (ready to type)
            c.movePosition(c.MoveOperation.EndOfBlock)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)

    def _prefix_line(self, prefix: str) -> None:
        c = self.editor.textCursor()
        doc = self.editor.document()

        # No selection → prefix current line and return.
        if not c.hasSelection():
            c.beginEditBlock()
            c.movePosition(c.MoveOperation.StartOfLine)
            c.insertText(prefix)
            c.endEditBlock()
            self.editor.setTextCursor(c)
            return

        # Selection → prefix every line that intersects the selection.
        start = min(c.selectionStart(), c.selectionEnd())
        end = max(c.selectionStart(), c.selectionEnd())

        # Make sure the last block is included even if selection ends at a block boundary
        # or at the very end of the document.
        end_inclusive_pos = max(0, end - 1)

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end_inclusive_pos)

        cur = QTextCursor(start_block)
        cur.beginEditBlock()
        try:
            block = start_block
            while block.isValid():
                # Move to the beginning of this block and insert the prefix
                cur.setPosition(block.position())
                cur.insertText(prefix)
                if block == end_block:
                    break
                block = block.next()
        finally:
            cur.endEditBlock()

        # Keep the original selection/caret behavior predictable
        self.editor.setTextCursor(c)

    def _new_file(self):
        if not self._confirm_discard():
            return
        self.doc = Document(path=None, text="", modified=False)
        self.editor.setPlainText("")
        self._update_title()
        self._render_preview()

    def _open_dialog(self):
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Markdown",
            "",
            "Markdown (*.md *.markdown *.mdown);;Text (*.txt);;All files (*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _open_path(self, path: Path):
        if not self._confirm_discard():
            return
        try:
            text = self.file_service.read_text(path)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open file:\n{e}")
            return
        self.doc = Document(path=path, text=text, modified=False)
        self.editor.setPlainText(text)
        self._update_title()
        self._render_preview()
        self._add_recent(path)

    def _save(self):
        if self.doc.path is None:
            self._save_as()
            return
        self._write_to(self.doc.path)

    def _save_as(self):
        start = str(self.doc.path) if self.doc.path else ""
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save As", start, "Markdown (*.md);;All files (*)"
        )
        if not path_str:
            return
        path = Path(path_str)
        if self._write_to(path):
            self.doc.path = path
            self._update_title()
            self._add_recent(path)

    def _write_to(self, path: Path) -> bool:
        try:
            self.file_service.write_text_atomic(path, self.editor.toPlainText())
            self.doc.modified = False
            self._update_title()
            self.statusBar().showMessage(f"Saved: {path}", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")
            return False

    def _export_with(self, exporter):
        # choose output file
        default = (
            self.doc.path.with_suffix(f".{exporter.file_ext}").name
            if self.doc.path
            else f"document.{exporter.name}"
        )
        filt = f"{exporter.name.upper()} (*.{exporter.file_ext})"
        out_str, _ = QFileDialog.getSaveFileName(self, exporter.label, default, filt)
        if not out_str:
            return
        html = self.renderer.to_html(self.editor.toPlainText())
        try:
            exporter.export(html, Path(out_str))
            self.statusBar().showMessage(f"Exported {exporter.name.upper()}: {out_str}", 3000)
        except Exception as e:
            QMessageBox.critical(
                self, "Export Error", f"Failed to export {exporter.name.upper()}:\n{e}"
            )

    def _toggle_wrap(self, on: bool):
        mode = QTextEdit.LineWrapMode.WidgetWidth if on else QTextEdit.LineWrapMode.NoWrap
        self.editor.setLineWrapMode(mode)

    def _toggle_preview(self, on: bool):
        self.preview.setVisible(on)

    # ---------- Helpers ----------
    def _render_preview(self):
        html = self.renderer.to_html(self.editor.toPlainText())
        # Both QWebEngineView and QTextBrowser implement setHtml(html).
        self.preview.setHtml(html)

    def _on_text_changed(self):
        self.doc.modified = True
        self._update_title()
        self._render_preview()

    def _update_title(self):
        name = self.doc.path.name if self.doc.path else "Untitled"
        star = " •" if self.doc.modified else ""
        self.setWindowTitle(f"{name}{star} — Markdown Editor")

    def _confirm_discard(self) -> bool:
        if not self.doc.modified:
            return True
        resp = QMessageBox.question(
            self,
            "Discard changes?",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return resp == QMessageBox.StandardButton.Yes

    def _add_recent(self, path: Path):
        s = str(path)
        if s in self.recents:
            self.recents.remove(s)
        self.recents.insert(0, s)
        self.recents = self.recents[:MAX_RECENTS]
        self.settings.set_recent(self.recents)
        self._refresh_recent_menu()

    # ---------- DnD ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if not urls:
            return
        local = urls[0].toLocalFile()
        if local:
            self._open_path(Path(local))

    # ---------- Close ----------
    def closeEvent(self, event):
        self.settings.set_geometry(bytes(self.saveGeometry()))
        self.settings.set_splitter(bytes(self.splitter.saveState()))
        super().closeEvent(event)

    # ---------- Internal: preview creation ----------
    def _create_preview_widget(self):
        """
        Prefer QWebEngineView (JS-capable: MathJax/KaTeX, better CSS), fall back to QTextBrowser.
        We guard the import so the app runs even if Qt WebEngine isn't installed.
        """
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore

            print("QWebEngineView was initiated")
            return QWebEngineView(self)
        except Exception as e:
            print(f"QWebEngineView failed to initiate with message: {e}")
            w = QTextBrowser(self)
            print("QTextBrowser was initiated as a fallback")
            w.setOpenExternalLinks(True)
            return w
