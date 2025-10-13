from pymd.di.container import Container
from pymd.services.exporters.base import ExporterRegistryInst


def test_container_wires_services_and_registers_exporters():
    c = Container()
    assert c.renderer is not None
    assert c.file_service is not None
    assert c.settings_service is not None
    exporter_registry = ExporterRegistryInst()

    names = [e.name for e in exporter_registry.all()]
    # Expect at least html and pdf
    assert "html" in names and "pdf" in names
