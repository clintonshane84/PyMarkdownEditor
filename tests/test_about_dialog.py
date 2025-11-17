from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton

from pymd.services.ui.about import AboutDialog


class FakeCursor:
    def insertText(self, *_a, **_k):
        pass


class FakeEditor:
    def textCursor(self):
        return FakeCursor()

    def setTextCursor(self, _c):
        pass

    def document(self):
        return object()


@pytest.fixture
def editor():
    return FakeEditor()


@pytest.fixture
def dlg(qtbot, editor):
    d = AboutDialog(editor, None)
    qtbot.addWidget(d)
    return d


def test_constructs_and_is_non_modal(dlg: AboutDialog):
    assert dlg.windowTitle() == "About"
    assert dlg.isModal() is False


def test_has_expected_labels(dlg: AboutDialog):
    labels = dlg.findChildren(QLabel)
    texts = [l.text() for l in labels]
    assert any("PyMarkdown Editor" in t for t in texts)
    assert any("Version" in t for t in texts)


def test_has_ok_button_and_closes_on_click(qtbot, dlg: AboutDialog):
    ok: QPushButton | None = dlg.close_btn
    assert isinstance(ok, QPushButton)
    assert ok.text().lower() in ("ok", "close")

    dlg.show()
    assert dlg.isVisible() is True

    # Use a proper Qt mouse button enum
    qtbot.mouseClick(ok, Qt.MouseButton.LeftButton)
    # Wait until the dialog is no longer visible to avoid race conditions
    qtbot.waitUntil(lambda: not dlg.isVisible(), timeout=1000)


def test_no_link_creation_controls_present(dlg: AboutDialog):
    # Guard against accidental copy/paste of link dialog API
    for attr in ("create_link_btn", "url_edit", "link_title", "show_create_link", "create_link"):
        assert not hasattr(dlg, attr), f"AboutDialog unexpectedly has '{attr}'"
