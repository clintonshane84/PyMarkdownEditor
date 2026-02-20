from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PluginCatalogItem:
    plugin_id: str  # matches plugin.meta.id once installed
    name: str
    pip_package: str  # e.g. "pymd-plugin-uppercase"
    description: str = ""
    homepage: str = ""


def default_catalog() -> Sequence[PluginCatalogItem]:
    # Replace with your real “official” plugins once you publish them.
    return [
        PluginCatalogItem(
            plugin_id="com.pymd.plugins.uppercase",
            name="Uppercase Tool",
            pip_package="pymd-plugin-uppercase",
            description="Adds a Tools menu action to uppercase the current document.",
        ),
        PluginCatalogItem(
            plugin_id="com.pymd.plugins.wordcount",
            name="Word Count",
            pip_package="pymd-plugin-wordcount",
            description="Shows word/char counts for the current document.",
        ),
    ]
