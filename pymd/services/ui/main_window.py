from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QByteArray, QEvent, Qt
from PyQt6.QtGui import QAction, QKeyEvent, QKeySequence, QTextCursor
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

from pymd.domain.interfaces import IAppConfig, IFileService, IMarkdownRenderer, ISettingsService
from pymd.domain.models import Document
from pymd.services.exporters.base import ExporterRegistryInst, IExporterRegistry
from pymd.services.ui.about import AboutDialog
from pymd.services.ui.create_link import CreateLinkDialog
from pymd.services.ui.find_replace import FindReplaceDialog
from pymd.services.ui.plugins_dialog import InstalledPluginRow, PluginsDialog
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

    def __init__(self, window: "MainWindow") -> None:
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
    def get_plugin_setting(self, plugin_id: str, key: str, default: str | None = None) -> str | None:
        return self._w.settings.get_raw(f"plugins/{plugin_id}/{key}", default)

    def set_plugin_setting(self, plugin_id: str, key: str, value: str) -> None:
        self._w.settings.set_raw(f"plugins/{plugin_id}/{key}", value)

    # ---- theme (example capability for builtin theme plugin) ----
    def get_theme(self) -> str:
        return getattr(self._w, "_theme_id", "default")

    def list_themes(self) -> list[str]:
        return ["default", "midnight", "paper"]

    def set_theme(self, theme_id: str) -> None:
        self._w.apply_theme(theme_id)


