from PyQt6.QtCore import QSettings

from pymd.di.container import Container


def test_container_wires_services_and_registers_exporters():
    c = Container()
    assert c.renderer is not None
    assert c.file_service is not None
    assert c.settings_service is not None
    exporter_registry = c.exporter_registry

    names = [e.name for e in exporter_registry.all()]
    # Expect at least html and pdf
    assert "html" in names and "pdf" in names


def test_container_default_uses_file_backed_user_ini_settings():
    c = Container.default()
    qsettings = c.settings_service.qsettings  # type: ignore[attr-defined]
    assert isinstance(qsettings, QSettings)
    assert qsettings.format() == QSettings.Format.IniFormat
    assert qsettings.fileName() != ""
