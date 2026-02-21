from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from pymd.di.container import Container
from pymd.utils.constants import APP_NAME, APP_ORG


def _resource_path(rel: str) -> Path:
    """
    Resolve resource path in dev and PyInstaller.

    Dev layout (your case):
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
    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(list(argv))

    start_path = Path(argv[1]) if len(argv) > 1 else None

    splash = None
    try:
        from pymd.app_bootstrapper import AppBootstrapper  # type: ignore
        from pymd.services.ui.splash_screen import SplashScreen  # type: ignore

        image_path = _resource_path("assets/splash.png")
        splash = SplashScreen(
            image_path=image_path,  # always pass; SplashScreen will report if missing/unloadable
            app_title=APP_NAME,
        )
        splash.show()
        app.processEvents()

        bootstrapper = AppBootstrapper(progress=splash)

        def _make_container() -> Container:
            return Container.default()

        # bootstrap (your 2s delay can be inside bootstrapper)
        container = _make_container()
        result = bootstrapper.boot(container_factory=lambda: container)

        # Use the window returned by the bootstrapper if it provides it
        win = result.window  # type: ignore[attr-defined]
        # If your bootstrapper builds without start_path, keep your existing behavior:
        # win = container.build_main_window(start_path=start_path, app_title=APP_NAME)

        # Optional: if win supports opening a file post-startup:
        try:
            if start_path is not None and hasattr(win, "_open_path"):
                win._open_path(start_path)  # type: ignore[attr-defined]
        except Exception:
            pass

        win.show()

        if splash is not None:
            splash.close()

        return app.exec()

    except Exception:
        if splash is not None:
            try:
                splash.close()
            except Exception:
                pass

        container = Container.default()
        win = container.build_main_window(start_path=start_path, app_title=APP_NAME)
        win.show()
        return app.exec()
