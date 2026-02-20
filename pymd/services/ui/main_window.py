from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

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
from pymd.services.ui.plugins_dialog import PluginsDialog
from pymd.services.ui.table_dialog import TableDialog
from pymd.utils.constants import MAX_RECENTS

# Plugin API is a stable contract; the concrete adapter stays inside the app.
try:
    from pymd.plugins.api import IAppAPI  # type: ignore
except Exception:  # pragma: no cover
    IAppAPI = object  # type: ignore[misc]


class _QtAppAPI(IAppAPI):  # type: ignore[misc]
    """
    Stable capabilities exposed to plugins. This is the only place that touches Qt.

    NOTE: We intentionally use ISettingsService.get_raw/set_raw to avoid poking into
    SettingsService internals (keeps mypy/ruff happy).
    """

    def __init__(self, window: MainWindow) -> None:
        self._w = window

    # ---- document/text ops ----
    def get_current_text(self) -> str:
        return self._w.editor.toPlainText()

    def set_current_text(self, text: str) -> None:
        self._w.editor.setPlainText(text)

    def insert_text_at_cursor(self, text: str) -> None:
        c = self._w.editor.textCursor()
        c.insertText(text)
        self._w.editor.setTextCursor(c)

    # ---- messaging ----
    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self._w, title, message)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self._w, title, message)

    # ---- export ----
    def export_current(self, exporter_id: str) -> None:
        exporter = self._w._exporters.get(exporter_id)
        self._w._export_with(exporter)

    # ---- plugin settings (namespaced) ----
    def get_plugin_setting(
        self, plugin_id: str, key: str, default: str | None = None
    ) -> str | None:
        return self._w.settings.get_raw(f"plugins/{plugin_id}/{key}", default)

    def set_plugin_setting(self, plugin_id: str, key: str, value: str) -> None:
        self._w.settings.set_raw(f"plugins/{plugin_id}/{key}", value)


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

        # Exporter registry instance (per-instance; test-friendly)
        self._exporters: IExporterRegistry = exporter_registry or ExporterRegistryInst()

        self.doc = Document(path=None, text="", modified=False)
        self.recents: list[str] = self.settings.get_recent()

        # Plugins (wired by container via attach_plugins)
        self._app_api = _QtAppAPI(self)
        self.plugin_manager: object | None = None
        self.plugin_installer: object | None = None
        self._plugins_dialog: PluginsDialog | None = None
        self._plugins_menu: QMenu | None = None
        self._plugin_action_qactions: list[QAction] = []

        # Widgets
        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(False)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))

        # Preview: prefer QWebEngineView, fallback to QTextBrowser
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

    # ----------------------- Container hook for plugins -----------------------

    def attach_plugins(
        self, *, plugin_manager: object | None, plugin_installer: object | None
    ) -> None:
        self.plugin_manager = plugin_manager
        self.plugin_installer = plugin_installer
        self._rebuild_plugin_actions()

    # ----------------------------- UI creation -----------------------------

    def _build_actions(self) -> None:
        self.exit_action = QAction("&Exit", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Exit application")
        self.exit_action.triggered.connect(QApplication.instance().quit)

        # Plugins manager action
        self.act_plugins = QAction("&Plugins…", self, triggered=self._show_plugins_manager)

        # File actions
        self.act_new = QAction(
            "New", self, shortcut=QKeySequence.StandardKey.New, triggered=self._new_file
        )
        self.act_open = QAction(
            "Open…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self._open_dialog
        )
        self.act_save = QAction(
            "Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self._save
        )
        self.act_save_as = QAction(
            "Save As…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=self._save_as
        )

        self.act_toggle_wrap = QAction(
            "Toggle Wrap", self, checkable=True, checked=True, triggered=self._toggle_wrap
        )
        self.act_toggle_preview = QAction(
            "Toggle Preview", self, checkable=True, checked=True, triggered=self._toggle_preview
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

        # Formatting actions
        self.act_bold = QAction("B", self, triggered=lambda: self._surround("**", "**"))
        self.act_italic = QAction("i", self, triggered=lambda: self._surround("*", "*"))
        self.act_code = QAction("`code`", self, triggered=self._insert_inline_code)
        self.act_code_block = QAction("codeblock", self, triggered=self._insert_code_block)
        self.act_h1 = QAction("H1", self, triggered=lambda: self._prefix_line("# "))
        self.act_h2 = QAction("H2", self, triggered=lambda: self._prefix_line("## "))
        self.act_list = QAction("List", self, triggered=lambda: self._prefix_line("- "))
        self.act_img = QAction("Image", self, triggered=self._select_image)
        self.act_link = QAction("Link", self, triggered=self._create_link)
        self.act_table = QAction(
            "Table", self, shortcut="Ctrl+Shift+T", triggered=self._insert_table
        )

        # Find/Replace actions with standard shortcuts
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

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tbf = QToolBar("Formatting", self)
        tb.setMovable(False)

        for a in (self.act_new, self.act_open, self.act_save, self.act_save_as):
            tb.addAction(a)
        for a in self.export_actions:
            tb.addAction(a)
        tb.addSeparator()

        for a in (self.act_find, self.act_find_prev, self.act_find_next, self.act_replace):
            tb.addAction(a)
        tb.addSeparator()

        tb.addAction(self.act_toggle_wrap)
        tb.addAction(self.act_toggle_preview)

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

        self.addToolBar(tb)
        self.addToolBarBreak()
        self.addToolBar(tbf)

    def _build_menu(self) -> None:
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
        filem.addSeparator()
        filem.addAction(self.exit_action)
        self._refresh_recent_menu()

        editm = m.addMenu("&Edit")
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
        for a in (self.act_find, self.act_find_prev, self.act_find_next, self.act_replace):
            editm.addAction(a)

        viewm = m.addMenu("&View")
        viewm.addAction(self.act_toggle_wrap)
        viewm.addAction(self.act_toggle_preview)

        toolsm = m.addMenu("&Tools")
        toolsm.addAction(self.act_plugins)
        toolsm.addSeparator()
        self._plugins_menu = toolsm

    def _refresh_recent_menu(self) -> None:
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

    # ----------------------------- Plugins UI -----------------------------

    def _show_plugins_manager(self) -> None:
        # Plugins UI is optional; show a clear message if missing wiring.
        if self.plugin_manager is None or self.plugin_installer is None:
            QMessageBox.information(
                self,
                "Plugins",
                "Plugin management is not available in this build.",
            )
            return

        if self._plugins_dialog is None:
            self._plugins_dialog = PluginsDialog(
                parent=self,
                # PluginsDialog expects these DI-provided collaborators:
                state=self.plugin_manager.state_store,  # type: ignore[attr-defined]
                pip=self.plugin_installer,  # QtPipInstaller implements the right signals
                get_installed=self.plugin_manager.get_installed_rows,  # type: ignore[attr-defined]
                reload_plugins=self.plugin_manager.reload,  # type: ignore[attr-defined]
                catalog=getattr(self.plugin_manager, "catalog", None),  # type: ignore[attr-defined]
            )
        self._plugins_dialog.show()
        self._plugins_dialog.raise_()
        self._plugins_dialog.activateWindow()

    def _on_plugins_changed(self) -> None:
        self._rebuild_plugin_actions()
        self._render_preview()

    def _rebuild_plugin_actions(self) -> None:
        """
        Populate Tools menu with actions from enabled plugins.

        Supported manager shapes (any one):
          - iter_enabled_actions(app_api) -> iterable[(spec, handler)]
          - iter_actions(app_api)         -> iterable[(spec, handler)]
          - iter_enabled_actions()        -> iterable[(spec, handler)]
          - iter_actions()               -> iterable[(spec, handler)]
        """
        if self._plugins_menu is None:
            return

        for act in self._plugin_action_qactions:
            try:
                self._plugins_menu.removeAction(act)
            except Exception:
                pass
        self._plugin_action_qactions.clear()

        pm = self.plugin_manager
        if pm is None:
            return

        def _get_actions() -> Iterable[tuple[Any, Callable[..., Any]]]:
            for name in ("iter_enabled_actions", "iter_actions"):
                if not hasattr(pm, name):
                    continue
                fn = getattr(pm, name)
                try:
                    return fn(self._app_api)  # type: ignore[misc]
                except TypeError:
                    try:
                        return fn()  # type: ignore[misc]
                    except Exception:
                        continue
                except Exception:
                    continue
            return ()

        for spec, handler in _get_actions() or []:
            title = getattr(spec, "title", None) or getattr(spec, "name", None) or "Plugin Action"
            shortcut = getattr(spec, "shortcut", None)
            status_tip = getattr(spec, "status_tip", None)

            act = QAction(str(title), self)
            if shortcut:
                act.setShortcut(str(shortcut))
            if status_tip:
                act.setStatusTip(str(status_tip))

            def _make_trigger(fn: Callable[..., Any]) -> Callable[[], None]:
                def _run() -> None:
                    try:
                        fn(self._app_api)  # type: ignore[misc]
                    except TypeError:
                        try:
                            fn()  # type: ignore[misc]
                        except Exception as e:
                            QMessageBox.critical(self, "Plugin Error", f"{e}")
                    except Exception as e:
                        QMessageBox.critical(self, "Plugin Error", f"{e}")

                return _run

            act.triggered.connect(_make_trigger(handler))
            self._plugins_menu.addAction(act)
            self._plugin_action_qactions.append(act)

    # ----------------------------- Actions -----------------------------

    def _show_find(self) -> None:
        self.find_dialog.show_find()

    def _show_replace(self) -> None:
        self.find_dialog.show_replace()

    def _select_image(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select image to add",
            "",
            "PNG (*.png);;JPEG (*.jpeg *.jpg);;All files (*)",
        )
        if not path_str:
            return
        c = self.editor.textCursor()
        c.insertText(f'<img src="{path_str}" width="300" alt="Alt Text" />')
        self.editor.setTextCursor(c)

    def _create_link(self) -> None:
        self.link_dialog.show_create_link()

    def _insert_table(self) -> None:
        self.table_dialog.show_table_dialog()

    def _surround(self, left: str, right: str) -> None:
        c = self.editor.textCursor()
        if not c.hasSelection():
            return
        sel = c.selectedText()
        c.insertText(f"{left}{sel}{right}")
        self.editor.setTextCursor(c)

    def _insert_inline_code(self) -> None:
        c = self.editor.textCursor()
        if c.hasSelection():
            sel = c.selectedText()
            c.insertText(f"`{sel}`")
        else:
            c.insertText("`")
        self.editor.setTextCursor(c)

    def _insert_code_block(self) -> None:
        languages = [
            "",
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

        lang_suffix = (lang or "").strip()
        first_line = f"```{lang_suffix}" if lang_suffix else "```"

        c = self.editor.textCursor()
        c.beginEditBlock()
        try:
            if c.position() > 0:
                original_pos = c.position()
                c.movePosition(c.MoveOperation.Left, c.MoveMode.KeepAnchor, 1)
                prev = c.selectedText()
                c.clearSelection()
                c.setPosition(original_pos)
                if prev not in ("\u2029", "\n"):
                    c.insertText("\n")

            c.insertText(first_line + "\n\n```\n")

            c.movePosition(c.MoveOperation.PreviousBlock)  # closing fence
            c.movePosition(c.MoveOperation.PreviousBlock)  # blank line
            c.movePosition(c.MoveOperation.EndOfBlock)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)

    def _prefix_line(self, prefix: str) -> None:
        c = self.editor.textCursor()
        doc = self.editor.document()

        if not c.hasSelection():
            c.beginEditBlock()
            c.movePosition(c.MoveOperation.StartOfLine)
            c.insertText(prefix)
            c.endEditBlock()
            self.editor.setTextCursor(c)
            return

        start = min(c.selectionStart(), c.selectionEnd())
        end = max(c.selectionStart(), c.selectionEnd())
        end_inclusive_pos = max(0, end - 1)

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end_inclusive_pos)

        cur = QTextCursor(start_block)
        cur.beginEditBlock()
        try:
            block = start_block
            while block.isValid():
                cur.setPosition(block.position())
                cur.insertText(prefix)
                if block == end_block:
                    break
                block = block.next()
        finally:
            cur.endEditBlock()

        self.editor.setTextCursor(c)

    def _new_file(self) -> None:
        if not self._confirm_discard():
            return
        self.doc = Document(path=None, text="", modified=False)
        self.editor.setPlainText("")
        self._update_title()
        self._render_preview()

    def _open_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Markdown",
            "",
            "Markdown (*.md *.markdown *.mdown);;Text (*.txt);;All files (*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _open_path(self, path: Path) -> None:
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

    def _save(self) -> None:
        if self.doc.path is None:
            self._save_as()
            return
        self._write_to(self.doc.path)

    def _save_as(self) -> None:
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

    def _export_with(self, exporter: Any) -> None:
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

    def _toggle_wrap(self, on: bool) -> None:
        mode = QTextEdit.LineWrapMode.WidgetWidth if on else QTextEdit.LineWrapMode.NoWrap
        self.editor.setLineWrapMode(mode)

    def _toggle_preview(self, on: bool) -> None:
        self.preview.setVisible(on)

    # ----------------------------- Helpers -----------------------------

    def _render_preview(self) -> None:
        html = self.renderer.to_html(self.editor.toPlainText())
        self.preview.setHtml(html)

    def _on_text_changed(self) -> None:
        self.doc.modified = True
        self._update_title()
        self._render_preview()

    def _update_title(self) -> None:
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

    def _add_recent(self, path: Path) -> None:
        s = str(path)
        if s in self.recents:
            self.recents.remove(s)
        self.recents.insert(0, s)
        self.recents = self.recents[:MAX_RECENTS]
        self.settings.set_recent(self.recents)
        self._refresh_recent_menu()

    # ----------------------------- DnD -----------------------------

    def dragEnterEvent(self, e: Any) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: Any) -> None:
        urls = e.mimeData().urls()
        if not urls:
            return
        local = urls[0].toLocalFile()
        if local:
            self._open_path(Path(local))

    # ----------------------------- Close -----------------------------

    def closeEvent(self, event: Any) -> None:
        self.settings.set_geometry(bytes(self.saveGeometry()))
        self.settings.set_splitter(bytes(self.splitter.saveState()))
        super().closeEvent(event)

    # ---------------------- Internal: preview creation ----------------------

    def _create_preview_widget(self) -> Any:
        """
        Prefer QWebEngineView (JS-capable: MathJax/KaTeX, better CSS),
        fall back to QTextBrowser. Guard imports so the app runs without WebEngine.
        """
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore

            return QWebEngineView(self)
        except Exception:
            w = QTextBrowser(self)
            w.setOpenExternalLinks(True)
            return w
