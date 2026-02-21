from __future__ import annotations

from collections.abc import Callable as AbcCallable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pymd.plugins.api import ActionSpec, IAppAPI, IPlugin
from pymd.plugins.catalog import PluginCatalogItem, default_catalog
from pymd.plugins.discovery import discover_plugins
from pymd.plugins.state import IPluginStateStore


class PluginRowLike(Protocol):
    """
    Minimal row shape required by the PluginsDialog.

    We keep this in the plugin layer to avoid importing UI types into core.
    """

    plugin_id: str
    name: str
    version: str
    description: str


@dataclass(frozen=True)
class PluginInfo:
    plugin_id: str
    name: str
    version: str
    description: str


class PluginManager:
    """
    Discovers plugins, tracks enabled state via IPluginStateStore, and exposes enabled actions.

    - `discover()` refreshes the available plugin set.
    - `reload()` discovers and (re)activates enabled plugins (best effort).
    - `iter_enabled_actions(api)` returns actions for enabled plugins only.

    The AppAPI may be injected later via `set_api()` which supports clean DI where
    the Qt window must exist before the API adapter can be constructed.
    """

    def __init__(
            self,
            *,
            state: IPluginStateStore,
            api: IAppAPI | None = None,
            catalog: Sequence[PluginCatalogItem] | None = None,
    ) -> None:
        self._api: IAppAPI | None = api
        self._state: IPluginStateStore = state
        self._plugins: dict[str, IPlugin] = {}
        self._active: dict[str, IPlugin] = {}
        self.catalog: list[PluginCatalogItem] = list(catalog or default_catalog())

    @property
    def state_store(self) -> IPluginStateStore:
        return self._state

    def set_api(self, api: IAppAPI) -> None:
        self._api = api

    # ----------------------------- discovery -----------------------------

    def discover(self) -> None:
        self._plugins.clear()

        for factory in discover_plugins():
            try:
                plugin = factory() if callable(factory) else factory
                meta = plugin.meta
                self._plugins[str(meta.id)] = plugin
            except Exception:
                # discovery is best-effort; a broken plugin shouldn't break the app
                continue

    def list_plugins(self) -> list[PluginInfo]:
        out: list[PluginInfo] = []
        for p in self._plugins.values():
            try:
                m = p.meta
                out.append(
                    PluginInfo(
                        plugin_id=str(m.id),
                        name=str(m.name),
                        version=str(m.version),
                        description=str(m.description),
                    )
                )
            except Exception:
                continue
        return out

    # ----------------------------- lifecycle -----------------------------

    def reload(self) -> None:
        """
        Re-discover plugins and activate all enabled ones.
        Deactivates plugins that were active but are no longer enabled.
        """
        self.discover()

        api = self._api
        if api is None:
            # Without an API, we can still discover/list, but can't activate.
            self._active.clear()
            return

        # Deactivate anything currently active that is now disabled or missing.
        for pid, plugin in list(self._active.items()):
            if pid not in self._plugins or not self._state.get_enabled(pid, default=False):
                try:
                    plugin.deactivate()
                except Exception:
                    pass
                self._active.pop(pid, None)

        # Activate enabled plugins (best-effort).
        for pid, plugin in self._plugins.items():
            if not self._state.get_enabled(pid, default=False):
                continue
            if pid in self._active:
                continue
            try:
                plugin.activate(api)
                self._active[pid] = plugin
            except Exception:
                continue

    # ----------------------------- UI helpers -----------------------------

    def get_installed_rows(self) -> Sequence[PluginRowLike]:
        """
        Returns row-like objects (plugin_id/name/version/description) for the PluginsDialog.

        We return PluginInfo (which matches those attribute names), but type it as PluginRowLike
        to keep the plugin layer decoupled from UI modules.
        """
        if not self._plugins:
            self.discover()
        return self.list_plugins()

    # ----------------------------- actions -----------------------------

    def iter_enabled_actions(
            self, api: IAppAPI
    ) -> Sequence[tuple[ActionSpec, AbcCallable[[IAppAPI], None]]]:
        """
        Returns (ActionSpec, handler) for enabled plugins only.
        The handler returned here expects an IAppAPI argument.
        """
        return self._iter_actions(api=api, enabled_only=True)

    def iter_actions(
            self, api: IAppAPI
    ) -> Sequence[tuple[ActionSpec, AbcCallable[[IAppAPI], None]]]:
        """
        Returns (ActionSpec, handler) for all discovered plugins (enabled or not).
        The handler returned here expects an IAppAPI argument.
        """
        return self._iter_actions(api=api, enabled_only=False)

    def _iter_actions(
            self,
            *,
            api: IAppAPI,
            enabled_only: bool,
    ) -> Sequence[tuple[ActionSpec, AbcCallable[[IAppAPI], None]]]:
        if not self._plugins:
            self.discover()

        actions: list[tuple[ActionSpec, AbcCallable[[IAppAPI], None]]] = []
        for pid, plugin in self._plugins.items():
            if enabled_only and not self._state.get_enabled(pid, default=False):
                continue
            try:
                for spec, handler in plugin.register_actions():
                    # Keep original plugin handler signature: handler(app_api)
                    def _run(app_api: IAppAPI, h=handler) -> None:
                        h(app_api)

                    actions.append((spec, _run))
            except Exception:
                continue
        return actions
