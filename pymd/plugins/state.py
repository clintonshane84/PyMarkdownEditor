from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from pymd.domain.interfaces import ISettingsService

SETTINGS_PLUGINS_ENABLED = "plugins/enabled_map"  # QSettings key


class IPluginStateStore(Protocol):
    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool: ...
    def set_enabled(self, plugin_id: str, enabled: bool) -> None: ...
    def all_states(self) -> dict[str, bool]: ...


@dataclass
class SettingsPluginStateStore(IPluginStateStore):
    """
    Persistent plugin enabled-state store.

    Enhancements:
      - Supports optional default-enabled plugin ids (for built-ins).
      - Safe against corrupted JSON.
      - Deterministic fallback behavior.
    """

    settings: ISettingsService
    default_enabled: set[str] = field(default_factory=set)

    # -----------------------------
    # Internal helpers
    # -----------------------------

    def _read_map(self) -> dict[str, bool]:
        raw = self.settings.get_raw(SETTINGS_PLUGINS_ENABLED, "{}")

        if not isinstance(raw, str):
            return {}

        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                return {}

            # Normalize keys + bool values
            return {str(k): bool(v) for k, v in data.items()}
        except Exception:
            # Corrupt JSON → fail safely
            return {}

    def _write_map(self, m: dict[str, bool]) -> None:
        try:
            self.settings.set_raw(SETTINGS_PLUGINS_ENABLED, json.dumps(m))
        except Exception:
            # Never crash app due to settings write failure
            pass

    # -----------------------------
    # Public API
    # -----------------------------

    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool:
        """
        Resolution order:

          1. Explicit value in persisted map
          2. default_enabled set (for built-ins)
          3. Caller-provided default
        """
        m = self._read_map()

        if plugin_id in m:
            return bool(m[plugin_id])

        if plugin_id in self.default_enabled:
            return True

        return bool(default)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        m = self._read_map()
        m[str(plugin_id)] = bool(enabled)
        self._write_map(m)

    def all_states(self) -> dict[str, bool]:
        """
        Returns explicit persisted states only.
        Does NOT automatically include default-enabled plugins
        unless they were explicitly toggled.

        This keeps UI behavior clean and predictable.
        """
        return self._read_map()
