# PyMarkdownEditor Plugin Development Guide

This document explains how to build plugins for **PyMarkdownEditor** (`pymd`) using the **stable plugin API**.

It covers:

- Plugin discovery (built-in + third-party)
- Plugin lifecycle and hook ordering (deterministic startup)
- How to implement hooks (`on_load`, `activate`, `on_ready`, `deactivate`)
- How to register actions (menu/toolbar actions)
- How to store plugin settings safely
- A complete example: **Built-in Theme Plugin**
- Packaging as a third-party plugin using Python entry points
- Troubleshooting and best practices

---

## 1) Plugin System Overview

### Two plugin sources

PyMarkdownEditor discovers plugins from:

1. **Built-in plugins** shipped with the app (example: Theme plugin)
2. **Third-party plugins** discovered via Python entry points

Discovery is unified and deterministic:

- Built-ins are discovered first
- Entry-point plugins are discovered second

This ensures:

- stable plugin listing in the UI
- stable enable/disable state mapping by `plugin_id`

---

## 2) Deterministic Startup Contract (Host Behavior)

The host application wires plugin lifecycle deterministically in two phases:

### Pre-show phase (bootstrap)

Occurs **before** the main window is shown:

1. Build DI container
2. Build main window
3. Construct AppAPI adapter (`_QtAppAPI` inside `MainWindow`)
4. `plugin_manager.set_api(app_api)`
5. `plugin_manager.reload()`
    - discovers plugins
    - reads enabled-state map
    - activates enabled plugins
    - calls `on_load` (once per process, per plugin) for enabled plugins

### Post-show phase (next tick)

Occurs **after** the main window is visible:

- `plugin_manager.on_app_ready()` scheduled on the next event-loop tick
- allows UI-safe work
- calls `on_ready` once per activation session

This makes plugin execution predictable and safe.

---

## 3) Plugin Enable/Disable State

Enable/disable state is stored in the app settings under:

- `plugins/enabled_map`

The state store is `SettingsPluginStateStore`.

Important behaviors:

- A plugin may be installed/discovered but **disabled**
- Only enabled plugins are activated
- When disabled, the plugin is deactivated (best-effort)

The Plugins UI toggles this state map and triggers reload workflows.

---

## 4) Plugin API Contracts

All plugin interfaces live in:

- `pymd/plugins/api.py`

### API stability rule

`IAppAPI` is intentionally **Qt-free**.

Plugins must not import Qt types or depend on Qt objects.  
They should only rely on `IAppAPI`.

---

## 5) Required Concepts

### Plugin ID

Every plugin must define a stable, globally unique ID.

Recommended formats:

- Reverse-DNS: `org.pymd.theme`
- Namespaced: `com.example.myplugin`

This `plugin_id` is what the state store uses for enable/disable persistence.

---

## 6) Lifecycle Hooks and When to Use Them

Plugins can implement **any subset** of these hooks.

### 6.1 `on_load(api)` (Optional)

**When it runs**

- Called during `plugin_manager.reload()`
- Called **once per process** per plugin ID
- Only for enabled plugins
- Called before `activate`

**Use it for**

- Reading plugin settings
- Warming caches
- Doing quick initialization that doesn’t require a visible window

**Do not**

- Show modal dialogs
- Depend on layout or window visibility

### 6.2 `activate(api)` (Required)

**When it runs**

- Called during `plugin_manager.reload()`
- Called whenever plugin becomes enabled and is activated

**Use it for**

- Store the `api` reference
- Register internal state
- Prepare behavior used by actions or renderers

### 6.3 `on_ready(api)` (Optional)

**When it runs**

- Called after the main window is shown
- Triggered by `plugin_manager.on_app_ready()`
- Runs **once per activation session**
- If plugin is disabled and re-enabled, it can run again

**Use it for**

- Anything requiring a responsive UI loop
- Anything needing the window to be visible
- Deferred UI behavior

### 6.4 `deactivate()` (Required)

**When it runs**

- When plugin is disabled
- When plugin disappears (removed/uninstalled)
- On shutdown (best-effort)

**Use it for**

- Cleanup
- Stop timers
- Release resources
- Cancel background work

---

## 7) Extension Points

Plugins extend the app in V1 through:

### 7.1 Actions (menus/toolbars)

Plugins can register actions using:

- `register_actions() -> Sequence[(ActionSpec, handler)]`

Each action returns:

- `ActionSpec` (metadata describing the action)
- `handler(api)` (callable that receives `IAppAPI`)

The host creates real Qt `QAction` objects around these.

