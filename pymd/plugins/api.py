from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

# -----------------------------------------------------------------------------
# Plugin API versioning
# -----------------------------------------------------------------------------
# Bump MAJOR when you introduce breaking changes to these contracts.
PLUGIN_API_VERSION = "1.1"

# Conventional entry-point group name plugin packages should use in pyproject.toml:
# [project.entry-points."pymarkdowneditor.plugins"]
# my_plugin = "my_pkg.plugin:Plugin"
ENTRYPOINT_GROUP = "pymarkdowneditor.plugins"

# -----------------------------------------------------------------------------
# Core metadata + action specs
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginMeta:
    """
    Metadata describing a plugin.

    Notes:
      - `id` must be globally unique and stable over time. Use reverse-DNS or
        a clear namespace: "org.pymd.spellcheck" / "com.example.uppercase".
      - `requires_app` and `requires_plugin_api` are version range strings
        (semver-like). The host may choose to validate strictly or loosely.
    """

    id: str  # e.g. "org.pymd.spellcheck"
    name: str  # Human-friendly display name
    version: str  # Plugin package version (semver recommended)
    description: str = ""
    author: str = ""
    homepage: str = ""
    license: str = ""
    requires_app: str = ">=0.0.0"
    requires_plugin_api: str = "==1.*"


MenuName = Literal["File", "Edit", "View", "Tools", "Export", "Help"]


@dataclass(frozen=True)
class ActionSpec:
    """
    Declarative description of an action the host can surface via menu/toolbar.

    Notes:
      - `id` should be unique within the plugin namespace.
      - `menu` is a suggested placement; the host may re-home actions.
      - `toolbar=True` is only a hint; host may ignore.
    """

    id: str  # e.g. "org.pymd.spellcheck.toggle"
    title: str  # UI label
    menu: str | MenuName  # e.g. "Tools", "Edit", "Export"
    shortcut: str | None = None
    status_tip: str | None = None
    toolbar: bool = False


# -----------------------------------------------------------------------------
# Host -> Plugin stable API (no Qt types)
# -----------------------------------------------------------------------------


class IAppAPI(Protocol):
    """
    Stable capabilities exposed to plugins.

    IMPORTANT:
      - No Qt types should appear here.
      - Keep this interface narrow and additive.
      - Prefer returning plain data (str/bool/int/dicts) not objects.
    """

    # -----------------------------
    # Document/text operations
    # -----------------------------
    def get_current_text(self) -> str: ...
    def set_current_text(self, text: str) -> None: ...
    def insert_text_at_cursor(self, text: str) -> None: ...

    # Optional but useful context
    def get_current_path(self) -> str | None: ...
    def is_modified(self) -> bool: ...

    # -----------------------------
    # UX messaging
    # -----------------------------
    def show_info(self, title: str, message: str) -> None: ...
    def show_warning(self, title: str, message: str) -> None: ...
    def show_error(self, title: str, message: str) -> None: ...

    # -----------------------------
    # Export by registered exporter id
    # -----------------------------
    def export_current(self, exporter_id: str) -> None: ...

    # -----------------------------
    # Plugin-scoped settings
    # -----------------------------
    # Intentionally typed as strings for long-term stability across settings backends.
    # Plugin authors can encode JSON if needed.
    def get_plugin_setting(
        self,
        plugin_id: str,
        key: str,
        default: str | None = None,
    ) -> str | None: ...

    def set_plugin_setting(self, plugin_id: str, key: str, value: str) -> None: ...

    def remove_plugin_setting(self, plugin_id: str, key: str) -> None: ...

    # -----------------------------
    # Logging (optional but recommended)
    # -----------------------------
    def log_debug(self, message: str) -> None: ...
    def log_info(self, message: str) -> None: ...
    def log_warning(self, message: str) -> None: ...
    def log_error(self, message: str) -> None: ...

    # -----------------------------
    # Theming (host-controlled)
    # -----------------------------
    def set_theme(self, theme_id: str) -> None: ...

    def get_theme(self) -> str: ...

    def list_themes(self) -> Sequence[str]: ...

# -----------------------------------------------------------------------------
# Plugin contract
# -----------------------------------------------------------------------------


@runtime_checkable
class IPlugin(Protocol):
    """
    Main plugin contract.

    Lifecycle:
      - activate(api) is called when plugin is enabled (or on app startup if enabled)
      - deactivate() is called when plugin is disabled and on shutdown

    Extension points are "pull" based (host asks plugin what it provides).
    Keep implementations resilient: never assume host calls order beyond lifecycle.
    """

    meta: PluginMeta

    # -----------------------------
    # Lifecycle
    # -----------------------------
    def activate(self, api: IAppAPI) -> None:
        """Called when plugin is enabled. Store api if needed."""
        ...

    def deactivate(self) -> None:
        """Called when plugin is disabled or app exits. Cleanup timers/resources."""
        ...

    # -----------------------------
    # Extension points
    # -----------------------------
    def register_actions(self) -> Sequence[tuple[ActionSpec, Callable[[IAppAPI], None]]]:
        """
        Return a list of (ActionSpec, handler) tuples.
        Handlers receive the IAppAPI and must not depend on Qt.
        """
        return ()

    def register_exporters(self) -> Sequence[object]:
        """
        Optional: return exporter instances that the host can register.
        Exporter interface is host-defined; keep this loosely coupled in V1.
        """
        return ()

    def register_markdown_extensions(self) -> Sequence[object]:
        """
        Optional: return python-markdown extensions or renderer hooks.

        Host may:
          - Accept python-markdown Extension objects, OR
          - Accept a host-defined adapter/hook type.

        In V1, keep this simple and document what you support in host docs.
        """
        return ()


# -----------------------------------------------------------------------------
# Optional lifecycle hooks (duck-typed by host)
# -----------------------------------------------------------------------------


@runtime_checkable
class IPluginOnLoad(Protocol):
    """
    Optional hook: called once per app start for enabled plugins, before activate().

    Use cases:
      - read plugin settings
      - warm caches
      - validate environment
      - register non-UI integrations that don't require a visible window
    """

    def on_load(self, api: IAppAPI) -> None: ...


@runtime_checkable
class IPluginOnReady(Protocol):
    """
    Optional hook: called after the main window is shown (post-show).

    Use cases:
      - UI-related work that benefits from a responsive event loop
      - "first render" enhancements
      - deferred initialization (timers, async tasks) that should start after show()
    """

    def on_ready(self, api: IAppAPI) -> None: ...


# -----------------------------------------------------------------------------
# Optional: convenience base class plugin authors can inherit from
# -----------------------------------------------------------------------------


class BasePlugin:
    """
    Optional convenience base class that implements no-op lifecycle and extensions.
    Plugin authors may inherit from this instead of implementing everything.
    """

    meta: PluginMeta

    def activate(self, api: IAppAPI) -> None:  # pragma: no cover
        self._api = api  # type: ignore[attr-defined]

    def deactivate(self) -> None:  # pragma: no cover
        pass

    def register_actions(
        self,
    ) -> Sequence[tuple[ActionSpec, Callable[[IAppAPI], None]]]:  # pragma: no cover
        return ()

    def register_exporters(self) -> Sequence[object]:  # pragma: no cover
        return ()

    def register_markdown_extensions(self) -> Sequence[object]:  # pragma: no cover
        return ()

    # Optional hooks can be implemented by subclasses without inheriting from
    # separate mixins; the host will check via runtime protocols (best-effort).
    def on_load(self, api: IAppAPI) -> None:  # pragma: no cover
        _ = api

    def on_ready(self, api: IAppAPI) -> None:  # pragma: no cover
        _ = api
