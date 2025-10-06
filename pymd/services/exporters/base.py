from __future__ import annotations
from typing import Dict, List
from pymd.domain.interfaces import IExporter

class ExporterRegistry:
    """
    Simple registry/factory for export strategies (OCP).
    UI can iterate over `all()` to build dynamic export menus.
    """
    _registry: Dict[str, IExporter] = {}

    @classmethod
    def register(cls, exporter: IExporter) -> None:
        cls._registry[exporter.name] = exporter

    @classmethod
    def get(cls, name: str) -> IExporter:
        return cls._registry[name]

    @classmethod
    def all(cls) -> List[IExporter]:
        return list(cls._registry.values())