### 7.2 Exporters (optional)

`register_exporters()` is allowed but loosely coupled in V1.

### 7.3 Markdown extensions (optional)

`register_markdown_extensions()` may return python-markdown extensions.

---

## 8) Theme Plugin Example (Built-in)

This section demonstrates a **complete plugin** using:

- `on_load` to read persisted theme selection
- `activate` to store API ref
- `on_ready` to apply the theme after window is visible
- actions to allow theme switching
- plugin settings to store theme config

> Note: The Theme plugin does not need Qt. It communicates through `IAppAPI`.

### 8.1 Example: Theme Plugin Skeleton

Create:

- `pymd/plugins/builtin/theme_plugin.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from pymd.plugins.api import (
    ActionSpec,
    BasePlugin,
    IAppAPI,
    PluginMeta,
    IPluginOnLoad,
    IPluginOnReady,
)

THEME_KEY = "theme"  # plugin-scoped setting key


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    # In V1, store theme configuration as a simple string.
    # This could be CSS name, preset token, or JSON-encoded tokens.
    value: str


THEMES = [
    Theme(id="light", label="Light", value="light"),
    Theme(id="dark", label="Dark", value="dark"),
]


class ThemePlugin(BasePlugin, IPluginOnLoad, IPluginOnReady):
    meta = PluginMeta(
        id="org.pymd.theme",
        name="Theme",
        version="1.0.0",
        description="Built-in theme switcher for preview and editor styling.",
        author="PyMarkdownEditor",
        requires_app=">=0.0.0",
        requires_plugin_api="==1.*",
    )

    def __init__(self) -> None:
        self._api: IAppAPI | None = None
        self._current_theme: str = "light"

    # --------------------
    # Hooks
    # --------------------

    def on_load(self, api: IAppAPI) -> None:
        # Runs once per process; safe place to read settings.
        saved = api.get_plugin_setting(self.meta.id, THEME_KEY, default="light")
        self._current_theme = saved or "light"

    def activate(self, api: IAppAPI) -> None:
        # Called whenever enabled/activated.
        self._api = api

    def on_ready(self, api: IAppAPI) -> None:
        # Runs post-show; apply theme when UI is ready.
        self._apply_theme(self._current_theme)

    def deactivate(self) -> None:
        # Best-effort cleanup.
        self._api = None

    # --------------------
    # Actions
    # --------------------

    def register_actions(self) -> Sequence[tuple[ActionSpec, callable]]:
        return [
            (
                ActionSpec(
                    id="org.pymd.theme.light",
                    title="Theme: Light",
                    menu="View",
                    shortcut=None,
                    status_tip="Switch to the light theme",
                    toolbar=False,
                ),
                lambda api: self._set_theme("light"),
            ),
            (
                ActionSpec(
                    id="org.pymd.theme.dark",
                    title="Theme: Dark",
                    menu="View",
                    shortcut=None,
                    status_tip="Switch to the dark theme",
                    toolbar=False,
                ),
                lambda api: self._set_theme("dark"),
            ),
        ]

    # --------------------
    # Internal helpers
    # --------------------

    def _set_theme(self, theme_id: str) -> None:
        self._current_theme = theme_id
        if self._api is not None:
            self._api.set_plugin_setting(self.meta.id, THEME_KEY, theme_id)
        self._apply_theme(theme_id)

    def _apply_theme(self, theme_id: str) -> None:
        api = self._api
        if api is None:
            return

        # V1: There may be no explicit theme API.
        # Two common strategies:
        #
        # (A) If the host adds "set_theme" later, use it.
        # (B) Use current text as a fallback signal and/or plugin settings
        #     consumed by the host UI layer.
        #
        # For now, demonstrate messaging + setting persistence.

        api.log_info(f"[ThemePlugin] Applying theme: {theme_id}")
        api.show_info("Theme", f"Theme set to: {theme_id}")
````

### 8.2 Notes about the example

* `on_load` reads the saved theme once (fast, pre-activate)
* `on_ready` applies the theme after the window is visible
* `activate` stores `api` so action handlers can use it
* Theme is persisted via `get_plugin_setting / set_plugin_setting`

> If the host later adds `IAppAPI.set_theme(...)`, you can replace `_apply_theme()` with that call without breaking the
> plugin API.

---

## 9) Built-in Plugin Wiring

Built-in plugins are discovered by `pymd/plugins/discovery.py`:

* `_discover_builtin_plugins()` yields `DiscoveredPlugin(factory=ThemePlugin, ...)`

Built-ins:

* appear in the Plugins UI
* can be enabled/disabled
* have `dist_version=None`

---

## 10) Writing a Third-Party Plugin (Entry Points)

To publish an external plugin, create a Python package and expose an entry point.

### 10.1 `pyproject.toml` example

```toml
[project]
name = "pymd-myplugin"
version = "0.1.0"

