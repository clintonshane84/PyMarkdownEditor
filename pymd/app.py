from __future__ import annotations
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from pymd.di.container import Container
from pymd.ui.main_window import MainWindow
from pymd.utils.constants import APP_ORG, APP_NAME


def run_app(argv: list[str]) -> int:
    """Bootstraps Qt, builds dependencies, and launches the main window."""
    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(argv)

    container = Container()

    start_path = Path(argv[1]) if len(argv) > 1 else None
    win = MainWindow(
        renderer=container.renderer,
        file_service=container.file_service,
        settings=container.settings_service,
        start_path=start_path,
        app_title=APP_NAME,
    )
    win.show()
    return app.exec()
