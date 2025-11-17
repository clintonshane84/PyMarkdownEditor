# tests/test_markdown_renderer.py
import pytest

from pymd.services.markdown_renderer import MarkdownRenderer


@pytest.fixture
def renderer_mathjax() -> MarkdownRenderer:
    # Default engine is MathJax
    return MarkdownRenderer()


@pytest.fixture
def renderer_katex() -> MarkdownRenderer:
    return MarkdownRenderer(math_engine="katex")


def test_renderer_basic_html(renderer_mathjax: MarkdownRenderer):
    html = renderer_mathjax.to_html("# Title\n\nSome **bold** text.")
    # <h1 ...>Title</h1> (toc may add id attrs)
    assert "<h1" in html and "Title" in html
    assert "<strong>" in html
    # Template + CSS present
    assert html.lower().startswith("<!doctype html")
    assert "<style>" in html


def test_renderer_code_block(renderer_mathjax: MarkdownRenderer):
    md = "```python\nprint('x')\n```"
    html = renderer_mathjax.to_html(md)
    # codehilite may wrap as <div class="codehilite"><pre><code>...
    assert ("<pre" in html or "<code" in html) and "print" in html


def _has_arithmatex_wrappers(s: str) -> bool:
    return ('class="arithmatex"' in s) or ("class='arithmatex'" in s)


def _has_inline_math_raw(s: str) -> bool:
    # tolerate either raw TeX delimiters or arithmatex wrapping
    return "$e^{i\\pi}+1=0$" in s or "e^{i\\pi}+1=0" in s


def _has_display_math_raw(s: str) -> bool:
    return "$$\n" in s or "\\[" in s or "\\]" in s


def test_inline_math_wrapping_or_raw_with_mathjax(renderer_mathjax: MarkdownRenderer):
    md = r"Euler: $e^{i\pi}+1=0$."
    html = renderer_mathjax.to_html(md)

    # Accept either arithmatex wrappers OR raw inline math text
    assert _has_arithmatex_wrappers(html) or _has_inline_math_raw(html)

    # MathJax assets should be present for default engine
    assert 'id="MathJax-script"' in html
    assert "tex-chtml.js" in html
    assert "window.MathJax" in html  # config block


def test_display_math_wrapping_or_raw_with_mathjax(renderer_mathjax: MarkdownRenderer):
    md = r"""
Here is display math:

$$
\int_a^b f(x)\,dx
$$
"""
    html = renderer_mathjax.to_html(md)
    # Accept either arithmatex <div> wrapper or raw $$…$$ delimiters
    assert ('<div class="arithmatex">' in html) or _has_display_math_raw(html)

    # MathJax config script should be present
    assert "window.MathJax" in html
    assert 'id="MathJax-script"' in html


def test_katex_assets_and_wrapping_or_raw(renderer_katex: MarkdownRenderer):
    md = r"Inline: $a^2 + b^2 = c^2$"
    html = renderer_katex.to_html(md)

    # Accept arithmatex OR raw inline TeX (KaTeX auto-render can scan raw)
    assert _has_arithmatex_wrappers(html) or "$a^2 + b^2 = c^2$" in html or "a^2 + b^2 = c^2" in html

    # KaTeX assets
    assert "katex.min.css" in html
    assert "katex.min.js" in html
    assert "auto-render.min.js" in html
    assert "renderMathInElement" in html

    # MathJax assets should NOT be present for KaTeX
    assert 'id="MathJax-script"' not in html
    assert "tex-chtml.js" not in html


def test_math_not_processed_inside_code_blocks(renderer_mathjax: MarkdownRenderer):
    # Dollars inside code fences should NOT become arithmatex
    md = r"""```python
s = "$x$"
print(s)
```"""
    html = renderer_mathjax.to_html(md)
    # No arithmatex should appear because all $...$ was inside code fence
    assert "arithmatex" not in html

    # Code should still render as code/pre
    assert ("<pre" in html or "<code" in html) and "$x$" in html


def test_headers_and_toc_still_work(renderer_mathjax: MarkdownRenderer):
    md = "# Heading 1\n\n## Heading 2"
    html = renderer_mathjax.to_html(md)
    assert "<h1" in html and "Heading 1" in html
    assert "<h2" in html and "Heading 2" in html
    # toc extension typically adds id attributes; don't rely on exact format
    assert "id=" in html or "name=" in html
