#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QSaveFile,
    QIODevice,
    QByteArray,
    QSettings,
    QMarginsF,
)
from PyQt6.QtGui import QAction, QKeySequence, QPageLayout, QPageSize, QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QTextBrowser,
    QFileDialog,
    QSplitter,
    QToolBar,
    QMessageBox,
    QStatusBar,
    QMenu,
)
from PyQt6.QtPrintSupport import QPrinter

APP_ORG = "QuickTools"
APP_NAME = "PyQt Markdown Editor"
SETTINGS_GEOMETRY = "window/geometry"
SETTINGS_SPLITTER = "window/splitter"
SETTINGS_RECENTS = "file/recent"
MAX_RECENTS = 8

# ---- Minimal CSS for preview (light + dark) ----
PREVIEW_CSS = """
:root { --bg:#ffffff; --fg:#111; --muted:#555; --code:#f4f6f8; --border:#ddd; --link:#0b6bfd; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#0f1115; --fg:#e7e9ee; --muted:#a0a4ae; --code:#1a1d24; --border:#2a2f3a; --link:#7aa2ff; }
}
html,body { background:var(--bg); color:var(--fg); }
body {
  font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  margin: 1.25rem; line-height: 1.55;
}
h1,h2,h3,h4,h5 { margin-top: 1.2em; }
pre { padding:.75rem; overflow:auto; border-radius:8px; background:var(--code); }
code { background:var(--code); padding:.15rem .3rem; border-radius:6px; }
blockquote { border-left:4px solid var(--border); margin:1em 0; padding:.25em .75em; color:var(--muted); }
table { border-collapse: collapse; }
th, td { border:1px solid var(--border); padding:.4rem .6rem; }
a { color:var(--link); text-decoration:none; }
a:hover { text-decoration:underline; }
hr { border:none; border-top:1px solid var(--border); margin:1.5rem 0; }
ul,ol { padding-left:1.5rem; }
"""

HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


