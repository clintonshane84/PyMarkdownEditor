from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QByteArray, QObject, pyqtSignal
from PyQt6.QtTest import QSignalSpy

import pymd.plugins.pip_installer as pip_mod
from pymd.plugins.pip_installer import PipResult, QtPipInstaller

# ----------------------------
# Fakes
# ----------------------------


@dataclass
class _FakeEnv:
    data: dict[str, str]

    def insert(self, k: str, v: str) -> None:
        self.data[str(k)] = str(v)


class FakeQProcess(QObject):
    """
    Deterministic QProcess stand-in.

    - start() does NOT auto-emit.
    - test calls play_script() explicitly.
    """

    readyReadStandardOutput = pyqtSignal()
    readyReadStandardError = pyqtSignal()
    finished = pyqtSignal(int, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._program: str | None = None
        self._args: list[str] = []
        self._env = _FakeEnv({})
        self._stdout_buf: QByteArray = QByteArray()
        self._stderr_buf: QByteArray = QByteArray()
        self.kill_called = False
        self.started = False

        # script: [("stdout"|"stderr"|"finish", payload)]
        self.script: list[tuple[str, Any]] = []

    # --- API used by QtPipInstaller ---
    def setProgram(self, program: str) -> None:
        self._program = program

    def setArguments(self, args: list[str]) -> None:
        self._args = list(args)

    def processEnvironment(self) -> _FakeEnv:
        return self._env

    def setProcessEnvironment(self, env: _FakeEnv) -> None:
        self._env = env

    def start(self) -> None:
        self.started = True

    def kill(self) -> None:
        self.kill_called = True

    def readAllStandardOutput(self) -> QByteArray:
        return self._stdout_buf

    def readAllStandardError(self) -> QByteArray:
        return self._stderr_buf

    # --- test helper ---
    def play_script(self) -> None:
        for kind, payload in self.script:
            if kind == "stdout":
                self._stdout_buf = QByteArray(str(payload).encode("utf-8"))
                self.readyReadStandardOutput.emit()
            elif kind == "stderr":
                self._stderr_buf = QByteArray(str(payload).encode("utf-8"))
                self.readyReadStandardError.emit()
            elif kind == "finish":
                self.finished.emit(int(payload), object())


# ----------------------------
# Tests
# ----------------------------


def test_pip_install_success_emits_output_and_finished_ok(qapp, monkeypatch):
    created: dict[str, FakeQProcess] = {}

    def _factory(parent: QObject) -> FakeQProcess:
        p = FakeQProcess(parent)
        p.script = [
            ("stdout", "Collecting foo\n"),
            ("stderr", "WARNING: something\n"),
            ("finish", 0),
        ]
        created["proc"] = p
        return p

    monkeypatch.setattr(pip_mod, "QProcess", _factory)

    inst = QtPipInstaller()
    spy_out = QSignalSpy(inst.output)
    spy_fin = QSignalSpy(inst.finished)

    inst.install("foo")

    # deterministically drive the fake process
    proc = created["proc"]
    proc.play_script()
    qapp.processEvents()

    assert len(spy_fin) == 1, "finished signal not emitted"

    # Verify wiring
    assert proc._program is not None
    assert proc._args[:3] == ["-m", "pip", "install"]
    assert proc._args[3] == "foo"
    assert proc._env.data.get("PYTHONIOENCODING") == "utf-8"

    # Output streamed (combined)
    out_lines = [args[0] for args in spy_out]  # each entry is (str,)
    assert any("Collecting foo" in s for s in out_lines)
    assert any("WARNING" in s for s in out_lines)

    # Finished result
    result_obj = spy_fin[0][0]
    assert isinstance(result_obj, PipResult)
    assert result_obj.ok is True
    assert result_obj.exit_code == 0
    assert "Collecting foo" in result_obj.stdout
    assert "WARNING" in result_obj.stderr


def test_pip_uninstall_fail_and_cancel_kills_process(qapp, monkeypatch):
    created: dict[str, FakeQProcess] = {}

    def _factory(parent: QObject) -> FakeQProcess:
        p = FakeQProcess(parent)
        created["proc"] = p
        return p

    monkeypatch.setattr(pip_mod, "QProcess", _factory)

    inst = QtPipInstaller()
    spy_fin = QSignalSpy(inst.finished)

    # ---- Cancel path: do NOT finish yet ----
    inst.uninstall("nope")
    proc = created["proc"]
    assert proc.started is True

    inst.cancel()
    assert proc.kill_called is True
    assert inst._proc is None  # cleared

    # even if process tries to "finish" after cancel, should not crash
    proc.script = [("finish", 1)]
    proc.play_script()
    qapp.processEvents()

    # ---- Fail path deterministically ----
    inst.uninstall("nope")
    proc2 = created["proc"]
    proc2.script = [
        ("stderr", "ERROR: not installed\n"),
        ("finish", 1),
    ]
    proc2.play_script()
    qapp.processEvents()

    assert len(spy_fin) >= 1, "finished signal not emitted on fail path"

    result_obj = spy_fin[-1][0]
    assert isinstance(result_obj, PipResult)
    assert result_obj.ok is False
    assert result_obj.exit_code == 1
    assert "ERROR: not installed" in result_obj.stderr

    # Verify uninstall args include "-y"
    assert proc2._args[:4] == ["-m", "pip", "uninstall", "-y"]
    assert proc2._args[4] == "nope"
