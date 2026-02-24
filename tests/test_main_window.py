# tests/test_main_window.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QEvent, QSettings, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QMessageBox, QTextBrowser, QTextEdit

from pymd.services.exporters.base import IExporter, IExporterRegistry
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService
from pymd.services.ui.main_window import MainWindow
from pymd.utils.constants import MAX_RECENTS


# ------------------------------
# Minimal config + dialog stubs
# ------------------------------
@dataclass(frozen=True)
class DummyConfig:
    """
    Keep this deliberately permissive: AboutDialog may access various config attributes.
    Unknown attributes return a sensible empty string.
    """

    app_name: str = "PyMarkdownEditor"
    version: str = "1.0.0"
    website: str = ""
    repo_url: str = ""
    author: str = ""
    copyright: str = ""

    def __getattr__(self, _: str) -> str:  # for any other attribute AboutDialog may touch
        return ""


class DummyAboutDialog:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._shown = False

    def show(self) -> None:
        self._shown = True

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None


# ------------------------------
# Force the preview widget to be QTextBrowser in tests (avoid WebEngine)
# ------------------------------
@pytest.fixture(autouse=True)
def force_textbrowser_preview(monkeypatch):
    def _factory(self: MainWindow):
        w = QTextBrowser(self)
        w.setOpenExternalLinks(True)
        return w

    monkeypatch.setattr(MainWindow, "_create_preview_widget", _factory, raising=True)


