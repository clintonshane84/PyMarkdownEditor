from pathlib import Path

import pytest

from pymd.domain.interfaces import IExporter
from pymd.services.exporters import ExporterRegistryInst


class DummyExporter(IExporter):
    name = "dummy"
    label = "Export Dummy…"

    def __init__(self):
        self.called = False

    def export(self, html: str, out_path: Path) -> None:
        self.called = True
        out_path.write_text("ok", encoding="utf-8")


def test_registry_register_and_get(tmp_path):
    d = DummyExporter()
    exporter_registry = ExporterRegistryInst()
    exporter_registry.register(d)
    got = exporter_registry.get("dummy")
    assert got is d


def test_registry_all_contains_registered():
    exporter_registry = ExporterRegistryInst()
    assert any(exp.name == "dummy" for exp in exporter_registry.all())


def test_registry_get_unknown_key_raises():
    with pytest.raises(KeyError):
        exporter_registry = ExporterRegistryInst()
        exporter_registry.get("__does_not_exist__")