class MarkdownEditor(QMainWindow):
    def __init__(self, path: Path | None = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}")
        self.resize(1100, 700)

        # State
        self.current_path: Path | None = None
        self.modified = False
        self.recent_files: list[str] = []

        # Widgets
        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(False)
        self.editor.setTabStopDistance(
            4 * self.editor.fontMetrics().horizontalAdvance(" ")
        )
        self.preview = QTextBrowser(self)
        self.preview.setOpenExternalLinks(True)

        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Debounced live preview
        self._debounce = QTimer(self)
        self._debounce.setInterval(150)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.render_preview)

        self.editor.textChanged.connect(self._on_text_changed)

        # UI: toolbar & menu
        self._build_actions()
        self._build_toolbar()
        self._build_menubar()
        self.setStatusBar(QStatusBar(self))

        # Settings
        self._settings = QSettings(APP_ORG, APP_NAME)
        self._load_settings()

        # Load initial file if provided
        if path:
            self.open_file(path)
        else:
            self.render_preview()

        # Drag & drop support
        self.setAcceptDrops(True)

    # ---------- UI Builders ----------
    def _build_actions(self):
        self.act_new = QAction(
            "New", self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_file
        )
        self.act_open = QAction(
            "Open…",
            self,
            shortcut=QKeySequence.StandardKey.Open,
            triggered=self.open_dialog,
        )
        self.act_save = QAction(
            "Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save
        )
        self.act_save_as = QAction(
            "Save As…",
            self,
            shortcut=QKeySequence.StandardKey.SaveAs,
            triggered=self.save_as,
        )
        self.act_export_html = QAction("Export HTML…", self, triggered=self.export_html)
        self.act_export_pdf = QAction("Export PDF…", self, triggered=self.export_pdf)
        self.act_quit = QAction(
            "Quit", self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close
        )

        self.act_wrap = QAction(
            "Toggle Wrap",
            self,
            checkable=True,
            checked=True,
            triggered=self.toggle_wrap,
        )
        self.act_preview = QAction(
            "Toggle Preview",
            self,
            checkable=True,
            checked=True,
            triggered=self.toggle_preview,
        )
        self.act_reload = QAction(
            "Re-render", self, shortcut="Ctrl+R", triggered=self.render_preview
        )
        self.act_about = QAction("About", self, triggered=self.show_about)

        # Basic formatting inserts
        self.act_bold = QAction(
            "**B**", self, triggered=lambda: self._surround("**", "**")
        )
        self.act_italic = QAction(
            "*i*", self, triggered=lambda: self._surround("*", "*")
        )
        self.act_code = QAction(
            "`code`", self, triggered=lambda: self._surround("`", "`")
        )
        self.act_h1 = QAction("# H1", self, triggered=lambda: self._prefix_line("# "))
        self.act_h2 = QAction("## H2", self, triggered=lambda: self._prefix_line("## "))
        self.act_list = QAction(
            "- list", self, triggered=lambda: self._prefix_line("- ")
        )

        # Recent files submenu (populated later)
        self.recent_menu = QMenu("Open Recent", self)

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        for a in (
            self.act_new,
            self.act_open,
            self.act_save,
            self.act_save_as,
            self.act_export_html,
            self.act_export_pdf,
        ):
            tb.addAction(a)
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
        tb.addSeparator()
        tb.addAction(self.act_wrap)
        tb.addAction(self.act_preview)
        tb.addAction(self.act_reload)
        self.addToolBar(tb)

    def _build_menubar(self):
        m = self.menuBar()
        filem = m.addMenu("&File")
        for a in (self.act_new, self.act_open):
            filem.addAction(a)
        filem.addMenu(self.recent_menu)
        filem.addSeparator()
        for a in (
            self.act_save,
            self.act_save_as,
            self.act_export_html,
            self.act_export_pdf,
        ):
            filem.addAction(a)
        filem.addSeparator()
        filem.addAction(self.act_quit)

        viewm = m.addMenu("&View")
        viewm.addAction(self.act_wrap)
        viewm.addAction(self.act_preview)

        helpm = m.addMenu("&Help")
        helpm.addAction(self.act_about)

    # ---------- Settings ----------
    def _load_settings(self):
        g = self._settings.value(SETTINGS_GEOMETRY)
        if isinstance(g, QByteArray):
            self.restoreGeometry(g)
        s = self._settings.value(SETTINGS_SPLITTER)
        if isinstance(s, QByteArray):
            self.splitter.restoreState(s)
        recents = self._settings.value(SETTINGS_RECENTS, [])
        if isinstance(recents, list):
            self.recent_files = [str(p) for p in recents if p]
        self._refresh_recent_menu()

    def _save_settings(self):
        self._settings.setValue(SETTINGS_GEOMETRY, self.saveGeometry())
        self._settings.setValue(SETTINGS_SPLITTER, self.splitter.saveState())
        self._settings.setValue(SETTINGS_RECENTS, self.recent_files[:MAX_RECENTS])

    def _refresh_recent_menu(self):
        self.recent_menu.clear()
        if not self.recent_files:
            a = QAction("(empty)", self)
            a.setEnabled(False)
            self.recent_menu.addAction(a)
            return
        for p in self.recent_files[:MAX_RECENTS]:
            action = QAction(
                p, self, triggered=lambda chk=False, x=p: self._open_recent(x)
            )
            self.recent_menu.addAction(action)

    def _open_recent(self, path_str: str):
        p = Path(path_str)
        if p.exists():
            self.open_file(p)
        else:
            QMessageBox.warning(self, "Missing", f"File not found:\n{p}")
            self._remove_from_recents(p)

    def _add_to_recents(self, path: Path):
        p = str(path)
        if p in self.recent_files:
            self.recent_files.remove(p)
        self.recent_files.insert(0, p)
        self.recent_files = self.recent_files[:MAX_RECENTS]
        self._refresh_recent_menu()

    def _remove_from_recents(self, path: Path):
        p = str(path)
        if p in self.recent_files:
            self.recent_files.remove(p)
            self._refresh_recent_menu()

    # ---------- File Ops ----------
    def new_file(self):
        if not self._confirm_discard():
            return
        self.editor.clear()
        self.current_path = None
        self._set_modified(False)
        self._update_title()
        self.render_preview()

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Markdown",
            "",
            "Markdown (*.md *.markdown *.mdown);;Text (*.txt);;All files (*)",
        )
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path):
        if not self._confirm_discard():
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open file:\n{e}")
            return
        self.editor.setPlainText(text)
        self.current_path = Path(path)
        self._set_modified(False)
        self._update_title()
        self.render_preview()
        self.statusBar().showMessage(f"Opened: {path}", 3000)
        self._add_to_recents(self.current_path)

    def save(self):
        if self.current_path is None:
            return self.save_as()
        return self._write_to(self.current_path)

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            str(self.current_path or ""),
            "Markdown (*.md);;All files (*)",
        )
        if not path:
            return False
        self.current_path = Path(path)
        ok = self._write_to(self.current_path)
        if ok:
            self._update_title()
            self._add_to_recents(self.current_path)
        return ok

    def _write_to(self, path: Path):
        # Atomic save with QSaveFile
        try:
            sf = QSaveFile(str(path))
            if not sf.open(QIODevice.OpenModeFlag.WriteOnly):
                raise IOError(f"Cannot open for write: {path}")
            data = self.editor.toPlainText().encode("utf-8")
            sf.write(data)
            if not sf.commit():
                raise IOError(f"Commit failed for: {path}")
            self._set_modified(False)
            self.statusBar().showMessage(f"Saved: {path}", 3000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")
            return False

    def export_html(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export HTML", "", "HTML (*.html *.htm);;All files (*)"
        )
        if not path:
            return
        html = self._render_html(self.editor.toPlainText())
        try:
            Path(path).write_text(html, encoding="utf-8")
            self.statusBar().showMessage(f"Exported HTML: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def export_pdf(self):
        # Choose output path
        default_name = (
            self.current_path.with_suffix(".pdf").name
            if self.current_path
            else "document.pdf"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default_name, "PDF (*.pdf)"
        )
        if not path:
            return

        # Prepare printer (PDF)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)

        # A4 portrait, 12.7 mm margins
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(12.7, 12.7, 12.7, 12.7),
            QPageLayout.Unit.Millimeter,
        )
        printer.setPageLayout(layout)

        # Render the same HTML used in preview to a QTextDocument and print it
        html = self._render_html(self.editor.toPlainText())
        doc = QTextDocument()
        doc.setHtml(html)
        try:
            doc.print(printer)  # blocks until written
            self.statusBar().showMessage(f"Exported PDF: {path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export PDF:\n{e}")
        finally:
            del doc  # ensure resources are freed

    # ---------- Markdown rendering ----------
    def _render_html(self, md_text: str) -> str:
        import markdown  # lazy import

        body = markdown.markdown(
            md_text,
            extensions=[
                "extra",  # tables, etc.
                "fenced_code",
                "codehilite",  # syntax highlighting (Pygments)
                "toc",  # [TOC] anchors
                "sane_lists",
                "smarty",
            ],
            extension_configs={"codehilite": {"guess_lang": True, "noclasses": True}},
            output_format="html5",
        )
        return HTML_TEMPLATE.format(css=PREVIEW_CSS, body=body)

    def render_preview(self):
        md_text = self.editor.toPlainText()
        html = self._render_html(md_text)
        self.preview.setHtml(html)

    def _on_text_changed(self):
        if not self.modified:
            self._set_modified(True)
            self._update_title()
        self._debounce.start()

    # ---------- Editor helpers ----------
    def toggle_wrap(self, on: bool):
        mode = (
            QTextEdit.LineWrapMode.WidgetWidth if on else QTextEdit.LineWrapMode.NoWrap
        )
        self.editor.setLineWrapMode(mode)

    def toggle_preview(self, on: bool):
        self.preview.setVisible(on)

    def _surround(self, left: str, right: str):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.insertText(left + right)
            cursor.movePosition(
                cursor.MoveOperation.Left, cursor.MoveMode.MoveAnchor, len(right)
            )
            self.editor.setTextCursor(cursor)
            return
        text = cursor.selectedText()
        cursor.insertText(f"{left}{text}{right}")

    def _prefix_line(self, prefix: str):
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(start)
            while cursor.position() <= end:
                cursor.movePosition(cursor.MoveOperation.StartOfLine)
                cursor.insertText(prefix)
                if not cursor.movePosition(cursor.MoveOperation.Down):
                    break
                end += len(prefix)
        else:
            cursor.movePosition(cursor.MoveOperation.StartOfLine)
            cursor.insertText(prefix)
        cursor.endEditBlock()

    def _confirm_discard(self) -> bool:
        if not self.modified:
            return True
        resp = QMessageBox.question(
            self,
            "Discard changes?",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return resp == QMessageBox.StandardButton.Yes

    def _set_modified(self, flag: bool):
        self.modified = flag
        self.setWindowModified(flag)

    def _update_title(self):
        name = self.current_path.name if self.current_path else "Untitled"
        star = " •" if self.modified else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    # ---------- Drag & Drop ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if not urls:
            return
        local = urls[0].toLocalFile()
        if local:
            self.open_file(Path(local))

    # ---------- Close ----------
    def closeEvent(self, event):
        if self._confirm_discard():
            self._save_settings()
            event.accept()
        else:
            event.ignore()

    # ---------- Help ----------
    def show_about(self):
        QMessageBox.information(
            self,
            "About",
            f"{APP_NAME}\n"
            "• Live preview (debounced)\n"
            "• Open/Save .md (atomic), Export HTML/PDF\n"
            "• Recent files, dark-mode aware preview\n"
            "• Simple formatting helpers\n\n"
            "Built with PyQt6 + python-markdown.",
        )


def main():
    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(sys.argv)
    # Optional: open a file passed as arg
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    win = MarkdownEditor(path)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
