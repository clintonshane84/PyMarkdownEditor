from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from pymd.di.container import Container
from pymd.utils.constants import APP_NAME, APP_ORG


def run_app(argv: Sequence[str]) -> int:
    """
    Bootstraps Qt, composes the application via the DI container,
    optionally shows a splash screen during startup, and launches the main window.
    """
    # Must be set before a Q(Core)Application is created
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(list(argv))

    # Optional file path to open passed as first CLI argument
    start_path = Path(argv[1]) if len(argv) > 1 else None

    # --- Splash + bootstrapping (best-effort; cleanly falls back if not present) ---
    splash = None
    try:
        from pymd.app_bootstrapper import AppBootstrapper  # type: ignore
        from pymd.services.ui.splash_screen import SplashScreen  # type: ignore

        image_path = Path(__file__).resolve().parent / "assets" / "splash.png"
        splash = SplashScreen(
            image_path=image_path if image_path.exists() else None,
            app_title=APP_NAME,
        )
        splash.show()
        app.processEvents()

        bootstrapper = AppBootstrapper(progress=splash)

        def _make_container() -> Container:
            return Container.default()

        # Build container and window via bootstrapper; pass start_path into container build.
        # Keep container construction inside the factory for test-friendly DI.
        result = bootstrapper.boot(
            container_factory=lambda: _make_container(),
        )

        # The bootstrapper returns an object-like result; we still need to open start_path.
        # We build the actual window from a fresh container so DI wiring remains consistent.
        # If your bootstrapper already builds the window, you can adjust it later to accept start_path.
        container = _make_container()
        win = container.build_main_window(start_path=start_path, app_title=APP_NAME)
        win.show()

        if splash is not None:
            splash.close()

        return app.exec()

    except Exception:
        # Fallback to original behavior if splash/bootstrap modules aren’t available yet
        if splash is not None:
            try:
                splash.close()
            except Exception:
                pass

        container = Container.default()
        win = container.build_main_window(start_path=start_path, app_title=APP_NAME)
        win.show()
        return app.exec()