[project.entry-points."pymarkdowneditor.plugins"]
myplugin = "pymd_myplugin.plugin:Plugin"
```

Where:

* `"pymarkdowneditor.plugins"` is the host entry-point group
* `Plugin` is your plugin class or factory callable

### 10.2 Plugin module example

```python
from pymd.plugins.api import BasePlugin, PluginMeta


class Plugin(BasePlugin):
    meta = PluginMeta(
        id="com.example.myplugin",
        name="My Plugin",
        version="0.1.0",
        description="Example plugin",
    )
```

Install it into the same environment:

```bash
pip install -e .
```

Restart PyMarkdownEditor and it should appear in the Plugins UI.

---

## 11) Storing Plugin Settings

Plugins must store settings using the plugin-scoped API:

* `api.get_plugin_setting(plugin_id, key, default)`
* `api.set_plugin_setting(plugin_id, key, value)`
* `api.remove_plugin_setting(plugin_id, key)`

These settings are stored under:

* `plugins/<plugin_id>/<key>`

### Use strings for stability

The settings API uses strings intentionally so it remains stable across:

* QSettings backends
* future config systems
* platform differences

If you need structured data:

* JSON-encode your payload

Example:

```python
import json

data = {"enabled": True, "level": 3}
api.set_plugin_setting(pid, "config", json.dumps(data))
```

---

## 12) Best Practices

### Keep plugin code resilient

* Wrap your own risky code in try/except
* Fail silently where possible (log warnings)

### Never crash the app

The host is best-effort, but plugin errors should be contained.

### Avoid Qt imports

Your plugin should not import or reference Qt types.
Use `IAppAPI` only.

### Keep hooks fast

* `on_load` and `activate` should be quick
* any heavy work should be delayed or done incrementally

---

## 13) Troubleshooting

### Plugin not showing up

* Ensure it is installed in the same environment
* Verify entry point group matches exactly:

    * `pymarkdowneditor.plugins`
* Confirm the plugin class has `meta` with a valid `id`

### Plugin appears but can’t be enabled

* Ensure `meta.id` is stable and unique
* Verify state store is writing `plugins/enabled_map`

### Hooks not firing

* Confirm the host calls:

    * `plugin_manager.set_api(app_api)` before `reload()`
    * `on_app_ready()` after `win.show()` (scheduled next tick)

### Plugin action not appearing in Tools menu

* Ensure plugin is enabled
* Ensure `register_actions()` returns a list of `(ActionSpec, handler)` tuples

---

## 14) Reference: Hook Execution Order

When the app starts:

1. `plugin_manager.set_api(app_api)`
2. `plugin_manager.reload()`

    * discover()
    * deactivate removed/disabled plugins
    * for enabled plugins:

        * `on_load(api)` once per process
        * `activate(api)`
3. after window shown:

    * `plugin_manager.on_app_ready()`

        * for active plugins:

            * `on_ready(api)` once per activation session

When plugin is disabled:

* `deactivate()`
* `on_ready` is allowed again if re-enabled later

---

## 15) Minimal Plugin Template (Copy/Paste)

```python
from pymd.plugins.api import BasePlugin, PluginMeta, IAppAPI, ActionSpec
from typing import Sequence


class Plugin(BasePlugin):
    meta = PluginMeta(
        id="com.example.plugin",
        name="Example Plugin",
        version="0.1.0",
        description="Example plugin template.",
    )

    def __init__(self) -> None:
        self._api: IAppAPI | None = None

    def activate(self, api: IAppAPI) -> None:
        self._api = api

    def deactivate(self) -> None:
        self._api = None

    def register_actions(self) -> Sequence[tuple[ActionSpec, callable]]:
        return [
            (ActionSpec(id="com.example.plugin.hello", title="Hello", menu="Tools"),
             lambda api: api.show_info("Hello", "Hello from plugin!"))
        ]
```

---

## 16) API Compatibility Policy

The `PLUGIN_API_VERSION` in `pymd/plugins/api.py` follows:

* MAJOR bump: breaking change
* MINOR bump: additive change only

Plugins should declare compatibility with:

* `requires_plugin_api="==1.*"`

---

**End of document**

```
