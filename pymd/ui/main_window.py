from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
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
from pymd.services.exporters.base import ExporterRegistry
from pymd.utils.constants import MAX_RECENTS


class MainWindow(QMainWindow):
    """Thin PyQt window that delegates work to injected services (DIP)."""

    def __init__(
        self,
        renderer: IMarkdownRenderer,
        file_service: IFileService,
        settings: ISettingsService,
        start_path: Path | None = None,
        app_title: str = "PyMarkdownEditor",
    ) -> None:
        super().__init__()
        self.setWindowTitle(app_title)
        self.resize(1100, 700)

        self.renderer = renderer
        self.file_service = file_service
        self.settings = settings

        self.doc = Document(path=None, text="", modified=False)
        self.recents: list[str] = self.settings.get_recent()

        # Widgets
        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(False)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))
        self.preview = QTextBrowser(self)
        self.preview.setOpenExternalLinks(True)

        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Signals
        self.editor.textChanged.connect(self._on_text_changed)

        # UI
        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self.setStatusBar(QStatusBar(self))

        # Restore UI state
        geo = self.settings.get_geometry()
        if isinstance(geo, bytes | bytearray):
            self.restoreGeometry(QByteArray(geo))
        split = self.settings.get_splitter()
        if isinstance(split, bytes | bytearray):
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
        self.act_quit = QAction(
            "Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close
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

        # === Reintroduced basic formatting inserts ===
        self.act_bold = QAction("**B**", self, triggered=lambda: self._surround("**", "**"))
        self.act_italic = QAction("*i*", self, triggered=lambda: self._surround("*", "*"))
        self.act_code = QAction("`code`", self, triggered=lambda: self._surround("`", "`"))
        self.act_h1 = QAction("# H1", self, triggered=lambda: self._prefix_line("# "))
        self.act_h2 = QAction("## H2", self, triggered=lambda: self._prefix_line("## "))
        self.act_list = QAction("- list", self, triggered=lambda: self._prefix_line("- "))

        # Export actions from registry
        self.export_actions: list[QAction] = []
        for exporter in ExporterRegistry.all():
            act = QAction(
                exporter.label,
                self,
                triggered=lambda chk=False, e=exporter: self._export_with(e),
            )
            self.export_actions.append(act)

        self.recent_menu = QMenu("Open Recent", self)

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            tb.addAction(a)
        for a in self.export_actions:
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_toggle_wrap)
        tb.addAction(self.act_toggle_preview)

        # Formatting actions on toolbar
        tb.addSeparator()
        for a in (
            self.act_bold,
            self.act_italic,
            self.act_code,
            self.act_h1,
            self.act_h2,
            self.act_list,
        ):
            tb.addAction(a)

        self.addToolBar(tb)

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
        self._refresh_recent_menu()
        filem.addSeparator()
        filem.addAction(self.act_quit)

        viewm = m.addMenu("&View")
        viewm.addAction(self.act_toggle_wrap)
        viewm.addAction(self.act_toggle_preview)

        # New "Format" menu for quick inserts
        fmtm = m.addMenu("&Format")
        for a in (
            self.act_bold,
            self.act_italic,
            self.act_code,
            self.act_h1,
            self.act_h2,
            self.act_list,
        ):
            fmtm.addAction(a)

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
            self.doc.path.with_suffix(f".{exporter.name}").name
            if self.doc.path
            else f"document.{exporter.name}"
        )
        filt = f"{exporter.name.upper()} (*.{exporter.name})"
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

    # ---------- Formatting helpers ----------
    def _surround(self, prefix: str, suffix: str) -> None:
        """
        Surround selection with prefix/suffix;
        If no selection, insert pair & place cursor between.
        """
        c = self.editor.textCursor()
        if c.hasSelection():
            # Replace selection with wrapped text
            selected = c.selectedText()
            # Qt uses U+2029 for line breaks in selectedText(); normalize back to '\n'
            selected = selected.replace("\u2029", "\n")
            c.insertText(f"{prefix}{selected}{suffix}")
        else:
            # Insert and move cursor between the pair
            c.insertText(f"{prefix}{suffix}")
            # Move left by len(suffix) to end up between
            for _ in range(len(suffix)):
                c.movePosition(c.MoveOperation.Left)
            self.editor.setTextCursor(c)

    def _prefix_line(self, text: str) -> None:
        """Prefix each selected line (or current line) with given text."""
        doc = self.editor.document()
        c = self.editor.textCursor()
        start = c.selectionStart()
        end = c.selectionEnd()
        if start == end:
            # No selection -> just prefix current block
            block = doc.findBlock(c.position())
            tc = self.editor.textCursor()
            tc.beginEditBlock()
            tc.setPosition(block.position())
            tc.insertText(text)
            tc.endEditBlock()
            return

        # Multi-line selection: prefix every block touched by the selection
        tc = self.editor.textCursor()
        tc.beginEditBlock()
        blk = doc.findBlock(start)
        # Ensure we cover the last block that contains 'end-1'
        last_pos = max(end - 1, start)
        last_block = doc.findBlock(last_pos)
        while blk.isValid():
            ins = self.editor.textCursor()
            ins.setPosition(blk.position())
            ins.insertText(text)
            if blk == last_block:
                break
            blk = blk.next()
        tc.endEditBlock()

    # ---------- Helpers ----------
    def _render_preview(self):
        html = self.renderer.to_html(self.editor.toPlainText())
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
