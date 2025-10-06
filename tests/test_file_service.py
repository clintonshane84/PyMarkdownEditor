import pytest
from pymd.services.file_service import FileService


def test_file_service_read_write_atomic_success(tmp_path):
    fs = FileService()
    p = tmp_path / "a.md"
    fs.write_text_atomic(p, "hello")
    assert p.read_text(encoding="utf-8") == "hello"


def test_file_service_read_text_missing(tmp_path):
    fs = FileService()
    p = tmp_path / "missing.md"
    with pytest.raises(FileNotFoundError):
        fs.read_text(p)


def test_file_service_write_atomic_open_fail(monkeypatch, tmp_path):
    class FakeQSaveFile:
        def __init__(self, *_):
            pass

        def open(self, *_):
            return False

    fs = FileService()
    p = tmp_path / "x.md"
    monkeypatch.setattr(
        "pymd.services.file_service.QSaveFile", FakeQSaveFile, raising=True
    )
    with pytest.raises(IOError):
        fs.write_text_atomic(p, "data")


def test_file_service_write_atomic_commit_fail(monkeypatch, tmp_path):
    class FakeQSaveFile:
        def __init__(self, *_):
            self._data = b""

        def open(self, *_):
            return True

        def write(self, b):
            self._data += b

        def commit(self):
            return False

    fs = FileService()
    p = tmp_path / "x.md"
    monkeypatch.setattr(
        "pymd.services.file_service.QSaveFile", FakeQSaveFile, raising=True
    )
    with pytest.raises(IOError):
        fs.write_text_atomic(p, "data")
