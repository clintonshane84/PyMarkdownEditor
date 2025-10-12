from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from pymd.di.container import Container
from pymd.utils.constants import APP_NAME, APP_ORG


def run_app(argv: Sequence[str]) -> int:
    """
    Bootstraps Qt, composes the application via the DI container,
    and launches the main window.
    """
    QApplication.setOrganizationName(APP_ORG)
    QApplication.setApplicationName(APP_NAME)
    app = QApplication(list(argv))

    # Build the default container (renderer, files, settings, dialogs, messages, etc.)
    container = Container.default()

    # Optional file path to open passed as first CLI argument
    start_path = Path(argv[1]) if len(argv) > 1 else None

    # Ask the container to build a fully-wired MainWindow (with presenter attached)
    win = container.build_main_window(start_path=start_path, app_title=APP_NAME)
    win.show()

    return app.exec()
