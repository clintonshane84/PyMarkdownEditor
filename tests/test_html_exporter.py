import pytest

from pymd.services.exporters.html_exporter import HtmlExporter


def test_html_exporter_writes_file(tmp_path):
    exp = HtmlExporter()
    out = tmp_path / "out.html"
    exp.export("<html>ok</html>", out)
    assert out.read_text(encoding="utf-8") == "<html>ok</html>"


def test_html_exporter_permission_error(monkeypatch, tmp_path):
    exp = HtmlExporter()
    out = tmp_path / "out.html"

    # safer target: the bound method on the class used by Path instances
    monkeypatch.setattr(
        "pathlib.Path.write_text",
        lambda *a, **k: (_ for _ in ()).throw(PermissionError("nope")),
    )
    with pytest.raises(PermissionError):
        exp.export("<html>ok</html>", out)