class MainWindow(QMainWindow):
    """Thin PyQt window that delegates work to injected services (DIP)."""

    def __init__(
        self,
            *,
            app_title: str = "PyMarkdownEditor",
            config: IAppConfig,
            exporter_registry: IExporterRegistry | None = None,
            file_service: IFileService,
        renderer: IMarkdownRenderer,
        settings: ISettingsService,
        start_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(app_title)
        self.resize(1100, 700)

        self.renderer = renderer
        self.file_service = file_service
        self.settings = settings

        # ✅ IMPORTANT: store config before any use
        self.config: IAppConfig = config

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
        self._plugins_dialog_hooked: bool = False

        # Widgets
        self.editor = QTextEdit(self)
        self.editor.setAcceptRichText(False)
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))

        # Selection-aware UX shortcuts
        self.editor.installEventFilter(self)

        # Preview: prefer QWebEngineView, fallback to QTextBrowser
        self.preview = self._create_preview_widget()

        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Non-modal dialogs
        self.about_dialog = AboutDialog(config=self.config, parent=self)
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

        self._theme_id = self.settings.get_raw("ui/theme", "default") or "default"
        self.apply_theme(self._theme_id)

    # ----------------------- Container hook for plugins -----------------------

    def attach_plugins(self, *, plugin_manager: object | None, plugin_installer: object | None) -> None:
        """
        Ownership rule:
          - Bootstrapper owns plugin reload() for deterministic boot.
          - MainWindow.attach_plugins() must NOT call reload().
        """
        self.plugin_manager = plugin_manager
        self.plugin_installer = plugin_installer

        if self.plugin_manager is not None and hasattr(self.plugin_manager, "set_api"):
            try:
                self.plugin_manager.set_api(self._app_api)  # type: ignore[attr-defined]
            except Exception:
                pass

        self._rebuild_plugin_actions()

    # ----------------------------- UI creation -----------------------------

    def _build_actions(self) -> None:
        self.exit_action = QAction("&Exit", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Exit application")
        self.exit_action.triggered.connect(QApplication.instance().quit)  # type: ignore[union-attr]

        self.act_plugins = QAction("&Plugins…", self, triggered=self._show_plugins_manager)

        self.act_new = QAction("New", self, shortcut=QKeySequence.StandardKey.New, triggered=self._new_file)
        self.act_open = QAction("Open…", self, shortcut=QKeySequence.StandardKey.Open, triggered=self._open_dialog)
        self.act_save = QAction("Save", self, shortcut=QKeySequence.StandardKey.Save, triggered=self._save)
        self.act_save_as = QAction("Save As…", self, shortcut=QKeySequence.StandardKey.SaveAs, triggered=self._save_as)

        self.act_toggle_wrap = QAction("Toggle Wrap", self, checkable=True, checked=True, triggered=self._toggle_wrap)
        self.act_toggle_preview = QAction(
            "Toggle Preview", self, checkable=True, checked=True, triggered=self._toggle_preview
        )

        self.act_about = QAction("About…", self, triggered=self._show_about)

        self.export_actions: list[QAction] = []
        for exporter in self._exporters.all():
            act = QAction(exporter.label, self, triggered=lambda chk=False, e=exporter: self._export_with(e))
            self.export_actions.append(act)

        self.recent_menu = QMenu("Open Recent", self)

        self.act_bold = QAction("B", self, triggered=lambda: self._surround_selection("**", "**"))
        self.act_bold.setShortcut("Ctrl+B")

        self.act_italic = QAction("i", self, triggered=lambda: self._surround_selection("_", "_"))
        self.act_italic.setShortcut("Ctrl+I")

        self.act_code = QAction("`code`", self, triggered=self._insert_inline_code)
        self.act_code_block = QAction("codeblock", self, triggered=self._insert_code_block)

        self.act_code_block_simple = QAction(
            "Insert Code Block", self, shortcut="Ctrl+E", triggered=self._insert_fenced_code_block_simple
        )

        self.act_h1 = QAction("H1", self, triggered=lambda: self._toggle_header_prefix("# "))
        self.act_h2 = QAction("H2", self, triggered=lambda: self._toggle_header_prefix("## "))
        self.act_list = QAction("List", self, triggered=lambda: self._prefix_line("- "))
        self.act_img = QAction("Image", self, triggered=self._select_image)
        self.act_link = QAction("Link", self, triggered=self._create_link)
        self.act_table = QAction("Table", self, shortcut="Ctrl+Shift+T", triggered=self._insert_table)

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
            self.act_code_block_simple,
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

        helpm = m.addMenu("&Help")
        helpm.addAction(self.act_about)

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        if not self.recents:
            na = QAction("(empty)", self)
            na.setEnabled(False)
            self.recent_menu.addAction(na)
            return
        for p in self.recents[:MAX_RECENTS]:
            self.recent_menu.addAction(QAction(p, self, triggered=lambda chk=False, x=p: self._open_path(Path(x))))

    # ---------------------- UX: selection-aware shortcuts ----------------------

    def eventFilter(self, obj: object, event: object) -> bool:  # noqa: N802
        """
        Intercept editor key combos for selection-aware Markdown helpers.

        - Ctrl+B: toggle **selection**
        - Ctrl+I: toggle _selection_
        - Ctrl+V:
            * selection + URL in clipboard -> [selection](url)
            * no selection + URL in clipboard -> [](url) and place cursor inside []
        - Ctrl+E: insert fenced code block on new line
        """
        if obj is self.editor and isinstance(event, QKeyEvent):
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                mods = event.modifiers()

                ctrl_down = bool(mods & Qt.KeyboardModifier.ControlModifier) or bool(
                    mods & Qt.KeyboardModifier.MetaModifier
                )

                if ctrl_down and key == Qt.Key.Key_B:
                    self._surround_selection("**", "**")
                    return True

                if ctrl_down and key == Qt.Key.Key_I:
                    self._surround_selection("_", "_")
                    return True

                if ctrl_down and key == Qt.Key.Key_E:
                    self._insert_fenced_code_block_simple()
                    return True

                if ctrl_down and key == Qt.Key.Key_V:
                    if self._paste_as_markdown_link_if_applicable():
                        return True
                    # else let default paste happen

        return super().eventFilter(obj, event)  # type: ignore[misc]

    # ---------------------- UX: bold/italic toggles ----------------------

    def _surround_selection(self, left: str, right: str) -> None:
        c = self.editor.textCursor()
        if not c.hasSelection():
            return

        raw_sel = c.selectedText()
        sel = raw_sel.replace("\u2029", "\n")

        if left == "**" and right == "**":
            new_text = self._toggle_wrapped_text(sel, left="**", right="**")
        elif left == "_" and right == "_":
            new_text = self._toggle_italic_underscore(sel)
        else:
            new_text = self._toggle_wrapped_text(sel, left=left, right=right)

        c.beginEditBlock()
        try:
            c.insertText(new_text)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)

    def _toggle_wrapped_text(self, text: str, *, left: str, right: str) -> str:
        if text.startswith(left) and text.endswith(right) and len(text) >= len(left) + len(right):
            return text[len(left): -len(right)]
        return f"{left}{text}{right}"

    def _toggle_italic_underscore(self, text: str) -> str:
        if not text:
            return "_"

        if text.startswith("_") and text.endswith("_") and len(text) >= 2:
            return text[1:-1]

        stripped = text.strip()
        if stripped.startswith("_") and stripped.endswith("_") and len(stripped) >= 2:
            return stripped[1:-1]

        return f"_{text}_"

    # ---------------------- UX: header toggle ----------------------

    def _toggle_header_prefix(self, prefix: str) -> None:
        c = self.editor.textCursor()
        doc = self.editor.document()
        block = doc.findBlock(c.position())
        if not block.isValid():
            return

        line_text = block.text()

        existing = ""
        i = 0
        while i < len(line_text) and line_text[i] == "#" and i < 6:
            i += 1
        if i > 0 and i < len(line_text) and line_text[i] == " ":
            existing = "#" * i + " "

        replacement_prefix = "" if existing == prefix else prefix

        c.beginEditBlock()
        try:
            line_start = block.position()
            cur = QTextCursor(doc)
            cur.setPosition(line_start)

            if existing:
                cur.movePosition(
                    QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, len(existing)
                )
                cur.removeSelectedText()
                cur.clearSelection()

            if replacement_prefix:
                cur.insertText(replacement_prefix)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)

    # ---------------------- UX: paste URL as markdown link ----------------------

    def _clipboard_text(self) -> str:
        cb = QApplication.clipboard()
        return (cb.text() or "").strip()

    def _looks_like_url(self, text: str) -> bool:
        t = text.strip()
        if not t:
            return False
        lower = t.lower()
        return lower.startswith("http://") or lower.startswith("https://") or lower.startswith("www.")

    def _normalize_url(self, text: str) -> str:
        t = text.strip()
        if t.lower().startswith("www."):
            return "https://" + t
        return t

    def _paste_as_markdown_link_if_applicable(self) -> bool:
        """
        Ctrl+V smart paste:
          - selection + URL -> [selection](url)
          - no selection + URL -> [](url) with cursor placed inside []
        Returns True if handled, False if caller should fall back to default paste.
        """
        clip = self._clipboard_text()
        if not self._looks_like_url(clip):
            return False

        url = self._normalize_url(clip)

        c = self.editor.textCursor()

        # Case 1: selection exists -> [sel](url)
        if c.hasSelection():
            sel = c.selectedText().replace("\u2029", "\n").strip()
            if not sel:
                return False
            c.beginEditBlock()
            try:
                c.insertText(f"[{sel}]({url})")
            finally:
                c.endEditBlock()
            self.editor.setTextCursor(c)
            return True

        # Case 2: no selection -> [](url) and move cursor inside []
        c.beginEditBlock()
        try:
            insert_pos = c.position()
            md = f"[]({url})"
            c.insertText(md)

            # Move cursor to between [ and ]
            # inserted text length is len(md); we want position: insert_pos + 1
            c.setPosition(insert_pos + 1)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)
        return True

    # ---------------------- UX: code block insert ----------------------

    def _insert_fenced_code_block_simple(self) -> None:
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

            c.insertText("```\n\n```\n")
            c.movePosition(c.MoveOperation.PreviousBlock)
            c.movePosition(c.MoveOperation.PreviousBlock)
            c.movePosition(c.MoveOperation.EndOfBlock)
        finally:
            c.endEditBlock()

        self.editor.setTextCursor(c)

    # ----------------------------- Plugins UI -----------------------------

    def _show_plugins_manager(self) -> None:
        if self.plugin_manager is None or self.plugin_installer is None:
            QMessageBox.information(self, "Plugins", "Plugin management is not available in this build.")
            return

        if not hasattr(self.plugin_manager, "state_store") or not hasattr(self.plugin_manager, "reload"):
            QMessageBox.information(
                self,
                "Plugins",
                "Plugin manager is not compatible with this UI (missing expected APIs).",
            )
            return

        if self._plugins_dialog is None:

            def _get_installed() -> Iterable[InstalledPluginRow]:
                rows = self.plugin_manager.get_installed_rows()  # type: ignore[attr-defined]
                return rows  # type: ignore[return-value]

            self._plugins_dialog = PluginsDialog(
                parent=self,
                state=self.plugin_manager.state_store,  # type: ignore[attr-defined]
                pip=self.plugin_installer,
                get_installed=_get_installed,  # type: ignore[arg-type]
                reload_plugins=self.plugin_manager.reload,  # type: ignore[attr-defined]
                catalog=getattr(self.plugin_manager, "catalog", None),
            )

        if not self._plugins_dialog_hooked:
            self._plugins_dialog.finished.connect(lambda _=0: self._rebuild_plugin_actions())  # type: ignore[arg-type]
            self._plugins_dialog_hooked = True

        self._plugins_dialog.show()
        self._plugins_dialog.raise_()
        self._plugins_dialog.activateWindow()

    def _rebuild_plugin_actions(self) -> None:
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

    def _show_about(self) -> None:
        self.about_dialog.show()
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

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

    def _insert_inline_code(self) -> None:
        c = self.editor.textCursor()
        if c.hasSelection():
            sel = c.selectedText().replace("\u2029", "\n")
            c.insertText(f"`{sel}`")
        else:
            c.insertText("`")
        self.editor.setTextCursor(c)

    def _insert_code_block(self) -> None:
        languages = ["", "php", "javascript", "typescript", "java", "c", "cpp", "csharp", "python", "ruby", "scala"]

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
            c.movePosition(c.MoveOperation.PreviousBlock)
            c.movePosition(c.MoveOperation.PreviousBlock)
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

    # ----------------------------- File ops -----------------------------

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
        path_str, _ = QFileDialog.getSaveFileName(self, "Save As", start, "Markdown (*.md);;All files (*)")
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
            self.statusBar().showMessage(f"Saved: {path}", 3000)  # type: ignore[union-attr]
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")
            return False

    def _export_with(self, exporter: Any) -> None:
        default = self.doc.path.with_suffix(
            f".{exporter.file_ext}").name if self.doc.path else f"document.{exporter.name}"
        filt = f"{exporter.name.upper()} (*.{exporter.file_ext})"
        out_str, _ = QFileDialog.getSaveFileName(self, exporter.label, default, filt)
        if not out_str:
            return
        html = self.renderer.to_html(self.editor.toPlainText())
        try:
            exporter.export(html, Path(out_str))
            self.statusBar().showMessage(f"Exported {exporter.name.upper()}: {out_str}",
                                         3000)  # type: ignore[union-attr]
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export {exporter.name.upper()}:\n{e}")

    def _toggle_wrap(self, on: bool) -> None:
        mode = QTextEdit.LineWrapMode.WidgetWidth if on else QTextEdit.LineWrapMode.NoWrap
        self.editor.setLineWrapMode(mode)

    def _toggle_preview(self, on: bool) -> None:
        self.preview.setVisible(on)

    # ----------------------------- Helpers -----------------------------

    def _render_preview(self) -> None:
        html = self.renderer.to_html(self.editor.toPlainText())
        self.preview.setHtml(html)  # type: ignore[attr-defined]

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
        disable_webengine = (
                os.environ.get("PYMD_DISABLE_WEBENGINE", "").strip() == "1"
                or "PYTEST_CURRENT_TEST" in os.environ
        )

        if disable_webengine:
            w = QTextBrowser(self)
            w.setOpenExternalLinks(True)
            return w

        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore

            return QWebEngineView(self)
        except Exception:
            w = QTextBrowser(self)
            w.setOpenExternalLinks(True)
            return w

    # ----------------------------- Themes -----------------------------

    def apply_theme(self, theme_id: str) -> None:
        self._theme_id = theme_id
        self.settings.set_raw("ui/theme", theme_id)

        if theme_id == "default":
            self.setStyleSheet("")
            return

        if theme_id == "midnight":
            self.setStyleSheet(
                """
                QMainWindow { background: #1e1e1e; }
                QTextEdit { background: #111; color: #e6e6e6; border: 1px solid #333; }
                QTextBrowser { background: #111; color: #e6e6e6; border: 1px solid #333; }
                QMenuBar, QMenu { background: #1e1e1e; color: #e6e6e6; }
                QToolBar { background: #1e1e1e; border: none; }
                """
            )
            return

        if theme_id == "paper":
            self.setStyleSheet(
                """
                QMainWindow { background: #fafafa; }
                QTextEdit { background: #ffffff; color: #111; border: 1px solid #ddd; }
                QTextBrowser { background: #ffffff; color: #111; border: 1px solid #ddd; }
                QMenuBar, QMenu { background: #fafafa; color: #111; }
                QToolBar { background: #fafafa; border: none; }
                """
            )
            return
