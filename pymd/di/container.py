from __future__ import annotations

from PyQt6.QtCore import QSettings

from pymd.domain.interfaces import IFileService, IMarkdownRenderer, ISettingsService

# Exporter registry: singleton-style instance that tests import as ExporterRegistryInst
from pymd.services.exporters.base import ExporterRegistryInst
from pymd.services.exporters.html_exporter import HtmlExporter
from pymd.services.exporters.pdf_exporter import PdfExporter
from pymd.services.file_service import FileService
from pymd.services.markdown_renderer import MarkdownRenderer
from pymd.services.settings_service import SettingsService

# Current Qt window (thin view)
from pymd.services.ui.main_window import MainWindow

# Optional adapters & presenter: keep functionality if present, but don't hard-fail if not.
try:
    from pymd.services.ui.adapters import QtFileDialogService, QtMessageService  # type: ignore
except Exception:  # pragma: no cover - optional
    QtFileDialogService = None  # type: ignore
    QtMessageService = None  # type: ignore

try:
    from pymd.services.ui.presenters import MainPresenter  # type: ignore
    from pymd.services.ui.presenters.main_presenter import IMainView  # type: ignore
except Exception:  # pragma: no cover - optional
    MainPresenter = None  # type: ignore
    IMainView = None  # type: ignore


class Container:
    """
    Lightweight DI container:
      - Wires default services if not provided
      - Ensures built-in exporters (html, pdf) are registered in the singleton registry
      - Optionally wires presenter/adapters if those modules are available
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

        # Optional UI service ports (Qt-backed adapters) if available
        self.dialogs = dialogs
        self.messages = messages
        if self.dialogs is None and QtFileDialogService is not None:
            self.dialogs = QtFileDialogService()  # type: ignore[call-arg]
        if self.messages is None and QtMessageService is not None:
            self.messages = QtMessageService()  # type: ignore[call-arg]

        # Register built-in exporters if missing
        self._ensure_builtin_exporters()

    # ---------- Class helpers (parity with previous API) ----------

    @staticmethod
    def default(
        qsettings: QSettings | None = None,
        *,
        organization: str = "PyMarkdownEditor",
        application: str = "PyMarkdownEditor",
    ) -> Container:
        """
        Build a default container (similar to prior dataclass factory),
        keeping compatibility with earlier callers.
        """
        if qsettings is None:
            qsettings = QSettings(organization, application)
        return Container(qsettings=qsettings)

    # ---------- Internals ----------

    def _ensure_builtin_exporters(self) -> None:
        # html
        try:
            ExporterRegistryInst.get("html")
        except KeyError:
            ExporterRegistryInst.register(HtmlExporter())

        # pdf
        try:
            ExporterRegistryInst.get("pdf")
        except KeyError:
            ExporterRegistryInst.register(PdfExporter())

    # ---------- UI factories ----------

    def build_main_presenter(self, view) -> object:
        """
        Create a MainPresenter bound to a view (if presenter layer is available).
        Kept for backward compatibility with the previous architecture.

        Returns the presenter instance, or raises RuntimeError if presenter code
        is not available in this build.
        """
        if MainPresenter is None:  # pragma: no cover - optional
            raise RuntimeError("Presenter layer is not available in this build.")

        # We don't hard type here to avoid importing Protocols when unavailable.
        return MainPresenter(  # type: ignore[call-arg]
            view=view,
            renderer=self.renderer,
            files=self.file_service,
            settings=self.settings_service,
            messages=self.messages,
            dialogs=self.dialogs,
        )

    def build_main_window(
        self,
        *,
        start_path=None,
        app_title: str = "PyMarkdownEditor",
    ) -> MainWindow:
        """
        Create the Qt MainWindow, wire services, and (optionally) attach a presenter
        if presenter layer is available and the view exposes `attach_presenter`.
        """
        window = MainWindow(
            renderer=self.renderer,
            file_service=self.file_service,
            settings=self.settings_service,
            start_path=start_path,
            app_title=app_title,
        )

        # Attach presenter if both the presenter and adapters exist and the view supports it
        if MainPresenter is not None and self.messages is not None and self.dialogs is not None:
            try:
                presenter = self.build_main_presenter(view=window)
                if hasattr(window, "attach_presenter"):
                    window.attach_presenter(presenter)  # type: ignore[attr-defined]
            except Exception:
                # Presenter layer is optional; UI works fine without it.
                pass

        return window


# --- Convenience top-level function (parity with prior API) ------------------


def build_main_window(
    qsettings: QSettings | None = None,
    *,
    start_path=None,
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
