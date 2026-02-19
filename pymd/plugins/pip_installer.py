from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Protocol

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


@dataclass(frozen=True)
class PipResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str


class IPipInstaller(Protocol):
    def install(self, package: str) -> None: ...
    def uninstall(self, package: str) -> None: ...
    def cancel(self) -> None: ...


class QtPipInstaller(QObject):
    """
    Runs `python -m pip install/uninstall ...` in the background via QProcess.
    Emits streaming output for a progress dialog.
    """

    output = pyqtSignal(str)           # combined stdout/stderr lines
    finished = pyqtSignal(object)      # PipResult

    def __init__(self) -> None:
        super().__init__()
        self._proc: QProcess | None = None
        self._stdout: list[str] = []
        self._stderr: list[str] = []

    def _start(self, args: list[str]) -> None:
        self.cancel()

        proc = QProcess(self)
        self._proc = proc
        self._stdout.clear()
        self._stderr.clear()

        proc.setProgram(sys.executable)
        proc.setArguments(["-m", "pip", *args])

        # Ensure UTF-8 output best-effort
        env = proc.processEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        proc.setProcessEnvironment(env)

        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.readyReadStandardError.connect(self._on_stderr)
        proc.finished.connect(self._on_finished)  # type: ignore[arg-type]

        proc.start()

    def install(self, package: str) -> None:
        # Use -q? No: we want output for the progress dialog.
        self._start(["install", package])

    def uninstall(self, package: str) -> None:
        # -y avoids interactive prompts
        self._start(["uninstall", "-y", package])

    def cancel(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def _on_stdout(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout.append(data)
        self.output.emit(data)

    def _on_stderr(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr.append(data)
        self.output.emit(data)

    def _on_finished(self, exit_code: int, _status) -> None:
        out = "".join(self._stdout)
        err = "".join(self._stderr)
        ok = exit_code == 0
        self.finished.emit(PipResult(ok=ok, exit_code=exit_code, stdout=out, stderr=err))
        self._proc = None