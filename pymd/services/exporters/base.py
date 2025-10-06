from __future__ import annotations

from typing import ClassVar

from pymd.domain.interfaces import IExporter


class ExporterRegistry:
    """
    Simple registry/factory for export strategies (OCP).
    UI can iterate over `all()` to build dynamic export menus.
    """

    _registry: ClassVar[dict[str, IExporter]] = {}

    @classmethod
    def register(cls, exporter: IExporter) -> None:
        cls._registry[exporter.name] = exporter

    @classmethod
    def get(cls, name: str) -> IExporter:
        return cls._registry[name]

    @classmethod
    def all(cls) -> list[IExporter]:
        return list(cls._registry.values())
