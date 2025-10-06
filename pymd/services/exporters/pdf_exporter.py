from __future__ import annotations
from pathlib import Path
from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtCore import QMarginsF

from pymd.domain.interfaces import IExporter

class PdfExporter(IExporter):
    name = "pdf"
    label = "Export PDF…"

    def export(self, html: str, out_path: Path) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(out_path))
        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(12.7, 12.7, 12.7, 12.7),
            QPageLayout.Unit.Millimeter,
        )
        printer.setPageLayout(layout)

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print(printer)
