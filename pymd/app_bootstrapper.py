from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from PyQt6.QtCore import QEventLoop, QTimer


class IStartupProgress(Protocol):
    def set_status(self, text: str) -> None: ...

    def set_progress(self, *, value: int | None = None, maximum: int | None = None) -> None: ...


@dataclass(frozen=True)
class BootstrapResult:
    window: object


class AppBootstrapper:
    """
    SRP: orchestrates startup steps and reports progress.

    Ownership rule:
      - Bootstrapper owns plugin reload for determinism.
      - MainWindow.attach_plugins() must NOT call reload.
    """

    def __init__(self, *, progress: IStartupProgress, delay_ms: int = 500) -> None:
        self._progress = progress
        self._delay_ms = delay_ms

    # ----------------------------- internal helpers -----------------------------

    def _intentional_delay(self) -> None:
        """
        Keeps Qt event loop responsive while enforcing a minimum splash duration.
        Avoids blocking the UI thread with time.sleep().
        """
        loop = QEventLoop()
        QTimer.singleShot(self._delay_ms, loop.quit)
        loop.exec()

    # ----------------------------- boot sequence -----------------------------

    def boot(self, *, container_factory: Callable[[], object]) -> BootstrapResult:
        # 1) Initial state
        self._progress.set_status("Initializing…")
        self._progress.set_progress(maximum=None)

        self._intentional_delay()

        # 2) Build container
        self._progress.set_status("Loading services…")
        container = container_factory()

        # 3) Build main window (this creates the AppAPI adapter inside MainWindow)
        self._progress.set_status("Building interface…")
        window = container.build_main_window()

        # 4) Load plugins (deterministic pre-show phase)
        self._progress.set_status("Loading plugins…")
        try:
            pm = getattr(container, "plugin_manager", None)
            if pm is not None:
                # Ensure API is set before reload.
                app_api = getattr(window, "_app_api", None)
                if app_api is not None and hasattr(pm, "set_api"):
                    try:
                        pm.set_api(app_api)  # type: ignore[attr-defined]
                    except Exception:
                        pass

                if hasattr(pm, "reload"):
                    try:
                        pm.reload()  # type: ignore[attr-defined]
                    except Exception:
                        pass
        except Exception:
            pass

        # 5) Finish
        self._progress.set_status("Ready")
        self._progress.set_progress(maximum=1, value=1)

        return BootstrapResult(window=window)
