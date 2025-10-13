from __future__ import annotations

from PyQt6.QtCore import QSettings

from pymd.domain.interfaces import (
    IExporterRegistry,
    IFileService,
    IMarkdownRenderer,
    ISettingsService,
)

# Exporter registry: **singleton instance** (do NOT call it)
from pymd.services.exporters.base import ExporterRegistryInst
from pymd.services.exporters.html_exporter import HtmlExporter
from pymd.services.exporters.pdf_exporter import PdfExporter
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService

# Thin Qt window
from pymd.services.ui.main_window import MainWindow

# Optional adapters & presenter (keep optional to avoid hard failures in lean builds)
try:
    from pymd.services.ui.adapters import QtFileDialogService, QtMessageService  # type: ignore
except Exception:  # pragma: no cover
    QtFileDialogService = None  # type: ignore
    QtMessageService = None  # type: ignore

try:
    from pymd.services.ui.presenters import MainPresenter  # type: ignore
except Exception:  # pragma: no cover
    MainPresenter = None  # type: ignore


class Container:
    """
    Lightweight DI container:
      - Wires default services if not provided.
      - Ensures built-in exporters (html, pdf) are registered on the singleton registry.
      - Optionally wires presenter/adapters if present.
    """

    def __init__(
        self,
        renderer: IMarkdownRenderer | None = None,
        files: IFileService | None = None,
        settings: ISettingsService | None = None,
        qsettings: QSettings | None = None,
        dialogs: object | None = None,
        messages: object | None = None,
    ) -> None:
        # Core services (defaults if not supplied)
        self.renderer: IMarkdownRenderer = renderer or MarkdownRenderer()
        self.file_service: IFileService = files or FileService()
        self.settings_service: ISettingsService = settings or SettingsService(
            qsettings or QSettings()
        )

        # Exporter registry **singleton instance**
        self.exporter_registry: IExporterRegistry = ExporterRegistryInst

        # Ensure built-ins are present on the same instance the tests will read
        self._ensure_builtin_exporters(self.exporter_registry)

        # Optional UI ports
        self.dialogs = (
            dialogs
            if dialogs is not None
            else (
                QtFileDialogService() if QtFileDialogService is not None else None  # type: ignore[call-arg]
            )
        )
        self.messages = (
            messages
            if messages is not None
            else (
                QtMessageService() if QtMessageService is not None else None  # type: ignore[call-arg]
            )
        )

    # ---------- Class helper (compat with prior API) ----------

    @staticmethod
    def default(
        qsettings: QSettings | None = None,
        *,
        organization: str = "PyMarkdownEditor",
        application: str = "PyMarkdownEditor",
    ) -> Container:
        if qsettings is None:
            qsettings = QSettings(organization, application)
        return Container(qsettings=qsettings)

    # ---------- Internals ----------

    def _ensure_builtin_exporters(self, exporter_registry: IExporterRegistry) -> None:
        # html
        try:
            exporter_registry.get("html")
        except KeyError:
            exporter_registry.register(HtmlExporter())

        # pdf
        try:
            exporter_registry.get("pdf")
        except KeyError:
            exporter_registry.register(PdfExporter())

    # ---------- UI factories ----------

    def build_main_presenter(self, view) -> object:
        """
        Create a MainPresenter bound to a view (if presenter layer is available).
        """
        if MainPresenter is None:  # pragma: no cover
            raise RuntimeError("Presenter layer is not available in this build.")

        return MainPresenter(  # type: ignore[call-arg]
            view=view,
            renderer=self.renderer,
            files=self.file_service,
            settings=self.settings_service,
            messages=self.messages,
            dialogs=self.dialogs,
            exporter_registry=self.exporter_registry,
        )

    def build_main_window(
        self,
        *,
        start_path=None,
        app_title: str = "PyMarkdownEditor",
    ) -> MainWindow:
        """
        Create the Qt MainWindow, wire services, and (optionally) attach a presenter.
        """
        window = MainWindow(
            renderer=self.renderer,
            file_service=self.file_service,
            settings=self.settings_service,
            exporter_registry=self.exporter_registry,
            start_path=start_path,
            app_title=app_title,
        )

        # Attach presenter if available
        try:
            if MainPresenter is not None and self.messages is not None and self.dialogs is not None:
                presenter = self.build_main_presenter(view=window)
                if hasattr(window, "attach_presenter"):
                    window.attach_presenter(presenter)  # type: ignore[attr-defined]
        except Exception:
            # Presenter layer optional; ignore failures here.
            pass

        return window


# --- Convenience function (parity with prior API) ----------------------------


def build_main_window(
    qsettings: QSettings | None = None,
    *,
    start_path=None,
    app_title: str = "PyMarkdownEditor",
    organization: str = "PyMarkdownEditor",
    application: str = "PyMarkdownEditor",
) -> MainWindow:
    container = Container.default(
        qsettings=qsettings,
        organization=organization,
        application=application,
    )
    return container.build_main_window(start_path=start_path, app_title=app_title)
