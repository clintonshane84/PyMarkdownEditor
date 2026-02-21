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

    # Exporters (built-ins registered cleanly)
    exporter_registry = c.exporter_registry
    names = {e.name for e in exporter_registry.all()}
    assert "html" in names
    assert "pdf" in names

    # Plugins: feature should be enabled / wired
    assert c.plugin_state is not None
    assert c.plugin_installer is not None
    assert c.plugin_manager is not None

    # PluginManager should expose state store
    assert c.plugin_manager.state_store is c.plugin_state


def test_container_build_main_window_attaches_plugin_manager_and_installer_but_does_not_reload(qapp, qsettings,
                                                                                               monkeypatch):
    """
    Ownership rule: bootstrapper owns plugin_manager.reload().

    Container/build_main_window must:
      - always attach plugin_manager + plugin_installer to the window
      - ensure AppAPI is set (via MainWindow.attach_plugins)
      - NOT call plugin_manager.reload()
    """
    c = Container(qsettings=qsettings)

    # Fail fast if Container tries to reload during build_main_window()
    def boom_reload() -> None:
        raise AssertionError("Container must not call plugin_manager.reload(); bootstrapper owns reload.")

    monkeypatch.setattr(c.plugin_manager, "reload", boom_reload, raising=True)

    win = c.build_main_window(app_title="Test")

    # Attached consistently
    assert getattr(win, "plugin_manager", None) is c.plugin_manager
    assert getattr(win, "plugin_installer", None) is c.plugin_installer

    # AppAPI adapter should be created by MainWindow and bound to PluginManager via attach_plugins()
    app_api = getattr(win, "_app_api", None)
    assert app_api is not None

    # PluginManager should now have an API set (private but stable for this test)
    assert getattr(c.plugin_manager, "_api", None) is app_api


def test_container_default_uses_provided_qsettings(qapp, qsettings):
    """
    Container.default(qsettings=...) should respect the supplied settings object,
    so plugin enablement and other persisted state are deterministic in tests.
    """
    c = Container.default(qsettings=qsettings)
    assert c.settings_service is not None
    # SettingsService is an abstraction; we just assert the container was created successfully.
    # (Avoid reaching into SettingsService internals.)
