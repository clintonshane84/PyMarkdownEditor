from __future__ import annotations

from pymd.di.container import Container


def test_container_wires_services_exporters_and_plugins(qapp, qsettings):
    # Arrange
    c = Container(qsettings=qsettings)

    # Core services
    assert c.renderer is not None
    assert c.file_service is not None
    assert c.settings_service is not None

    # Exporters
    exporter_registry = c.exporter_registry
    names = {e.name for e in exporter_registry.all()}
    assert "html" in names
    assert "pdf" in names

    # Plugins: feature should be enabled / wired
    assert c.plugin_state is not None
    assert c.pip_installer is not None
    assert c.plugin_manager is not None

    # Sanity: PluginManager should expose state store (per your manager.py)
    assert getattr(c.plugin_manager, "state_store") is c.plugin_state
