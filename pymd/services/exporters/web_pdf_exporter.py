# pymd/services/exporters/web_pdf_exporter.py
from __future__ import annotations

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
except Exception as e:
    raise RuntimeError(
        "Qt WebEngine is not available. Install PyQt6-WebEngine to enable Web PDF export."
    ) from e

from pathlib import Path

from PyQt6.QtCore import QEventLoop, QMarginsF, QTimer
from PyQt6.QtGui import QPageLayout, QPageSize

from pymd.domain.interfaces import IExporter


class WebEnginePdfExporter(IExporter):
    """
    Render HTML to PDF via Qt WebEngine for output that matches the preview.
    Falls back by raising a clear error if QtWebEngine is unavailable.
    """

    name = "pdf"
    label = "Export PDF…"
    file_ext = "pdf"

    def __init__(
        self,
        page_size: QPageSize | None = None,
        margins_mm: tuple[float, float, float, float] = (12.7, 12.7, 12.7, 12.7),
        orientation: QPageLayout.Orientation = QPageLayout.Orientation.Portrait,
        timeout_ms: int = 15000,
    ) -> None:
        self._page_size = page_size or QPageSize(QPageSize.PageSizeId.A4)
        self._margins = QMarginsF(*margins_mm)
        self._orientation = orientation
        self._timeout_ms = timeout_ms

    def export(self, html: str, out_path: Path) -> None:
        page = QWebEngineView()
        loop = QEventLoop()
        errored: list[Exception | None] = [None]

        # Safety timeout
        def on_timeout():
            if loop.isRunning():
                errored[0] = TimeoutError("Timed out while rendering PDF")
                loop.quit()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(on_timeout)
        timer.start(self._timeout_ms)

        # After load, print to PDF
        def on_load_finished(ok: bool):
            if not ok:
                errored[0] = RuntimeError("Failed to load HTML into WebEngine page")
                loop.quit()
                return

            layout = QPageLayout(
                self._page_size, self._orientation, self._margins, QPageLayout.Unit.Millimeter
            )

            def on_pdf_ready(data: bytes):
                try:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(data)
                except Exception as ex:
                    errored[0] = ex
                finally:
                    loop.quit()

            # Qt ≥ 6.6 supports pageLayout kwarg
            try:
                page.printToPdf(on_pdf_ready, pageLayout=layout)
            except TypeError:
                # Older bindings may not support the kwarg name—try positional form
                page.printToPdf(on_pdf_ready, layout)

        page.loadFinished.connect(on_load_finished)

        # IMPORTANT: connect signals before calling setHtml
        page.setHtml(html)
        loop.exec()

        if errored[0] is not None:
            raise errored[0]
