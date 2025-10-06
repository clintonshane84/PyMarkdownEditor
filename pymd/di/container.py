from __future__ import annotations

from PyQt6.QtCore import QSettings

from pymd.services.exporters.base import ExporterRegistry
from pymd.services.exporters.html_exporter import HtmlExporter
from pymd.services.exporters.pdf_exporter import PdfExporter
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService
from pymd.utils.constants import APP_NAME, APP_ORG


class Container:
    """
    Tiny DI container. Central place to swap implementations or register strategies.
    """

    def __init__(self) -> None:
        # Core services
        self.qsettings = QSettings(APP_ORG, APP_NAME)
        self.renderer = MarkdownRenderer()
        self.file_service = FileService()
        self.settings_service = SettingsService(self.qsettings)

        # Exporters (Strategy + Registry)
        ExporterRegistry.register(HtmlExporter())
        ExporterRegistry.register(PdfExporter())
