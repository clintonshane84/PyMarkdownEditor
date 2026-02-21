from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import entry_points, version

from pymd.plugins import ENTRYPOINT_GROUP


@dataclass(frozen=True)
class DiscoveredPlugin:
    """
    A discovered plugin factory.

    - factory: a callable that returns an IPlugin instance (or an instance itself)
    - entry_point_name: stable identifier for the discovery source
    - dist_version: distribution version (only for installed packages; None for built-ins)
    """

    factory: object
    entry_point_name: str
    dist_version: str | None


def _discover_builtin_plugins() -> Iterable[DiscoveredPlugin]:
    """
    Built-in plugins shipped with the app.

    These are first-class plugins:
      - they appear in the Plugins UI (via PluginManager.get_installed_rows())
      - they can be enabled/disabled (state store still controls activation)

    Best-effort: if a built-in import fails, skip it rather than breaking the app.
    """
    # Theme plugin (example plugin bundled with the app)
    try:
        # Expected to exist per your request:
        #   pymd/plugins/builtin/theme_plugin.py -> ThemePlugin
        from pymd.plugins.builtin.theme_plugin import ThemePlugin  # type: ignore

        yield DiscoveredPlugin(
            factory=ThemePlugin,
            entry_point_name="builtin:org.pymd.theme",
            dist_version=None,
        )
    except Exception:
        # Built-ins must never crash discovery in lean builds.
        return


def _discover_entrypoint_plugins() -> Iterable[DiscoveredPlugin]:
    """
    Third-party plugins discovered via Python entry points.
    """
    eps = entry_points()
    group_eps = (
        eps.select(group=ENTRYPOINT_GROUP)
        if hasattr(eps, "select")
        else eps.get(ENTRYPOINT_GROUP, [])
    )

    for ep in group_eps:
        dist_ver: str | None = None
        try:
            # ep.dist is not always available across Python versions/tooling; best-effort.
            if getattr(ep, "dist", None) is not None:
                dist_ver = version(ep.dist.name)  # type: ignore[attr-defined]
        except Exception:
            dist_ver = None

        try:
            factory = ep.load()
        except Exception:
            # A broken entry point should not break the app.
            continue

        yield DiscoveredPlugin(
            factory=factory,
            entry_point_name=str(ep.name),
            dist_version=dist_ver,
        )


def discover_plugins() -> Iterable[DiscoveredPlugin]:
    """
    Unified plugin discovery:
      1) built-in plugins shipped with the app
      2) third-party plugins via entry points

    Ordering is deterministic so:
      - the Plugins UI list is stable
      - enable/disable state maps to stable plugin_id values
    """
    yield from _discover_builtin_plugins()
    yield from _discover_entrypoint_plugins()
