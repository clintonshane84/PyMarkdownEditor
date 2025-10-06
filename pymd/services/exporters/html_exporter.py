from __future__ import annotations
from pathlib import Path
from pymd.domain.interfaces import IExporter


class HtmlExporter(IExporter):
    name = "html"
    label = "Export HTML…"

    def export(self, html: str, out_path: Path) -> None:
        out_path.write_text(html, encoding="utf-8")
