from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QSettings

from pymd.domain.interfaces import (
    IExporterRegistry,
    IFileService,
    IMarkdownRenderer,
    ISettingsService,
)

# New instance registry (no globals)
from pymd.services.exporters.base import ExporterRegistryInst
from pymd.services.exporters.html_exporter import HtmlExporter
from pymd.services.exporters.pdf_exporter import PdfExporter
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService

# UI adapters and presenter
from pymd.services.ui.adapters import QtFileDialogService, QtMessageService

# Qt window (thin view)
from pymd.services.ui.main_window import MainWindow
from pymd.services.ui.presenters import MainPresenter
from pymd.services.ui.presenters.main_presenter import IMainView  # protocol


@dataclass(frozen=True)
class Container:
    """
    Small DI container that wires all app services.
    Nothing global; everything is explicitly injected.
    """

    # Core services
    renderer: IMarkdownRenderer
    files: IFileService
    settings: ISettingsService

    # Exporters registry (instance, not global)
    exporters: IExporterRegistry

    # UI service ports (Qt-backed adapters)
    dialogs: QtFileDialogService
    messages: QtMessageService

    @staticmethod
    def default(
        qsettings: QSettings | None = None,
        *,
        organization: str = "PyMarkdownEditor",
        application: str = "PyMarkdownEditor",
    ) -> Container:
        renderer = MarkdownRenderer()
        files = FileService()

        if qsettings is None:
            qsettings = QSettings(organization, application)
        settings = SettingsService(qsettings)

        # Explicit exporter registry population (no side effects)
        exporters = ExporterRegistryInst()
        exporters.register(HtmlExporter())
        exporters.register(PdfExporter())

        dialogs = QtFileDialogService()
        messages = QtMessageService()

        return Container(
            renderer=renderer,
            files=files,
            settings=settings,
            exporters=exporters,
            dialogs=dialogs,
            messages=messages,
        )

    # ---- UI factories -----------------------------------------------------

    def build_main_presenter(self, view: IMainView) -> MainPresenter:
        """
        Create a MainPresenter bound to a view.
        """
        return MainPresenter(
            view=view,
            renderer=self.renderer,
            files=self.files,
            settings=self.settings,
            messages=self.messages,
            dialogs=self.dialogs,
        )

    def build_main_window(
        self,
        *,
        start_path: Path | None = None,
        app_title: str = "PyMarkdownEditor",
    ) -> MainWindow:
        """
        Create the Qt MainWindow, attach a presenter, and return it.
        """
        window = MainWindow(
            renderer=self.renderer,
            file_service=self.files,
            settings=self.settings,
            exporter_registry=self.exporters,
            start_path=start_path,
            app_title=app_title,
        )

        presenter = self.build_main_presenter(view=window)
        window.attach_presenter(presenter)

        # Let the view/presenter do their normal initial render paths.
        return window


# --- Convenience top-level function -----------------------------------------


def build_main_window(
    qsettings: QSettings | None = None,
    *,
    start_path: Path | None = None,
    app_title: str = "PyMarkdownEditor",
    organization: str = "PyMarkdownEditor",
    application: str = "PyMarkdownEditor",
) -> MainWindow:
    """
    One-call convenience for a ready-to-use window.
    """
    container = Container.default(
        qsettings=qsettings,
        organization=organization,
        application=application,
    )
    return container.build_main_window(start_path=start_path, app_title=app_title)
