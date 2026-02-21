from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

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
    Open/Closed: add steps later without changing splash/main window.
    """

    def __init__(self, *, progress: IStartupProgress, delay_ms: int = 500) -> None:
        self._progress = progress
        self._delay_ms = delay_ms  # intentional splash duration

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
        """
        container_factory: callable that returns a Container with build_main_window()
        We keep this injected so bootstrapping stays decoupled from DI details.
        """

        # 1️⃣ Initial state
        self._progress.set_status("Initializing…")
        self._progress.set_progress(maximum=None)  # indeterminate loader

        # Intentional 2s splash visibility
        self._intentional_delay()

        # 2️⃣ Build container
        self._progress.set_status("Loading services…")
        container = container_factory()

        # 3️⃣ Build main window
        self._progress.set_status("Building interface…")
        window = container.build_main_window()

        # 4️⃣ Load plugins
        self._progress.set_status("Loading plugins…")
        try:
            if hasattr(container, "plugin_manager"):
                container.plugin_manager.reload()  # type: ignore[attr-defined]
        except Exception:
            pass

        # 5️⃣ Finish
        self._progress.set_status("Ready")
        self._progress.set_progress(maximum=1, value=1)

        return BootstrapResult(window=window)
