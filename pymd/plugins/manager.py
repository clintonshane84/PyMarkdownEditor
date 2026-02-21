from __future__ import annotations

from collections.abc import Callable as AbcCallable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pymd.plugins.api import ActionSpec, IAppAPI, IPlugin, IPluginOnLoad, IPluginOnReady
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
    Discovers plugins, tracks enabled state via IPluginStateStore, and exposes actions.

    Deterministic host wiring contract (recommended):
      - Pre-show (bootstrap):
          plugin_manager.set_api(app_api)
          plugin_manager.reload()
      - Post-show (next tick):
          plugin_manager.on_app_ready()

    Notes:
      - Enabled state is persisted by the injected IPluginStateStore.
      - AppAPI may be injected later via set_api() (Qt window must exist first).
      - Optional hooks (additive, non-breaking):
          * on_load(api): called once per process per plugin id (pre-activate)
          * on_ready(api): called once per activation session (post-show),
                           reset when plugin is deactivated/disabled.
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

        # discovered plugin instances (id -> plugin)
        self._plugins: dict[str, IPlugin] = {}
        # active plugin instances (id -> plugin)
        self._active: dict[str, IPlugin] = {}

        # Optional hook bookkeeping
        # - on_load: once per process per plugin id
        # - on_ready: once per activation session (cleared on deactivate)
        self._loaded_once: set[str] = set()
        self._ready_once: set[str] = set()

        self.catalog: list[PluginCatalogItem] = list(catalog or default_catalog())

    @property
    def state_store(self) -> IPluginStateStore:
        return self._state

    def set_api(self, api: IAppAPI) -> None:
        self._api = api

    # ----------------------------- discovery -----------------------------

    def discover(self) -> None:
        """
        Discover plugins via entry points.

        Best-effort:
          - Any broken factory/plugin/meta access is skipped.
        """
        self._plugins.clear()

        for discovered in discover_plugins():
            try:
                factory = discovered.factory
                plugin = factory() if callable(factory) else factory
                meta = plugin.meta
                self._plugins[str(meta.id)] = plugin
            except Exception:
                continue

    def list_plugins(self) -> list[PluginInfo]:
        """
        Return metadata for discovered plugins only (best-effort).
        """
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

        Hook ordering (best-effort):
          1) discover()
          2) deactivate removed/disabled plugins
          3) for each newly-enabled plugin:
               - on_load(api) once per process (if supported)
               - activate(api)
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
                # Allow on_ready to run again if user re-enables later.
                self._ready_once.discard(pid)

        # Activate enabled plugins (best-effort).
        for pid, plugin in self._plugins.items():
            if not self._state.get_enabled(pid, default=False):
                continue
            if pid in self._active:
                continue

            # Optional: on_load runs once per process for this plugin id.
            if pid not in self._loaded_once and isinstance(plugin, IPluginOnLoad):
                try:
                    plugin.on_load(api)
                except Exception:
                    pass
                finally:
                    self._loaded_once.add(pid)

            try:
                plugin.activate(api)
                self._active[pid] = plugin
            except Exception:
                continue

    def on_app_ready(self) -> None:
        """
        Post-show hook to be called by the host after the main window is visible.

        Best-effort:
          - Only runs for currently active plugins.
          - Runs once per activation session per plugin id.
          - Reset when plugin deactivates (handled in reload()).
        """
        api = self._api
        if api is None:
            return

        for pid, plugin in list(self._active.items()):
            if pid in self._ready_once:
                continue

            if isinstance(plugin, IPluginOnReady):
                try:
                    plugin.on_ready(api)
                except Exception:
                    pass
                finally:
                    self._ready_once.add(pid)

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
        """
        return self._iter_actions(api=api, enabled_only=True)

    def iter_actions(
        self, api: IAppAPI
    ) -> Sequence[tuple[ActionSpec, AbcCallable[[IAppAPI], None]]]:
        """
        Returns (ActionSpec, handler) for all discovered plugins (enabled or not).
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

                    def _run(app_api: IAppAPI, h=handler) -> None:
                        h(app_api)

                    actions.append((spec, _run))
            except Exception:
                continue
        return actions
