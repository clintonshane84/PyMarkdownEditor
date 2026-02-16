from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PyQt6.QtCore import QPoint, QSettings


class TimerSettings:
    """Persistence wrapper for timer/session preferences."""

    KEY_AUTOSAVE_MIN = "timer/autosave_interval_min"
    KEY_SOUND_ENABLED = "timer/sound_enabled"
    KEY_SOUND_PROFILE = "timer/sound_profile"
    KEY_CUSTOM_SOUND_PATH = "timer/custom_sound_path"
    KEY_DEFAULT_FOLDER = "timer/default_folder"
    KEY_WINDOW_POS = "timer/window_pos"
    SOUND_PROFILES: ClassVar[set[str]] = {"beep", "chime", "bell", "ping", "custom"}

    def __init__(self, qsettings: QSettings) -> None:
        self._s = qsettings

    def get_autosave_interval_min(self) -> int:
        value = self._s.value(self.KEY_AUTOSAVE_MIN, 2)
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return 2

    def set_autosave_interval_min(self, minutes: int) -> None:
        self._s.setValue(self.KEY_AUTOSAVE_MIN, max(1, int(minutes)))
        self._s.sync()

    def get_sound_enabled(self) -> bool:
        value = self._s.value(self.KEY_SOUND_ENABLED, False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def set_sound_enabled(self, enabled: bool) -> None:
        self._s.setValue(self.KEY_SOUND_ENABLED, bool(enabled))
        self._s.sync()

    def get_sound_profile(self) -> str:
        value = self._s.value(self.KEY_SOUND_PROFILE, "beep")
        profile = str(value).strip().lower()
        return profile if profile in self.SOUND_PROFILES else "beep"

    def set_sound_profile(self, profile: str) -> None:
        value = profile.strip().lower()
        self._s.setValue(self.KEY_SOUND_PROFILE, value if value in self.SOUND_PROFILES else "beep")
        self._s.sync()

    def get_custom_sound_path(self) -> Path | None:
        value = self._s.value(self.KEY_CUSTOM_SOUND_PATH, "")
        if not isinstance(value, str) or not value.strip():
            return None
        return Path(value).expanduser()

    def set_custom_sound_path(self, path: Path | None) -> None:
        self._s.setValue(self.KEY_CUSTOM_SOUND_PATH, str(path) if path else "")
        self._s.sync()

    def get_default_folder(self) -> Path | None:
        value = self._s.value(self.KEY_DEFAULT_FOLDER, "")
        if not isinstance(value, str) or not value.strip():
            return None
        p = Path(value).expanduser()
        return p

    def set_default_folder(self, folder: Path | None) -> None:
        self._s.setValue(self.KEY_DEFAULT_FOLDER, str(folder) if folder else "")
        self._s.sync()

    def get_timer_window_pos(self) -> QPoint | None:
        value = self._s.value(self.KEY_WINDOW_POS)
        return value if isinstance(value, QPoint) else None

    def set_timer_window_pos(self, pos: QPoint) -> None:
        self._s.setValue(self.KEY_WINDOW_POS, pos)
        self._s.sync()
