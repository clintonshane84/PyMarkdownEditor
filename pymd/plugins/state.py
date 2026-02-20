from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pymd.domain.interfaces import ISettingsService

SETTINGS_PLUGINS_ENABLED = "plugins/enabled_map"  # QSettings key


class IPluginStateStore(Protocol):
    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool: ...
    def set_enabled(self, plugin_id: str, enabled: bool) -> None: ...
    def all_states(self) -> dict[str, bool]: ...


@dataclass
class SettingsPluginStateStore(IPluginStateStore):
    settings: ISettingsService

    def _read_map(self) -> dict[str, bool]:
        raw = self.settings.get_raw(SETTINGS_PLUGINS_ENABLED, "{}")
        try:
            if isinstance(raw, str):
                return {str(k): bool(v) for k, v in json.loads(raw).items()}
            return {}
        except Exception:
            return {}

    def _write_map(self, m: dict[str, bool]) -> None:
        self.settings.set_raw(SETTINGS_PLUGINS_ENABLED, json.dumps(m))

    def get_enabled(self, plugin_id: str, *, default: bool = False) -> bool:
        m = self._read_map()
        return bool(m.get(plugin_id, default))

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        m = self._read_map()
        m[plugin_id] = bool(enabled)
        self._write_map(m)

    def all_states(self) -> dict[str, bool]:
        return self._read_map()
