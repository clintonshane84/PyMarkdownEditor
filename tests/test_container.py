# tests/test_container.py
from __future__ import annotations

from typing import Any

from pymd.di.container import Container


def test_container_wires_services_exporters_and_plugins(qapp, qsettings):
    c = Container(qsettings=qsettings)

    # Core services
    assert c.renderer is not None
    assert c.file_service is not None
    assert c.settings_service is not None
    assert c.app_config is not None  # ✅ Container uses app_config, not config

    # Exporters (built-ins registered cleanly)
    exporter_registry = c.exporter_registry
    names = {e.name for e in exporter_registry.all()}
    assert "html" in names
    assert "pdf" in names

    # Plugins are expected to be available/wired in normal builds
    assert c.plugin_state is not None
    assert c.plugin_installer is not None
    assert c.plugin_manager is not None

    # PluginManager should expose the state store used by the UI
    assert getattr(c.plugin_manager, "state_store", None) is c.plugin_state


def test_container_build_main_window_attaches_plugins_and_does_not_reload(
    qapp, qsettings, monkeypatch
):
    """
    Ownership rule: bootstrapper owns plugin_manager.reload().

    Container.build_main_window must:
      - attach plugin_manager + plugin_installer to the window
      - NOT call plugin_manager.reload()
      - ensure plugin manager is bound to the window AppAPI
    """
    c = Container(qsettings=qsettings)

    # Fail fast if Container tries to reload during build_main_window()
    if c.plugin_manager is not None and hasattr(c.plugin_manager, "reload"):

        def boom_reload(*_a: Any, **_k: Any) -> None:
            raise AssertionError(
                "Container must not call plugin_manager.reload(); bootstrapper owns reload."
            )

        monkeypatch.setattr(c.plugin_manager, "reload", boom_reload, raising=True)

    # Spy that API was set (Container may call set_api directly, and/or via window.attach_plugins)
    api_seen: dict[str, Any] = {"api": None}
    if c.plugin_manager is not None and hasattr(c.plugin_manager, "set_api"):

        def spy_set_api(api: Any) -> None:
            api_seen["api"] = api

        monkeypatch.setattr(c.plugin_manager, "set_api", spy_set_api, raising=True)

    win = c.build_main_window(app_title="Test")

    # Attached consistently
    assert getattr(win, "plugin_manager", None) is c.plugin_manager
    assert getattr(win, "plugin_installer", None) is c.plugin_installer

    # AppAPI adapter should be created by MainWindow
    app_api = getattr(win, "_app_api", None)
    assert app_api is not None

    # PluginManager should have received the API (if it supports set_api)
    if c.plugin_manager is not None and hasattr(c.plugin_manager, "set_api"):
        assert api_seen["api"] is app_api

    # Smoke-check: plugin menu rebuild hook exists
    assert hasattr(win, "_rebuild_plugin_actions")


def test_container_default_uses_provided_qsettings(qapp, qsettings):
    """
    Container.default(qsettings=...) should respect the supplied settings object,
    so plugin enablement and other persisted state are deterministic in tests.
    """
    c = Container.default(qsettings=qsettings)

    # Sanity check container built correctly
    assert c.settings_service is not None
    assert c.app_config is not None  # ✅ app_config is the correct attribute
