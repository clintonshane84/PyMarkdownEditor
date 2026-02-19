from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from pymd.plugins.api import ActionSpec, IAppAPI, IPlugin
from pymd.plugins.discovery import discover_plugin_factories
from pymd.plugins.state import IPluginStateStore


@dataclass(frozen=True)
class PluginInfo:
    plugin_id: str
    name: str
    version: str
    description: str


class PluginManager:
    def __init__(self, *, api: IAppAPI, state: IPluginStateStore) -> None:
        self._api = api
        self._state = state
        self._plugins: dict[str, IPlugin] = {}

    def discover(self) -> None:
        self._plugins.clear()
        for factory in discover_plugin_factories():
            try:
                plugin = factory() if callable(factory) else factory
                meta = plugin.meta
                self._plugins[meta.id] = plugin
            except Exception:
                continue

    def list_plugins(self) -> list[PluginInfo]:
        out: list[PluginInfo] = []
        for p in self._plugins.values():
            try:
                m = p.meta
                out.append(PluginInfo(m.id, m.name, m.version, m.description))
            except Exception:
                continue
        return out

    def iter_actions(self) -> Sequence[tuple[ActionSpec, Callable[[], None]]]:
        """
        Returns ActionSpec + zero-arg callable already bound to AppAPI.
        Only returns actions for enabled plugins.
        """
        actions: list[tuple[ActionSpec, Callable[[], None]]] = []
        for pid, p in self._plugins.items():
            if not self._state.get_enabled(pid, default=False):
                continue
            try:
                for spec, handler in p.register_actions():
                    actions.append((spec, lambda h=handler: h(self._api)))
            except Exception:
                continue
        return actions