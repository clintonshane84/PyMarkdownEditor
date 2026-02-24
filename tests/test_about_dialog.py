# tests/test_about_dialog.py
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton

from pymd.services.ui.about import AboutDialog


@dataclass(frozen=True)
class GoodConfig:
    def get_version(self) -> str:
        return "1.0.5"


class BadConfig:
    def get_version(self) -> str:
        raise RuntimeError("boom")


class LegacyConfig:
    """Fallback path: no get_version(), only app_version()."""

    def app_version(self) -> str:
        return "2.3.4"


# ------------------------------
# Construction & basic UI
# ------------------------------
def test_constructs_and_is_non_modal(qtbot):
    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)
    assert d.windowTitle() == "About"
    assert d.isModal() is False


def test_has_ok_button_and_closes_on_click(qtbot):
    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)

    ok: QPushButton | None = d.close_btn
    assert isinstance(ok, QPushButton)
    assert ok.text().lower() in ("ok", "close")

    d.show()
    assert d.isVisible() is True

    qtbot.mouseClick(ok, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not d.isVisible(), timeout=1000)


def test_no_link_creation_controls_present(qtbot):
    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)

    for attr in ("create_link_btn", "url_edit", "link_title", "show_create_link", "create_link"):
        assert not hasattr(d, attr), f"AboutDialog unexpectedly has '{attr}'"


# ------------------------------
# Version resolution: success + fail paths
# ------------------------------
def test_version_label_uses_get_version_success(qtbot):
    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)

    labels = d.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]

    assert any("PyMarkdown Editor" in t for t in texts)
    assert any("Version 1.0.5" in t for t in texts)


def test_version_label_falls_back_to_default_on_get_version_error(qtbot):
    d = AboutDialog(parent=None, config=BadConfig())
    qtbot.addWidget(d)

    labels = d.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]

    # Fail path: any exception -> "0.0.0"
    assert any("Version 0.0.0" in t for t in texts)


def test_version_label_legacy_fallback_app_version(qtbot):
    d = AboutDialog(parent=None, config=LegacyConfig())
    qtbot.addWidget(d)

    labels = d.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]

    assert any("Version 2.3.4" in t for t in texts)


def test_version_label_no_config_defaults_to_0_0_0(qtbot):
    d = AboutDialog(parent=None, config=None)
    qtbot.addWidget(d)

    labels = d.findChildren(QLabel)
    texts = [lbl.text() for lbl in labels]

    assert any("Version 0.0.0" in t for t in texts)


# ------------------------------
# Splash image: success + fail paths (via QPixmap.isNull patch)
# ------------------------------
def _find_splash_label(dlg: AboutDialog) -> QLabel:
    """
    The splash QLabel is the only QLabel that either:
      - has a pixmap set, OR
      - contains the '(splash.png missing)' text.
    """
    labels = dlg.findChildren(QLabel)
    for lbl in labels:
        if lbl.pixmap() is not None:
            return lbl
        if "(splash.png missing)" in (lbl.text() or ""):
            return lbl
    raise AssertionError("Could not locate splash label")


def test_splash_success_sets_pixmap(monkeypatch, qtbot):
    # Force the success path regardless of filesystem
    monkeypatch.setattr(QPixmap, "isNull", lambda self: False, raising=True)

    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)

    splash = _find_splash_label(d)
    assert splash.pixmap() is not None
    assert "(splash.png missing)" not in (splash.text() or "")


def test_splash_missing_sets_placeholder_text(monkeypatch, qtbot):
    # Force the fail path regardless of filesystem
    monkeypatch.setattr(QPixmap, "isNull", lambda self: True, raising=True)

    d = AboutDialog(parent=None, config=GoodConfig())
    qtbot.addWidget(d)

    splash = _find_splash_label(d)

    # QLabel.pixmap() may return an "empty" QPixmap object rather than None.
    pm = splash.pixmap()
    assert pm is None or pm.isNull()

    assert splash.text() == "(splash.png missing)"
