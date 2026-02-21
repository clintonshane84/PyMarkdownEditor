from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from pymd.di.container import Container
from pymd.utils.constants import APP_NAME, APP_ORG


def _resource_path(rel: str) -> Path:
    """
    Resolve resource path in dev and PyInstaller.

    Dev layout:
      <repo>/assets/...

    PyInstaller:
      sys._MEIPASS/assets/...
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / rel  # type: ignore[arg-type]

    # repo root = parent of the "pymd" package folder
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / rel


def run_app(argv: Sequence[str]) -> int:
    # Qt global attribute (required for some WebEngine/OpenGL scenarios)
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    # App identity (QSettings namespace, etc.)
    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(list(argv))

    start_path = Path(argv[1]) if len(argv) > 1 else None

    splash = None
    try:
        # Imported inside try so fallback path works even if these imports fail
        from pymd.app_bootstrapper import AppBootstrapper  # type: ignore
        from pymd.services.ui.splash_screen import SplashScreen  # type: ignore

        image_path = _resource_path("assets/splash.png")
        splash = SplashScreen(
            image_path=image_path,  # SplashScreen will report if missing/unloadable
            app_title=APP_NAME,
        )
        splash.show()
        app.processEvents()

        bootstrapper = AppBootstrapper(progress=splash)

        # Create container once (so the same DI graph is used for boot + runtime)
        container: Container = Container.default()

        # Boot sequence (includes plugin_manager.reload() best-effort inside bootstrapper)
        result = bootstrapper.boot(container_factory=lambda: container)

        # Window returned by bootstrapper
        win = result.window  # type: ignore[attr-defined]

        # Optional: open a file post-startup if the window supports it
        try:
            if start_path is not None and hasattr(win, "_open_path"):
                win._open_path(start_path)  # type: ignore[attr-defined]
        except Exception:
            pass

        win.show()

        # Post-show plugin hook (safe next tick)
        try:
            pm = getattr(container, "plugin_manager", None)
            if pm is not None and hasattr(pm, "on_app_ready"):
                QTimer.singleShot(0, pm.on_app_ready)  # type: ignore[attr-defined]
        except Exception:
            pass

        if splash is not None:
            splash.close()

        return app.exec()

    except Exception:
        # Fallback: no splash/bootstrapper, or boot failed. Still start the app.
        if splash is not None:
            try:
                splash.close()
            except Exception:
                pass

        container = Container.default()
        win = container.build_main_window(start_path=start_path, app_title=APP_NAME)
        win.show()
        return app.exec()
