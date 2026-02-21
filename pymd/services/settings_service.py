from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import QByteArray, QSettings

from pymd.domain.interfaces import ISettingsService
from pymd.utils.constants import SETTINGS_GEOMETRY, SETTINGS_RECENTS, SETTINGS_SPLITTER


class SettingsService(ISettingsService):
    """Persist small UI bits like geometry, splitter position, and recent files."""

    def __init__(self, qsettings: QSettings) -> None:
        self._s = qsettings

    def get_geometry(self) -> bytes | None:
        v = self._s.value(SETTINGS_GEOMETRY)
        return bytes(v) if isinstance(v, QByteArray) else None

    def set_geometry(self, blob: bytes) -> None:
        self._s.setValue(SETTINGS_GEOMETRY, QByteArray(blob))

    def get_splitter(self) -> bytes | None:
        v = self._s.value(SETTINGS_SPLITTER)
        return bytes(v) if isinstance(v, QByteArray) else None

    def set_splitter(self, blob: bytes) -> None:
        self._s.setValue(SETTINGS_SPLITTER, QByteArray(blob))

    def get_recent(self) -> list[str]:
        v = self._s.value(SETTINGS_RECENTS, [])
        return [str(x) for x in v] if isinstance(v, list) else []

    def get_raw(self, key: str, default=None):
        return self._s.value(key, default)

    def set_raw(self, key: str, value) -> None:
        self._s.setValue(key, value)

    def set_recent(self, recent: Iterable[str]) -> None:
        self._s.setValue(SETTINGS_RECENTS, list(recent))
