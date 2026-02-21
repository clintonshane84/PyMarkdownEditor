from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QLabel, QProgressBar

from pymd.services.ui.splash_screen import SplashScreen


def _find_child(widget, cls, name: str) -> object:
    v = getattr(widget, name)
    assert isinstance(v, cls)
    return v


def test_splash_set_status_updates_label(qapp):
    s = SplashScreen(app_title="Test")
    lbl = _find_child(s, QLabel, "_status")

    s.set_status("Loading…")
    assert lbl.text() == "Loading…"


def test_splash_progress_indeterminate_and_determinate(qapp):
    s = SplashScreen(app_title="Test")
    bar = _find_child(s, QProgressBar, "_bar")

    # Indeterminate when maximum is None -> Qt uses max=0 convention
    s.set_progress(maximum=None)
    assert bar.maximum() == 0

    # Determinate
    s.set_progress(maximum=10, value=3)
    assert bar.maximum() == 10
    assert bar.value() == 3

    # Determinate without value should not crash; value may remain whatever Qt keeps
    s.set_progress(maximum=5, value=None)
    assert bar.maximum() == 5


def test_splash_set_image_success_loads_pixmap(qapp, tmp_path: Path):
    # Write a valid tiny PNG using Qt itself (no external deps)
    img = QImage(2, 2, QImage.Format.Format_ARGB32)
    img.fill(0xFF00FF00)  # opaque green

    p = tmp_path / "splash.png"
    assert img.save(str(p), "PNG") is True
    assert p.exists()

    s = SplashScreen(image_path=None, app_title="Test")
    img_lbl = _find_child(s, QLabel, "_img")
    status_lbl = _find_child(s, QLabel, "_status")

    s.set_image(p)

    # If successful, QLabel has a pixmap and no error placeholder text
    assert img_lbl.pixmap() is not None
    assert (img_lbl.text() or "") == ""
    # status should remain whatever it was (not replaced with error)
    assert "Qt could not load" not in status_lbl.text()
    assert "Splash image not found" not in status_lbl.text()


def test_splash_set_image_fail_missing_file_sets_error_text(qapp, tmp_path: Path):
    missing = tmp_path / "nope.png"
    assert not missing.exists()

    s = SplashScreen(image_path=None, app_title="Test")
    img_lbl = _find_child(s, QLabel, "_img")
    status_lbl = _find_child(s, QLabel, "_status")

    s.set_image(missing)

    assert img_lbl.text() == "Splash image not found"
    assert status_lbl.text() == str(missing)

    px = img_lbl.pixmap()
    assert px is None or px.isNull()  # <- robust across Qt variants


def test_splash_set_image_fail_pixmap_is_null_sets_error_text(qapp, tmp_path: Path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a png")

    s = SplashScreen(image_path=None, app_title="Test")
    img_lbl = _find_child(s, QLabel, "_img")
    status_lbl = _find_child(s, QLabel, "_status")

    s.set_image(bad)

    assert img_lbl.text() == "Failed to load splash image"
    assert status_lbl.text() == f"Qt could not load: {bad.name}"

    px = img_lbl.pixmap()
    assert px is None or px.isNull()  # <- robust across Qt variants
