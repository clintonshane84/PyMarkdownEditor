from __future__ import annotations

from pymd.domain.interfaces import IExporter, IExporterRegistry


class ExporterRegistryInst(IExporterRegistry):
    """
    Per-instance exporter registry for tests and DI.
    Tests expect to call `ExporterRegistryInst()` to get a fresh, empty registry.
    """

    def __init__(self) -> None:
        self._registry: dict[str, IExporter] = {}

    def register(self, e: IExporter) -> None:
        self._registry[e.name] = e

    def get(self, name: str) -> IExporter:
        return self._registry[name]

    def all(self) -> list[IExporter]:
        return list(self._registry.values())
