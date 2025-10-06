from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService


# --- Fallback QApplication fixture (works with or without pytest-qt) ---
@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication for tests that need Qt.
    Creates one if not present; reuses existing otherwise.
    """
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication([])
        created = True
    try:
        yield app
    finally:
        # Don't forcibly quit a shared app; only close if we created it here.
        if created:
            app.quit()


# --- Other common fixtures ---


@pytest.fixture()
def tmp_settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.ini"


@pytest.fixture()
def qsettings(tmp_settings_path: Path) -> QSettings:
    # Use an INI file so we don't touch system registry / platform stores
    s = QSettings(str(tmp_settings_path), QSettings.Format.IniFormat)
    s.clear()
    return s


@pytest.fixture()
def settings_service(qsettings: QSettings) -> SettingsService:
    return SettingsService(qsettings)


@pytest.fixture()
def file_service() -> FileService:
    return FileService()


@pytest.fixture()
def renderer() -> MarkdownRenderer:
    return MarkdownRenderer()
