from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pymd.plugins.api import (
    ActionSpec,
    BasePlugin,
    IAppAPI,
    IPluginOnLoad,
    IPluginOnReady,
    PluginMeta,
)

# Persisted keys (plugin-scoped)
K_ENABLED = "enabled"
K_THEME_ID = "theme_id"


@dataclass(frozen=True)
class _Theme:
    id: str
    label: str


THEMES: list[_Theme] = [
    _Theme(id="default", label="Default"),
    _Theme(id="midnight", label="Midnight (Dark)"),
    _Theme(id="paper", label="Paper (Light)"),
]


class ThemePlugin(BasePlugin, IPluginOnLoad, IPluginOnReady):
    """
    Example plugin: switches host theme using host-owned theming capability.

    Behavior:
      - Stores its own enabled flag + selected theme id in plugin settings.
      - on_load(): reads settings (no UI assumptions)
      - on_ready(): applies theme once UI is visible (safe post-show)
      - Actions allow selecting a theme + toggling plugin enable state.
    """

    meta = PluginMeta(
        id="org.pymd.theme",
        name="Theme Switcher (Example)",
        version="1.0.0",
        description="Example plugin that switches the editor theme and persists selection.",
        author="PyMarkdownEditor",
        homepage="",
        license="Apache-2.0",
        requires_app=">=0.0.0",
        requires_plugin_api="==1.*",
    )

    def __init__(self) -> None:
        self._api: IAppAPI | None = None
        self._enabled: bool = True
        self._theme_id: str = "default"

    # -----------------------------
    # Lifecycle + optional hooks
    # -----------------------------

    def on_load(self, api: IAppAPI) -> None:
        # Read persisted state (defaults: enabled=true, theme=default)
        self._enabled = (api.get_plugin_setting(self.meta.id, K_ENABLED, "true") or "true").lower() == "true"
        self._theme_id = api.get_plugin_setting(self.meta.id, K_THEME_ID, "default") or "default"

    def activate(self, api: IAppAPI) -> None:
        self._api = api

    def deactivate(self) -> None:
        self._api = None

    def on_ready(self, api: IAppAPI) -> None:
        # Only apply theme when enabled, post-show.
        if not self._enabled:
            return
        self._apply(api, self._theme_id, notify=False)

    # -----------------------------
    # Actions
    # -----------------------------

    def register_actions(self) -> Sequence[tuple[ActionSpec, callable]]:
        acts: list[tuple[ActionSpec, callable]] = []

        acts.append(
            (
                ActionSpec(
                    id="org.pymd.theme.toggle",
                    title="Theme Plugin: Enable/Disable",
                    menu="Tools",
                    status_tip="Toggle the Theme plugin on/off",
                ),
                self._toggle_enabled,
            )
        )

        # Theme options
        for t in THEMES:
            acts.append(
                (
                    ActionSpec(
                        id=f"org.pymd.theme.set.{t.id}",
                        title=f"Theme: {t.label}",
                        menu="Tools",
                        status_tip=f"Switch theme to {t.label}",
                    ),
                    (lambda api, theme_id=t.id: self._select_theme(api, theme_id)),
                )
            )

        return acts

    # -----------------------------
    # Implementation
    # -----------------------------

    def _toggle_enabled(self, api: IAppAPI) -> None:
        self._enabled = not self._enabled
        api.set_plugin_setting(self.meta.id, K_ENABLED, "true" if self._enabled else "false")

        if self._enabled:
            self._apply(api, self._theme_id, notify=True)
        else:
            # Return to default (host decides what “default” means)
            self._apply(api, "default", notify=True)

    def _select_theme(self, api: IAppAPI, theme_id: str) -> None:
        self._theme_id = theme_id
        api.set_plugin_setting(self.meta.id, K_THEME_ID, theme_id)

        if not self._enabled:
            api.show_info("Theme", f"Theme saved as '{theme_id}'. Enable the theme plugin to apply it.")
            return

        self._apply(api, theme_id, notify=True)

    def _apply(self, api: IAppAPI, theme_id: str, *, notify: bool) -> None:
        # Safety: only apply themes host says exist (if list_themes exists).
        try:
            if hasattr(api, "list_themes"):
                allowed = set(api.list_themes())  # type: ignore[misc]
                if theme_id not in allowed:
                    theme_id = "default"
        except Exception:
            theme_id = "default"

        try:
            if hasattr(api, "set_theme"):
                api.set_theme(theme_id)  # type: ignore[misc]
                if notify:
                    api.show_info("Theme", f"Theme switched to '{theme_id}'.")
            else:
                if notify:
                    api.show_warning(
                        "Theme",
                        "Host does not support theming yet (missing IAppAPI.set_theme).",
                    )
        except Exception as e:
            if notify:
                api.show_error("Theme Error", f"Failed to apply theme: {e}")
