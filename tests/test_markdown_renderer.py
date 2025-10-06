from pymd.services.markdown_renderer import MarkdownRenderer

def test_renderer_basic_html(renderer: MarkdownRenderer):
    html = renderer.to_html("# Title\n\nSome **bold** text.")
    # <h1 id="title">Title</h1> (toc extension adds id)
    assert "<h1" in html and "Title" in html
    assert "<strong>" in html
    # our template wraps body and includes CSS <style>
    assert html.lower().startswith("<!doctype html")
    assert "<style>" in html

def test_renderer_code_block(renderer: MarkdownRenderer):
    md = "```python\nprint('x')\n```"
    html = renderer.to_html(md)
    # codehilite may wrap as <div class="codehilite"><pre><code>...
    assert ("<pre" in html or "<code" in html) and "print" in html
