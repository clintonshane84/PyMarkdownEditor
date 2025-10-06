from pymd.domain.models import Document


def test_document_defaults():
    d = Document(path=None, text="")
    assert d.path is None
    assert d.text == ""
    assert d.modified is False


def test_document_mutation(tmp_path):
    p = tmp_path / "x.md"
    d = Document(path=p, text="hi", modified=True)
    assert d.path == p
    assert d.text == "hi"
    assert d.modified is True
