from __future__ import annotations

import math
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from PyQt6.QtCore import QByteArray, QSettings, Qt
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
from pymd.services.focus import (
    FocusSessionService,
    FocusStatus,
    SessionWriter,
    StartSessionRequest,
    TimerSettings,
)
from pymd.services.ui.create_link import CreateLinkDialog
from pymd.services.ui.find_replace import FindReplaceDialog
from pymd.services.ui.floating_timer_window import FloatingTimerWindow
from pymd.services.ui.focus_dialogs import StartSessionDialog, TimerSettingsDialog
from pymd.services.ui.table_dialog import TableDialog
from pymd.utils.constants import MAX_RECENTS

SUMMARY_LABEL_WORK_ITEM = "Work item"
SUMMARY_LABEL_WHEN = "When"
SUMMARY_LABEL_STATUS = "Status"
SUMMARY_LABEL_TIME = "Time"
SUMMARY_LABEL_INTERRUPTION = "Interruptions"
SUMMARY_LABEL_SESSION = "Session"


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
        self.timer_settings = TimerSettings(self._resolve_qsettings(settings))
        self.session_writer = SessionWriter(self.file_service)
        self.focus_service = FocusSessionService(
            writer=self.session_writer,
            timer_settings=self.timer_settings,
            save_active_note=self._save_active_session_note,
            on_finish_sound=self._play_finish_sound,
            parent=self,
        )
        self.timer_window = FloatingTimerWindow(self)
        self.timer_window.hide()
        self._alarm_sound_effects: dict[str, object] = {}
        self._alarm_sound_path: Path | None = None
        self._alarm_media_player = None
        self._alarm_audio_output = None
        self.timer_window.pause_resume_clicked.connect(self._toggle_focus_pause_resume)
        self.timer_window.stop_clicked.connect(self._stop_focus_session)
        self.focus_service.tick.connect(self._on_focus_tick)
        self.focus_service.state_changed.connect(self._on_focus_state_changed)
        self.focus_service.session_started.connect(self._on_focus_started)
        self.focus_service.session_stopped.connect(self._on_focus_stopped)
        self.focus_service.stop_failed.connect(self._on_focus_stop_failed)
        self._shutdown_persisted = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_app_about_to_quit)

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

        # Timer actions
        self.act_start_focus = QAction(
            "Start Focus Session…", self, triggered=self._start_focus_session
        )
        self.act_pause_resume_focus = QAction(
            "Pause", self, triggered=self._toggle_focus_pause_resume
        )
        self.act_pause_resume_focus.setEnabled(False)
        self.act_stop_focus = QAction("Stop & Save", self, triggered=self._stop_focus_session)
        self.act_stop_focus.setEnabled(False)
        self.act_timer_settings = QAction(
            "Timer Settings…", self, triggered=self._open_timer_settings
        )

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

        timerm = m.addMenu("&Timer")
        timerm.addAction(self.act_start_focus)
        timerm.addSeparator()
        timerm.addAction(self.act_pause_resume_focus)
        timerm.addAction(self.act_stop_focus)
        timerm.addSeparator()
        timerm.addAction(self.act_timer_settings)

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
        if self._is_session_note_locked():
            self._show_session_lock_warning("create a new file")
            return
        if not self._confirm_discard():
            return
        self.doc = Document(path=None, text="", modified=False)
        self._set_editor_text_safely("")
        self.doc.modified = False
        self._update_title()
        self._render_preview()

    def _open_dialog(self):
        if self._is_session_note_locked():
            self._show_session_lock_warning("open another file")
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Markdown",
            "",
            "Markdown (*.md *.markdown *.mdown);;Text (*.txt);;All files (*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _open_path(self, path: Path, *, confirm_discard: bool = True) -> bool:
        if self._is_session_note_locked() and not self._is_current_session_note_path(path):
            self._show_session_lock_warning("open another file")
            return False
        if confirm_discard and not self._confirm_discard():
            return False
        try:
            text = self.file_service.read_text(path)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open file:\n{e}")
            return False
        self.doc = Document(path=path, text=text, modified=False)
        self._set_editor_text_safely(text)
        self.doc.modified = False
        self._update_title()
        self._render_preview()
        self._add_recent(path)
        return True

    def _save(self):
        if self.doc.path is None:
            self._save_as()
            return
        self._write_to(self.doc.path)

    def _save_as(self):
        if self._is_session_note_locked():
            self._show_session_lock_warning("save this session under a different filename")
            return
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

    def _write_to(self, path: Path, *, silent: bool = False) -> bool:
        try:
            self.file_service.write_text_atomic(path, self.editor.toPlainText())
            self.doc.modified = False
            self._update_title()
            if not silent:
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

    def _set_editor_text_safely(self, text: str) -> None:
        was_blocked = self.editor.blockSignals(True)
        try:
            self.editor.setPlainText(text)
        finally:
            self.editor.blockSignals(was_blocked)

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

    # ---------- Focus Session ----------
    def _start_focus_session(self) -> None:
        if not self._confirm_discard():
            return

        dlg = StartSessionDialog(
            timer_settings=self.timer_settings,
            current_note_path=self.doc.path,
            parent=self,
        )
        result = dlg.get_result()
        if result is None:
            return

        if self.focus_service.is_active and not self._confirm_replace_active_session():
            return

        if self.focus_service.is_active:
            self._stop_focus_session()

        existing_note_path: Path | None = None
        if result.use_current_note:
            if self.doc.path is None:
                QMessageBox.information(
                    self,
                    "Save Required",
                    "Save this note first, then start a timer on it.",
                )
                return
            existing_note_path = self.doc.path

        req = StartSessionRequest(
            title=result.title,
            tag=result.tag,
            folder=result.folder,
            focus_minutes=result.focus_minutes,
            break_minutes=result.break_minutes,
            existing_note_path=existing_note_path,
        )
        try:
            state = self.focus_service.start_session(req)
            if self.doc.path != state.note_path:
                self._open_path(state.note_path, confirm_discard=False)
            self.timer_settings.set_default_folder(result.folder)
        except Exception as e:
            QMessageBox.critical(self, "Timer Error", f"Failed to start session:\n{e}")

    def _toggle_focus_pause_resume(self) -> None:
        state = self.focus_service.state
        if not state or state.stopped:
            return
        if state.paused:
            self.focus_service.resume()
        else:
            self.focus_service.pause()

    def _stop_focus_session(self) -> None:
        self.focus_service.stop()

    def _open_timer_settings(self) -> None:
        dlg = TimerSettingsDialog(timer_settings=self.timer_settings, parent=self)
        dlg.exec()

    def _on_focus_started(self, state) -> None:
        self.timer_window.set_paused(False)
        self.timer_window.set_countdown(state.remaining_seconds)
        pos = self.timer_settings.get_timer_window_pos()
        if pos is not None:
            self.timer_window.move(pos)
        self.timer_window.show()
        self.timer_window.raise_()
        self.statusBar().showMessage(f"Focus started: {state.preset_label}", 3000)

    def _on_focus_stopped(self, entry: dict[str, object]) -> None:
        self._persist_timer_window_pos()
        self.timer_window.hide()
        duration = entry.get("duration_min")
        self.statusBar().showMessage(f"Session saved ({duration} min)", 3000)

    def _on_focus_state_changed(self, is_active: bool, is_paused: bool) -> None:
        self.act_pause_resume_focus.setEnabled(is_active)
        self.act_pause_resume_focus.setText("Resume" if is_paused else "Pause")
        self.act_stop_focus.setEnabled(is_active)
        self.timer_window.set_paused(is_paused)
        self._set_session_lock_ui(is_active)
        state = self.focus_service.state
        if state is not None and (is_active or state.stopped):
            self._upsert_session_runtime_stats(state)

    def _on_focus_tick(self, remaining_seconds: int, total_seconds: int) -> None:
        self.timer_window.set_countdown(remaining_seconds)
        self.timer_window.set_color_state(
            self._color_level_for_remaining(remaining_seconds, total_seconds)
        )

    def _save_active_session_note(self) -> bool:
        state = self.focus_service.state
        if not state or state.stopped:
            return False
        if self.doc.path is None or self.doc.path != state.note_path:
            return False
        return self._write_to(state.note_path, silent=True)

    def _on_focus_stop_failed(self, message: str) -> None:
        self.statusBar().showMessage(message, 5000)
        QMessageBox.warning(self, "Session Stop Warning", message)

    def _safe_autosave(self) -> bool:
        return self.focus_service.safe_autosave()

    def _on_app_about_to_quit(self) -> None:
        self._persist_shutdown_state()

    # ---------- DnD ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if self._is_session_note_locked():
            self._show_session_lock_warning("open dropped files")
            return
        urls = e.mimeData().urls()
        if not urls:
            return
        local = urls[0].toLocalFile()
        if local:
            self._open_path(Path(local))

    # ---------- Close ----------
    def closeEvent(self, event):
        self._persist_shutdown_state()
        self.settings.set_geometry(bytes(self.saveGeometry()))
        self.settings.set_splitter(bytes(self.splitter.saveState()))
        super().closeEvent(event)

    def _resolve_qsettings(self, settings: ISettingsService) -> QSettings:
        qsettings = getattr(settings, "qsettings", None)
        if isinstance(qsettings, QSettings):
            return qsettings
        qsettings = getattr(settings, "_s", None)
        if isinstance(qsettings, QSettings):
            return qsettings
        return QSettings()

    def _is_session_note_locked(self) -> bool:
        return self.focus_service.is_active

    def _is_current_session_note_path(self, path: Path) -> bool:
        state = self.focus_service.state
        return state is not None and not state.stopped and state.note_path == path

    def _show_session_lock_warning(self, action: str) -> None:
        QMessageBox.information(
            self,
            "Session Locked",
            f"Stop the active focus session before trying to {action}.",
        )

    def _confirm_replace_active_session(self) -> bool:
        resp = QMessageBox.question(
            self,
            "Replace active session?",
            "A focus session is active. Stop it and start a new one?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return resp == QMessageBox.StandardButton.Yes

    def _set_session_lock_ui(self, locked: bool) -> None:
        self.act_new.setEnabled(not locked)
        self.act_open.setEnabled(not locked)
        self.act_save_as.setEnabled(not locked)
        self.recent_menu.setEnabled(not locked)

    def _persist_timer_window_pos(self) -> None:
        if self.timer_window.isVisible():
            self.timer_settings.set_timer_window_pos(self.timer_window.pos())

    def _persist_shutdown_state(self) -> None:
        if self._shutdown_persisted:
            return
        self._shutdown_persisted = True
        self._safe_autosave()
        self.focus_service.stop()
        self._persist_timer_window_pos()

    def _upsert_session_runtime_stats(self, state) -> None:
        work_item = self._infer_work_item(state)
        session_date = state.start_at.date().isoformat()
        block = self._build_session_footer_block(
            state, work_item=work_item, session_date=session_date
        )
        text = self._strip_legacy_focus_blocks(self.editor.toPlainText().rstrip())
        next_text = self._replace_or_append_summary_block(
            text=text,
            replacement_block=block,
            session_date=session_date,
            work_item=work_item,
        )
        self.editor.setPlainText(next_text + "\n")
        if self.doc.path is not None:
            self._write_to(self.doc.path, silent=True)

    def _build_session_footer_block(self, state, *, work_item: str, session_date: str) -> str:
        expected_seconds = state.expected_focus_seconds
        actual_seconds = state.actual_focus_seconds
        interrupt_seconds = state.break_total_seconds()
        expected = self._format_seconds(expected_seconds)
        actual = self._format_seconds(actual_seconds)
        break_total = self._format_seconds(interrupt_seconds)
        start_iso = state.start_at.isoformat(timespec="seconds")
        end_label = "in progress"
        if state.stopped and state.stopped_at is not None:
            end_label = state.stopped_at.isoformat(timespec="seconds")
        status_label = self._status_text(state)
        status_key = state.status().value
        lines = [
            "---",
            "",
            f"### Focus Session ({session_date})",
            "",
            f"**{SUMMARY_LABEL_WORK_ITEM}:** {work_item}  ",
            f"**{SUMMARY_LABEL_WHEN}:** start `{start_iso}` | end `{end_label}`  ",
            f"**{SUMMARY_LABEL_STATUS}:** {status_label}  ",
            f"**{SUMMARY_LABEL_TIME}:** actual **{actual}** vs expected **{expected}**  ",
            (
                f"**{SUMMARY_LABEL_INTERRUPTION}:** **{state.interruptions}** "
                f"(total **{break_total}**)  "
            ),
            (
                f"**{SUMMARY_LABEL_SESSION}:** preset `{state.preset_label}` "
                f"| id `{state.session_id}`"
            ),
            "<!-- focus-meta:",
            f"status={status_key}",
            f"actual_seconds={actual_seconds}",
            f"expected_seconds={expected_seconds}",
            f"interruptions={state.interruptions}",
            f"interrupt_seconds={interrupt_seconds}",
            "-->",
            "",
        ]
        return "\n".join(lines)

    def _format_seconds(self, seconds: int) -> str:
        minutes, sec = divmod(max(0, int(seconds)), 60)
        return f"{minutes}m {sec}s"

    def _strip_legacy_focus_blocks(self, text: str) -> str:
        old_stats_pattern = re.compile(
            r"\n*<!-- focus-session-stats:start -->.*?<!-- focus-session-stats:end -->\n*",
            re.DOTALL,
        )
        cleaned = old_stats_pattern.sub("\n", text).rstrip()
        old_yaml_pattern = re.compile(
            r"\n*---\n"
            r"id:\s+\d{8}T\d{12}\n"
            r"start:\s+.+\n"
            r"preset:\s+.+\n"
            r"tag:\s+.*\n"
            r"interruptions:\s+\d+\n"
            r"---\n*$",
            re.DOTALL,
        )
        cleaned = old_yaml_pattern.sub("\n", cleaned).rstrip()
        old_callout_pattern = re.compile(
            r"\n*<!-- focus-session-footer:start -->.*?<!-- focus-session-footer:end -->\n*",
            re.DOTALL,
        )
        cleaned = old_callout_pattern.sub("\n", cleaned).rstrip()
        return cleaned

    def _infer_work_item(self, state) -> str:
        title = state.title.strip()
        tag = state.tag.strip()
        if title and tag:
            return f"{title} ({tag})"
        if title:
            return title
        if tag:
            return tag
        heading = self._first_markdown_heading(self.editor.toPlainText())
        return heading or "Untitled focus work"

    def _first_markdown_heading(self, text: str) -> str | None:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip() or None
        return None

    def _status_text(self, state) -> str:
        status = state.status()
        if status == FocusStatus.PAUSED:
            return "🟠 ON BREAK"
        if status == FocusStatus.COMPLETED:
            return "🔴 COMPLETED"
        return "🟢 ACTIVE"

    def _session_block_pattern(self, session_id: str):
        return re.compile(
            r"\n*---\n\n### Focus Session \([^)]+\)\n\n"
            r".*?\n\*\*Session:\*\* preset `[^`]+` \| id `" + re.escape(session_id) + r"`\n\n-\n*",
            re.DOTALL,
        )

    def _replace_or_append_summary_block(
        self, *, text: str, replacement_block: str, session_date: str, work_item: str
    ) -> str:
        blocks = list(self._extract_summary_blocks(text))
        key = (session_date, work_item)
        if not blocks:
            return f"{text}\n\n{replacement_block}".strip()

        out_parts: list[str] = []
        cursor = 0
        replaced_once = False
        for start, end, date_value, work_value in blocks:
            out_parts.append(text[cursor:start])
            block_key = (date_value, work_value)
            if block_key == key:
                if not replaced_once:
                    out_parts.append(replacement_block)
                    replaced_once = True
                # Drop duplicate same-key blocks.
            else:
                out_parts.append(text[start:end])
            cursor = end
        out_parts.append(text[cursor:])
        merged = "".join(out_parts).strip()
        if replaced_once:
            return merged
        return f"{merged}\n\n{replacement_block}".strip()

    def _extract_summary_blocks(self, text: str):
        pattern = re.compile(
            r"---\n\n### Focus Session \((?P<date>[^)]+)\)\n\n"
            r"\*\*Work item:\*\* (?P<work>[^\n]+?)  \n"
            r".*?(?=\n---\n\n### Focus Session \(|\Z)",
            re.DOTALL,
        )
        for m in pattern.finditer(text):
            yield (m.start(), m.end(), m.group("date").strip(), m.group("work").strip())

    def _color_level_for_remaining(self, remaining_seconds: int, total_seconds: int) -> str:
        if total_seconds <= 0:
            return "green"
        if total_seconds <= 300:
            red_threshold = max(12, int(total_seconds * 0.12))
            amber_threshold = max(red_threshold + 1, int(total_seconds * 0.28))
        else:
            red_threshold = min(90, max(60, int(total_seconds * 0.10)))
            amber_threshold = max(red_threshold + 1, int(total_seconds * 0.20))
        if remaining_seconds <= red_threshold:
            return "red"
        if remaining_seconds <= amber_threshold:
            return "amber"
        return "green"

    def _play_finish_sound(self) -> None:
        profile = self.timer_settings.get_sound_profile()
        if profile == "beep":
            QApplication.beep()
            return
        alarm_path = self._resolve_alarm_sound_path(profile)
        if alarm_path and self._play_qsoundeffect_alarm(alarm_path):
            return
        QApplication.beep()

    def _play_qsoundeffect_alarm(self, sound_path: Path) -> bool:
        if sound_path.suffix.lower() != ".wav":
            return self._play_media_alarm(sound_path)
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QSoundEffect  # type: ignore
        except Exception:
            return self._play_media_alarm(sound_path)
        try:
            key = str(sound_path)
            effect = self._alarm_sound_effects.get(key)
            if effect is None:
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(sound_path)))
                effect.setVolume(0.90)
                self._alarm_sound_effects[key] = effect
            effect.play()
            return True
        except Exception:
            return self._play_media_alarm(sound_path)

    def _play_media_alarm(self, sound_path: Path) -> bool:
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer  # type: ignore
        except Exception:
            return self._play_system_alarm(sound_path)
        try:
            if self._alarm_media_player is None or self._alarm_audio_output is None:
                audio = QAudioOutput(self)
                audio.setVolume(0.95)
                player = QMediaPlayer(self)
                player.setAudioOutput(audio)
                self._alarm_audio_output = audio
                self._alarm_media_player = player
            self._alarm_media_player.setSource(QUrl.fromLocalFile(str(sound_path)))
            self._alarm_media_player.play()
            return True
        except Exception:
            return self._play_system_alarm(sound_path)

    def _play_system_alarm(self, sound_path: Path) -> bool:
        if platform.system() == "Darwin":
            afplay = shutil.which("afplay")
            if afplay:
                try:
                    subprocess.Popen(
                        [afplay, str(sound_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                except Exception:
                    return False
        return False

    def _resolve_alarm_sound_path(self, profile: str) -> Path | None:
        if profile == "custom":
            custom = self.timer_settings.get_custom_sound_path()
            if custom is None or not custom.exists():
                return None
            return custom
        return self._ensure_alarm_sound_file(profile)

    def _ensure_alarm_sound_file(self, profile: str) -> Path:
        out = Path(tempfile.gettempdir()) / f"pymd_focus_alarm_{profile}.wav"
        if out.exists():
            return out
        sample_rate = 44_100
        amplitude = 16000
        tones = self._tone_pattern(profile)
        with wave.open(str(out), "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for freq, dur in tones:
                if freq <= 0:
                    silence_frames = int(sample_rate * dur)
                    wav_file.writeframesraw(b"\x00\x00" * silence_frames)
                    continue
                frames = int(sample_rate * dur)
                for i in range(frames):
                    angle = 2.0 * math.pi * freq * (i / sample_rate)
                    sample = int(amplitude * math.sin(angle))
                    wav_file.writeframesraw(struct.pack("<h", sample))
        self._alarm_sound_path = out
        return out

    def _tone_pattern(self, profile: str) -> list[tuple[float, float]]:
        if profile == "chime":
            return [(659.0, 0.15), (0.0, 0.05), (880.0, 0.20)]
        if profile == "bell":
            return [(523.0, 0.25), (392.0, 0.20)]
        if profile == "ping":
            return [(1046.0, 0.12)]
        return [(880.0, 0.20)]

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
