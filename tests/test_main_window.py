# tests/test_main_windows.py
from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox, QTextEdit

from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService
from pymd.ui.main_window import MainWindow


@pytest.fixture()
def window(qapp, tmp_path):
    """
    Provide a MainWindow wired with real services but isolated QSettings.

    Teardown closes the window and processes events to prevent Qt from
    holding the event loop open on CI.
    """
    qs = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    renderer = MarkdownRenderer()
    files = FileService()
    settings = SettingsService(qs)
    w = MainWindow(renderer, files, settings, start_path=None, app_title="Test")
    try:
        yield w
    finally:
        w.close()
        qapp.processEvents()


def test_window_initial_state(window: MainWindow):
    assert window.doc.path is None
    assert window.doc.modified is False

    # Preview should have some HTML; Qt normalizes output and may not include our <style>.
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

    # save as (use private helper to avoid file dialogs)
    dest = tmp_path / "b.md"
    assert window._write_to(dest) is True
    assert dest.read_text(encoding="utf-8").endswith("World")


def test_window_write_failure_shows_error(monkeypatch, tmp_path: Path, window: MainWindow):
    # Simulate write failure in FileService.write_text_atomic
    def boom(_self, path: Path, text: str):
        raise OSError("disk full")

    monkeypatch.setattr(type(window.file_service), "write_text_atomic", boom, raising=False)
    assert window._write_to(tmp_path / "bad.md") is False


def test_window_export_html_pdf(tmp_path: Path, window: MainWindow, qapp):
    # Export via registry directly to avoid file dialogs
    html_out = tmp_path / "x.html"
    pdf_out = tmp_path / "x.pdf"

    from pymd.services.exporters.base import ExporterRegistry

    exps = {e.name: e for e in ExporterRegistry.all()}
    assert "html" in exps and "pdf" in exps

    html = window.renderer.to_html("# T")
    exps["html"].export(html, html_out)
    assert html_out.exists() and html_out.read_text(encoding="utf-8").lower().startswith(
        "<!doctype"
    )

    assert QApplication.instance() is not None
    exps["pdf"].export(html, pdf_out)
    assert pdf_out.exists() and pdf_out.stat().st_size > 0


def test_window_recents_persist(window: MainWindow, tmp_path: Path):
    p = tmp_path / "r.md"
    p.write_text("ok", encoding="utf-8")
    window._open_path(p)
    # Should be most recent entry
    assert window.recents and str(p) == window.recents[0]


def test_window_confirm_discard_negative(window: MainWindow, monkeypatch):
    # Simulate user selecting "No" (do not discard)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    window.doc.modified = True
    assert window._confirm_discard() is False


def test_window_confirm_discard_positive(window: MainWindow, monkeypatch):
    # Simulate user selecting "Yes" (discard)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    window.doc.modified = True
    assert window._confirm_discard() is True


def test_window_toggles(window: MainWindow, qapp):
    # Wrap toggle
    window._toggle_wrap(False)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.NoWrap
    window._toggle_wrap(True)
    assert window.editor.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth

    # Make sure visibility reflects actual state: show the top-level window
    window.show()
    qapp.processEvents()

    # Preview toggle
    window._toggle_preview(False)
    qapp.processEvents()
    assert window.preview.isVisible() is False

    window._toggle_preview(True)
    qapp.processEvents()
    assert window.preview.isVisible() is True
