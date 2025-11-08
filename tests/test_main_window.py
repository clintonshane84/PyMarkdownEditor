from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QMessageBox, QTextEdit

from pymd.domain.interfaces import IExporter, IExporterRegistry
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService
from pymd.services.ui.main_window import MainWindow

# ------------------------------
# Fakes & helpers
# ------------------------------


class DummyExporter(IExporter):
    """Tiny exporter used for tests; writes the HTML to a .txt file."""

    @property
    def name(self) -> str:
        return "txt"

    @property
    def label(self) -> str:
        return "Export TXT"

    def export(self, html: str, out_path: Path) -> None:
        out_path.write_text(html, encoding="utf-8")


class FakeExporterRegistry(IExporterRegistry):
    """Pure in-memory registry to avoid any global/singleton bleed across tests."""

    def __init__(self) -> None:
        self._map: dict[str, IExporter] = {}

    def register(self, e: IExporter) -> None:
        self._map[e.name] = e

    def unregister(self, name: str) -> None:
        self._map.pop(name, None)

    def get(self, name: str) -> IExporter:
        try:
            return self._map[name]
        except KeyError:
            raise KeyError(name)  # noqa: B904

    def all(self) -> list[IExporter]:
        return list(self._map.values())


@pytest.fixture()
def exporter_registry() -> IExporterRegistry:
    reg = FakeExporterRegistry()
    reg.register(DummyExporter())
    return reg


