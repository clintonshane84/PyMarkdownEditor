from __future__ import annotations

import typing as t
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QMessageBox, QTextEdit

from pymd.domain.interfaces import IExporter, IExporterRegistry
from pymd.services.exporters.base import ExporterRegistryInst
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService
from pymd.services.ui.main_window import MainWindow

# ------------------------------
# Helpers / fakes for the tests
# ------------------------------


class DummyExporter(IExporter):
    """Tiny exporter used for tests; writes the HTML to a .txt file."""

    @property
    def name(self) -> str:  # e.g., extension key
        return "txt"

    @property
    def label(self) -> str:
        return "Export TXT"

    def export(self, html: str, out_path: Path) -> None:
        out_path.write_text(html, encoding="utf-8")


@pytest.fixture()
def exporter_registry() -> IExporterRegistry:
    reg = ExporterRegistryInst()
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
    return w


# ------------------------------
# Tests
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


def test_window_export_via_registry(
    tmp_path: Path, window: MainWindow, exporter_registry: IExporterRegistry
):
    # Put some content in the editor and render once
    window.editor.setPlainText("# Title\n\nText")
    window._render_preview()

    # Get the dummy exporter from the injected registry
    exp = t.cast(DummyExporter, exporter_registry.get("txt"))
    out = tmp_path / "x.txt"
    exp.export(window.renderer.to_html(window.editor.toPlainText()), out)
    data = out.read_text(encoding="utf-8").lower()
    assert data.startswith("<!doctype") or "<html" in data


def test_window_recents_persist(window: MainWindow, tmp_path: Path):
    p = tmp_path / "r.md"
    p.write_text("ok", encoding="utf-8")
    window._open_path(p)
    assert str(p) in window.recents[:1]  # most recent


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


def test_window_toggles(window: MainWindow, qapp):
    # Wrap toggle
    window._toggle_wrap(False)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap
    window._toggle_wrap(True)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth

    # Preview toggle
    window._toggle_preview(False)
    assert window.preview.isVisible() is False
    window._toggle_preview(True)
    # Make sure widget hierarchy is actually shown so visibility reflects correctly
    window.show()
    qapp.processEvents()
    assert window.preview.isVisible() is True
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

    # Multi-line prefix with "- "
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
