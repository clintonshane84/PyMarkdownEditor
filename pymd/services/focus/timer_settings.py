from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QSettings


class TimerSettings:
    """Persistence wrapper for timer/session preferences."""

    KEY_AUTOSAVE_MIN = "timer/autosave_interval_min"
    KEY_SOUND_ENABLED = "timer/sound_enabled"
    KEY_DEFAULT_FOLDER = "timer/default_folder"
    KEY_WINDOW_POS = "timer/window_pos"

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

    def get_sound_enabled(self) -> bool:
        value = self._s.value(self.KEY_SOUND_ENABLED, False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def set_sound_enabled(self, enabled: bool) -> None:
        self._s.setValue(self.KEY_SOUND_ENABLED, bool(enabled))

    def get_default_folder(self) -> Path | None:
        value = self._s.value(self.KEY_DEFAULT_FOLDER, "")
        if not isinstance(value, str) or not value.strip():
            return None
        p = Path(value).expanduser()
        return p

    def set_default_folder(self, folder: Path | None) -> None:
        self._s.setValue(self.KEY_DEFAULT_FOLDER, str(folder) if folder else "")

    def get_timer_window_pos(self) -> QPoint | None:
        value = self._s.value(self.KEY_WINDOW_POS)
        return value if isinstance(value, QPoint) else None

    def set_timer_window_pos(self, pos: QPoint) -> None:
        self._s.setValue(self.KEY_WINDOW_POS, pos)