@pytest.fixture()
def window(qapp, tmp_path, exporter_registry: IExporterRegistry) -> MainWindow:
    """
    Build a MainWindow with file-based QSettings (isolated per test) and an injected
    exporter registry that contains a simple DummyExporter.
    """
    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    renderer = MarkdownRenderer()
    files = FileService()
    settings = SettingsService(qs)
    w = MainWindow(
        renderer=renderer,
        file_service=files,
        settings=settings,
        exporter_registry=exporter_registry,
        start_path=None,
        app_title="Test",
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

    # Preview should render empty doc to valid HTML
    html = window.preview.toHtml()
    assert "<html" in html.lower()


def test_window_open_save_cycle(tmp_path: Path, window: MainWindow):
    src = tmp_path / "a.md"
    src.write_text("# Hello", encoding="utf-8")

    window._open_path(src)
    assert window.doc.path == src
    assert window.editor.toPlainText().startswith("# Hello")

    # edit -> modified
    window.editor.setPlainText("# Hello\nWorld")
    assert window.doc.modified is True

    # save as
    dest = tmp_path / "b.md"
    assert window._write_to(dest) is True
    assert dest.read_text(encoding="utf-8").endswith("World")
    assert window.doc.modified is False


def test_window_write_failure_shows_error(monkeypatch, tmp_path: Path, window: MainWindow):
    # Neutralize blocking dialog
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    # Simulate write failure in FileService
    def boom(path: Path, text: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(type(window.file_service), "write_text_atomic", boom, raising=False)
    assert window._write_to(tmp_path / "bad.md") is False


def test_window_export_action_flows_through_registry(
    monkeypatch, tmp_path: Path, window: MainWindow
):
    # Put some content and render once
    window.editor.setPlainText("# Title\n\nText")

    # Pick the first export action created from the registry (our DummyExporter only)
    assert window.export_actions, "No export actions were created"
    act = window.export_actions[0]

    out = tmp_path / "doc.txt"
    # Drive the QFileDialog used by _export_with
    monkeypatch.setattr(
        "pymd.services.ui.main_window.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(out), ""),
    )

    # Trigger export via the UI action
    act.trigger()

    data = out.read_text(encoding="utf-8").lower()
    assert data.startswith("<!doctype") or "<html" in data


def test_window_recents_persist_roundtrip(window: MainWindow, tmp_path: Path, qapp):
    p = tmp_path / "r.md"
    p.write_text("ok", encoding="utf-8")
    window._open_path(p)
    assert str(p) in window.recents[:1]  # most recent

    # Close to persist geometry/splitter/recents into QSettings
    window.close()
    qapp.processEvents()

    # New window, reuse same SettingsService (same QSettings backend file)
    w2 = MainWindow(
        renderer=MarkdownRenderer(),
        file_service=FileService(),
        settings=window.settings,  # same SettingsService (file-backed)
        exporter_registry=window._exporters,
        app_title="Test2",
    )
    assert str(p) in w2.recents[:1]


def test_window_confirm_discard_negative(window: MainWindow, monkeypatch):
    # user says "No"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window.doc.modified = True
    assert window._confirm_discard() is False


def test_window_confirm_discard_positive(window: MainWindow, monkeypatch):
    # user says "Yes"
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
    # Wrap toggle
    window._toggle_wrap(False)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap
    window._toggle_wrap(True)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth

    # Preview toggle
    window._toggle_preview(False)
    qapp.processEvents()
    assert window.preview.isVisible() is False
    window._toggle_preview(True)
    qapp.processEvents()
    assert window.preview.isVisible() is True


def test_formatting_actions_surround_and_prefix(window: MainWindow):
    # Surround selection with bold
    window.editor.setPlainText("hello")
    c = window.editor.textCursor()
    c.setPosition(0)
    c.setPosition(5, c.MoveMode.KeepAnchor)
    window.editor.setTextCursor(c)
    window.act_bold.trigger()
    assert window.editor.toPlainText() == "**hello**"

    # Prefix line with "# "
    window.editor.setPlainText("line1\nline2")
    c = window.editor.textCursor()
    c.setPosition(0)
    window.editor.setTextCursor(c)
    window.act_h1.trigger()
    assert window.editor.toPlainText().startswith("# line1")

    # Multi-line prefix with "- " (full selection)
    window.editor.setPlainText("a\nb\nc")
    c = window.editor.textCursor()
    c.setPosition(0)
    c.movePosition(c.MoveOperation.End, c.MoveMode.KeepAnchor)
    window.editor.setTextCursor(c)
    window.act_list.trigger()
    text = window.editor.toPlainText().splitlines()
    assert text[0].startswith("- ")
    assert text[1].startswith("- ")
    assert text[2].startswith("- ")


def test_prefix_line_partial_multiline_selection(window: MainWindow):
    # Ensure only full selected lines are prefixed, no off-by-one past end.
    window.editor.setPlainText("a\nb\nc\n")
    c = window.editor.textCursor()
    # Select from start of 'b' line through newline after 'b' (not into 'c')
    # Positions: "a\nb\nc\n" -> 0 a,1 \n,2 b,3 \n,4 c,5 \n
    c.setPosition(2)  # start of 'b'
    c.setPosition(4, c.MoveMode.KeepAnchor)  # up to '\n' after 'b'
    window.editor.setTextCursor(c)
    window.act_list.trigger()
    assert window.editor.toPlainText().splitlines()[:3] == ["a", "- b", "c"]


# ------------------------------
# Find / Replace coverage
# ------------------------------


@pytest.mark.parametrize(
    "case,whole,needle,expected",
    [
        (False, False, "foo", ["foo", "foo", "FOO"]),  # substring & case-insensitive
        (False, True, "foo", ["foo", "FOO"]),  # whole words only; "foobar" excluded
        (True, True, "FOO", ["FOO"]),  # case + whole word
    ],
)
def test_find_options_whole_and_case(window: MainWindow, qapp, case, whole, needle, expected):
    window.editor.setPlainText("foo foobar FOO")
    dlg = window.find_dialog
    dlg.find_edit.setText(needle)
    dlg.case_cb.setChecked(case)
    dlg.word_cb.setChecked(whole)
    dlg.wrap_cb.setChecked(True)

    # Gather forward hits until cursor selection wraps or no selection
    hits: list[str] = []
    seen_starts: set[int] = set()

    # perform first find
    dlg.find(forward=True)
    qapp.processEvents()

    while window.editor.textCursor().hasSelection():
        cur = window.editor.textCursor()
        start = cur.selectionStart()
        if start in seen_starts:
            break  # wrapped/cycled
        seen_starts.add(start)
        hits.append(cur.selectedText())
        dlg.find(forward=True)
        qapp.processEvents()

    assert hits == expected


def test_find_backward_wraps(window: MainWindow, qapp):
    window.editor.setPlainText("a foo b foo c")
    dlg = window.find_dialog
    dlg.find_edit.setText("foo")
    dlg.case_cb.setChecked(False)
    dlg.word_cb.setChecked(True)
    dlg.wrap_cb.setChecked(True)

    # Move caret to start then search backward (forces wrap to last)
    c = window.editor.textCursor()
    c.movePosition(c.MoveOperation.Start)
    window.editor.setTextCursor(c)

    dlg.find(forward=False)
    qapp.processEvents()
    sel = window.editor.textCursor().selectedText()
    assert sel == "foo"
    # and ensure it's the *second* occurrence (after wrap)
    assert window.editor.textCursor().selectionStart() > 5  # past "a foo "


def test_replace_one_and_all(window: MainWindow, qapp):
    # Replace-one behavior
    window.editor.setPlainText("alpha beta alpha")
    window.act_replace.trigger()
    qapp.processEvents()

    dlg = window.find_dialog
    dlg.find_edit.setText("alpha")
    dlg.replace_edit.setText("ALPHA")
    dlg.case_cb.setChecked(False)
    dlg.word_cb.setChecked(True)
    dlg.wrap_cb.setChecked(True)

    # Find first, then replace one
    dlg.find(forward=True)
    qapp.processEvents()
    dlg.replace_one()
    qapp.processEvents()
    assert window.editor.toPlainText().startswith("ALPHA beta")

    # Replace all remaining
    dlg.replace_all()
    qapp.processEvents()
    assert "ALPHA beta ALPHA" == window.editor.toPlainText()


# ------------------------------
# Image & Link actions
# ------------------------------


def test_insert_image_inserts_img_tag(monkeypatch, window: MainWindow, qapp, tmp_path: Path):
    fake_img = tmp_path / "pic.png"
    fake_img.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal header

    # Stub the file dialog to return our image path
    monkeypatch.setattr(
        "pymd.services.ui.main_window.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(fake_img), "PNG (*.png)"),
    )

    window.editor.setPlainText("start")
    c = window.editor.textCursor()
    c.movePosition(c.MoveOperation.End)
    window.editor.setTextCursor(c)

    window.act_img.trigger()
    qapp.processEvents()

    text = window.editor.toPlainText()
    assert '<img src="' in text
    assert str(fake_img) in text


def test_create_link_invokes_dialog(window: MainWindow, qapp, monkeypatch):
    called = {"ok": False}

    def fake_show():
        called["ok"] = True

    monkeypatch.setattr(window.link_dialog, "show_create_link", fake_show)
    window.act_link.trigger()
    qapp.processEvents()
    assert called["ok"] is True
