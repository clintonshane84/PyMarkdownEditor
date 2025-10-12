from __future__ import annotations

from dataclasses import dataclass, field

from pymd.domain.interfaces import IExporter, IExporterRegistry


@dataclass
class ExporterRegistryInst(IExporterRegistry):
    """
    Instance-based exporter registry (no globals, no side-effects).
    Keeps registry local to the DI container for testability and clarity.
    """

    _reg: dict[str, IExporter] = field(default_factory=dict)

    def register(self, e: IExporter) -> None:
        self._reg[e.name] = e

    def get(self, name: str) -> IExporter:
        return self._reg[name]

    def all(self) -> list[IExporter]:
        return list(self._reg.values())