# ------------------------------
# Autouse patch: auto-accept discard dialogs
# ------------------------------
@pytest.fixture(autouse=True)
def auto_accept_discard(monkeypatch):
    monkeypatch.setattr(
        "pymd.services.ui.main_window.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )


# ------------------------------
# Export fakes
# ------------------------------
class DummyExporter(IExporter):
    file_ext = "txt"

    @property
    def name(self) -> str:
        return "txt"

    @property
    def label(self) -> str:
        return "Export TXT"

    def export(self, html: str, out_path: Path) -> None:
        out_path.write_text(html, encoding="utf-8")


class FakeExporterRegistry(IExporterRegistry):
    def __init__(self) -> None:
        self._map: dict[str, IExporter] = {}

    def register(self, e: IExporter) -> None:
        self._map[e.name] = e

    def unregister(self, name: str) -> None:
        self._map.pop(name, None)

    def get(self, name: str) -> IExporter:
        if name not in self._map:
            raise KeyError(name)
        return self._map[name]

    def all(self) -> list[IExporter]:
        return list(self._map.values())


@pytest.fixture()
def exporter_registry() -> IExporterRegistry:
    reg = FakeExporterRegistry()
    reg.register(DummyExporter())
    return reg


@pytest.fixture()
def window(qapp, tmp_path: Path, exporter_registry: IExporterRegistry, monkeypatch) -> MainWindow:
    """
    Build a MainWindow with file-backed QSettings (isolated per test) and a stub AboutDialog,
    plus an injected exporter registry containing DummyExporter.
    """
    # Avoid coupling to AboutDialog internals/expected config attributes
    monkeypatch.setattr("pymd.services.ui.main_window.AboutDialog", DummyAboutDialog, raising=True)

    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    renderer = MarkdownRenderer()
    files = FileService()
    settings = SettingsService(qs)

    w = MainWindow(
        app_title="Test",
        config=DummyConfig(),
        renderer=renderer,
        file_service=files,
        settings=settings,
        exporter_registry=exporter_registry,
        start_path=None,
    )
    w.show()
    qapp.processEvents()
    return w


# ------------------------------
# Core window behavior tests
# ------------------------------
def test_window_initial_state(window: MainWindow):
    assert window.doc.path is None
    assert window.doc.modified is False
    assert isinstance(window.editor, QTextEdit)
    assert isinstance(window.preview, QTextBrowser)

    html = window.preview.toHtml().lower()
    assert "<html" in html


def test_window_open_save_cycle(tmp_path: Path, window: MainWindow):
    src = tmp_path / "a.md"
    src.write_text("# Hello", encoding="utf-8")

    window._open_path(src)
    assert window.doc.path == src
    assert window.editor.toPlainText().startswith("# Hello")

    window.editor.setPlainText("# Hello\nWorld")
    assert window.doc.modified is True

    dest = tmp_path / "b.md"
    assert window._write_to(dest) is True
    assert dest.read_text(encoding="utf-8").endswith("World")
    assert window.doc.modified is False


def test_window_write_failure_shows_error(monkeypatch, tmp_path: Path, window: MainWindow):
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    def boom(_self: Any, _path: Path, _text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(type(window.file_service), "write_text_atomic", boom, raising=False)
    assert window._write_to(tmp_path / "bad.md") is False


def test_export_action_flows_through_registry(monkeypatch, tmp_path: Path, window: MainWindow):
    window.editor.setPlainText("# Title\n\nText")

    assert window.export_actions
    act = window.export_actions[0]

    out = tmp_path / "doc.txt"
    monkeypatch.setattr(
        "pymd.services.ui.main_window.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(out), ""),
    )

    act.trigger()

    data = out.read_text(encoding="utf-8").lower()
    assert "<html" in data


def test_recents_persist_roundtrip(window: MainWindow, tmp_path: Path, qapp):
    p = tmp_path / "r.md"
    p.write_text("ok", encoding="utf-8")
    window._open_path(p)
    assert window.recents[:1] == [str(p)]

    window.close()
    qapp.processEvents()

    w2 = MainWindow(
        app_title="Test2",
        config=DummyConfig(),
        renderer=MarkdownRenderer(),
        file_service=FileService(),
        settings=window.settings,  # same SettingsService backend
        exporter_registry=window._exporters,
        start_path=None,
    )
    assert w2.recents[:1] == [str(p)]


def test_confirm_discard_negative(window: MainWindow, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window.doc.modified = True
    assert window._confirm_discard() is False


def test_confirm_discard_positive(window: MainWindow, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.doc.modified = True
    assert window._confirm_discard() is True


def test_confirm_discard_no_dialog_when_unmodified(window: MainWindow, monkeypatch):
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", spy)
    window.doc.modified = False
    assert window._confirm_discard() is True
    assert called["n"] == 0


def test_window_toggles(window: MainWindow, qapp):
    window._toggle_wrap(False)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap
    window._toggle_wrap(True)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth

    window._toggle_preview(False)
    qapp.processEvents()
    assert window.preview.isVisible() is False
    window._toggle_preview(True)
    qapp.processEvents()
    assert window.preview.isVisible() is True


# ------------------------------
# Formatting & header toggles
# ------------------------------
def _select_range(w: MainWindow, start: int, end: int) -> None:
    c = w.editor.textCursor()
    c.setPosition(start)
    c.setPosition(end, c.MoveMode.KeepAnchor)
    w.editor.setTextCursor(c)


def test_bold_toggle_wraps_and_unwraps(window: MainWindow):
    window.editor.setPlainText("hello")
    _select_range(window, 0, 5)
    window.act_bold.trigger()
    assert window.editor.toPlainText() == "**hello**"

    # toggle off by selecting wrapped value
    window.editor.setPlainText("**hello**")
    _select_range(window, 0, len("**hello**"))
    window.act_bold.trigger()
    assert window.editor.toPlainText() == "hello"


def test_italic_toggle_handles_whitespace(window: MainWindow):
    window.editor.setPlainText(" hello ")
    _select_range(window, 0, len(" hello "))
    window.act_italic.trigger()
    assert window.editor.toPlainText() == "_ hello _"  # preserves original spacing

    # toggle off even if selection includes whitespace by stripping logic
    window.editor.setPlainText(" _hello_ ")
    _select_range(window, 0, len(" _hello_ "))
    window.act_italic.trigger()
    assert window.editor.toPlainText() == "hello"


def test_header_prefix_toggle(window: MainWindow):
    window.editor.setPlainText("line1\nline2")
    _select_range(window, 0, 0)  # caret on line1
    window.act_h1.trigger()
    assert window.editor.toPlainText().startswith("# line1")

    # toggle back to none
    window.act_h1.trigger()
    assert window.editor.toPlainText().startswith("line1")


def test_prefix_line_multiline_selection(window: MainWindow):
    window.editor.setPlainText("a\nb\nc")
    _select_range(window, 0, len("a\nb\nc"))
    window.act_list.trigger()
    assert window.editor.toPlainText().splitlines() == ["- a", "- b", "- c"]


def test_prefix_line_partial_multiline_selection(window: MainWindow):
    window.editor.setPlainText("a\nb\nc\n")
    # select only 'b' line (positions: 0 a,1 \n,2 b,3 \n,4 c,5 \n)
    _select_range(window, 2, 4)
    window.act_list.trigger()
    assert window.editor.toPlainText().splitlines()[:3] == ["a", "- b", "c"]


# ------------------------------
# Smart paste: URL -> Markdown link
# ------------------------------
def test_paste_as_markdown_link_with_selection(monkeypatch, window: MainWindow, qapp):
    cb = qapp.clipboard()
    cb.setText("https://example.com")

    window.editor.setPlainText("Click here")
    _select_range(window, 0, len("Click here"))

    handled = window._paste_as_markdown_link_if_applicable()
    assert handled is True
    assert window.editor.toPlainText() == "[Click here](https://example.com)"


def test_paste_as_markdown_link_no_selection_places_cursor_inside_brackets(monkeypatch, window: MainWindow, qapp):
    cb = qapp.clipboard()
    cb.setText("www.example.com")

    window.editor.setPlainText("")
    c = window.editor.textCursor()
    c.setPosition(0)
    window.editor.setTextCursor(c)

    handled = window._paste_as_markdown_link_if_applicable()
    assert handled is True
    assert window.editor.toPlainText() == "[](https://www.example.com)"
    # Cursor should be between [ and ]
    cur = window.editor.textCursor()
    assert cur.position() == 1


def test_paste_as_markdown_link_ignores_non_url(window: MainWindow, qapp):
    qapp.clipboard().setText("not a url")
    window.editor.setPlainText("")
    assert window._paste_as_markdown_link_if_applicable() is False


def test_event_filter_ctrl_v_handles_url(monkeypatch, window: MainWindow, qapp):
    qapp.clipboard().setText("https://example.com")
    window.editor.setPlainText("")
    window.editor.setFocus()

    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    handled = window.eventFilter(window.editor, ev)
    assert handled is True
    assert window.editor.toPlainText() == "[](https://example.com)"


def test_event_filter_ctrl_b_ctrl_i_require_selection(window: MainWindow):
    window.editor.setPlainText("hi")
    window.editor.setFocus()

    # no selection -> should do nothing but event is handled (it intercepts)
    ev_b = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    handled_b = window.eventFilter(window.editor, ev_b)
    assert handled_b is True
    assert window.editor.toPlainText() == "hi"

    ev_i = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
    handled_i = window.eventFilter(window.editor, ev_i)
    assert handled_i is True
    assert window.editor.toPlainText() == "hi"


def test_event_filter_ctrl_e_inserts_simple_code_block(window: MainWindow):
    window.editor.setPlainText("start")
    c = window.editor.textCursor()
    c.movePosition(c.MoveOperation.End)
    window.editor.setTextCursor(c)

    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
    handled = window.eventFilter(window.editor, ev)
    assert handled is True

    text = window.editor.toPlainText()
    assert "```\n\n```\n" in text


# ------------------------------
# Plugins: attach + menu behaviour
# ------------------------------
class FakePluginManager:
    def __init__(self) -> None:
        self.api: Any | None = None
        self.reload_calls = 0

    def set_api(self, api: Any) -> None:
        self.api = api

    def reload(self) -> None:
        self.reload_calls += 1

    # Provide one action via iter_enabled_actions
    class _Spec:
        title = "Do Thing"
        shortcut = "Ctrl+Alt+D"
        status_tip = "Run plugin thing"

    def iter_enabled_actions(self, _api: Any):
        def handler(api: Any) -> None:
            api.insert_text_at_cursor("PLUGIN!")

        return [(self._Spec(), handler)]


class FakePluginInstaller:
    pass


def test_attach_plugins_sets_api_and_does_not_reload(window: MainWindow):
    pm = FakePluginManager()
    pi = FakePluginInstaller()

    window.attach_plugins(plugin_manager=pm, plugin_installer=pi)

    assert pm.api is not None  # API injected
    assert pm.reload_calls == 0  # attach_plugins must not call reload()


def test_rebuild_plugin_actions_adds_actions_to_tools_menu(window: MainWindow):
    pm = FakePluginManager()
    window.attach_plugins(plugin_manager=pm, plugin_installer=FakePluginInstaller())

    # Trigger the newly added plugin action
    # The Tools menu already contains Plugins… and a separator; plugin action appended after.
    tools_menu = window._plugins_menu
    assert tools_menu is not None

    # Find our QAction by text
    actions = [a for a in tools_menu.actions() if a.text() == "Do Thing"]
    assert actions, "Expected plugin action not found"
    act = actions[0]

    # Put cursor at end and trigger
    window.editor.setPlainText("X")
    c = window.editor.textCursor()
    c.movePosition(c.MoveOperation.End)
    window.editor.setTextCursor(c)

    act.trigger()
    assert window.editor.toPlainText() == "XPLUGIN!"


def test_show_plugins_manager_unavailable_shows_info(monkeypatch, window: MainWindow):
    called = {"n": 0}
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    window.attach_plugins(plugin_manager=None, plugin_installer=None)
    window._show_plugins_manager()

    assert called["n"] == 1


# ------------------------------
# Themes: apply + persistence
# ------------------------------
def test_apply_theme_sets_setting(window: MainWindow):
    window.apply_theme("midnight")
    assert window.settings.get_raw("ui/theme", "default") == "midnight"

    window.apply_theme("paper")
    assert window.settings.get_raw("ui/theme", "default") == "paper"

    window.apply_theme("default")
    assert window.settings.get_raw("ui/theme", "default") == "default"


# ------------------------------
# Recents: dedup + cap
# ------------------------------
def test_recents_dedup_and_order(window: MainWindow, tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")

    window._open_path(a)
    window._open_path(b)
    window._open_path(a)  # bring to front again

    assert window.recents[:2] == [str(a), str(b)]


def test_recents_max_enforced(window: MainWindow, tmp_path: Path):
    opened: list[str] = []
    for i in range(0, 2 * MAX_RECENTS):
        p = tmp_path / f"f{i}.md"
        p.write_text("x", encoding="utf-8")
        window._open_path(p)
        opened.append(str(p))

    assert len(window.recents) == MAX_RECENTS
    assert window.recents[0] == opened[-1]
