import pytest

from pymd.services.exporters.pdf_exporter import PdfExporter


@pytest.mark.usefixtures("qapp")
def test_pdf_exporter_success(tmp_path):
    exp = PdfExporter()
    out = tmp_path / "out.pdf"
    exp.export("<html><body><h1>Test</h1></body></html>", out)
    # QPrinter writes a valid PDF; at least ensure non-empty file exists
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.usefixtures("qapp")
def test_pdf_exporter_raises_on_print_error(monkeypatch, tmp_path):
    # Force QTextDocument.print to raise
    from PyQt6.QtGui import QTextDocument

    def boom(self, _printer):
        raise RuntimeError("print fail")

    monkeypatch.setattr(QTextDocument, "print", boom, raising=True)

    exp = PdfExporter()
    out = tmp_path / "out.pdf"
    with pytest.raises(RuntimeError):
        exp.export("<html>bad</html>", out)
