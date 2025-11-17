# pymd/services/markdown_renderer.py
from __future__ import annotations

from typing import Literal

import markdown

from pymd.domain.interfaces import IMarkdownRenderer
from pymd.utils.constants import CSS_PREVIEW, HTML_TEMPLATE

MathEngine = Literal["mathjax", "katex"]


class MarkdownRenderer(IMarkdownRenderer):
    """
    Converts Markdown to HTML with optional LaTeX math support.

    Uses pymdownx.arithmatex to wrap inline ($...$) and display ($$...$$) math,
    and injects MathJax (default) or KaTeX scripts so a JS-capable preview can render it.
    """

    def __init__(self, math_engine: MathEngine = "mathjax") -> None:
        self.math_engine: MathEngine = math_engine

    def to_html(self, markdown_text: str) -> str:
        # Extensions for Markdown + math wrappers
        exts = [
            "extra",
            "fenced_code",
            "codehilite",
            "toc",
            "sane_lists",
            "smarty",
            "pymdownx.arithmatex",  # <-- math wrappers
        ]

        ext_cfg = {
            "codehilite": {"guess_lang": True, "noclasses": True},
            # 'generic=True' wraps math in <span class="arithmatex"> / <div class="arithmatex">
            # so the front-end renderer (MathJax/KaTeX) can process it.
            "pymdownx.arithmatex": {
                "generic": True,
                "inline_syntax": ["$", "$"],  # $...$
                "block_syntax": ["$$", "$$"],  # $$...$$
            },
        }

        body = markdown.markdown(
            markdown_text,
            extensions=exts,
            extension_configs=ext_cfg,
            output_format="html5",
        )

        # Inject CSS + math assets. We add math scripts *inside* the body so even if the
        # outer template is fixed, a JS-capable preview can still execute them.
        math_assets = self._math_assets(self.math_engine)

        # NOTE:
        # - If your HTML_TEMPLATE already has <head> injection points, you can place the
        #   CSS there. To keep this module drop-in, we concatenate CSS and scripts here.
        html = HTML_TEMPLATE.format(
            css=CSS_PREVIEW + math_assets["css"], body=body + math_assets["scripts"]
        )
        return html

    # -------------------- helpers --------------------

    def _math_assets(self, engine: MathEngine) -> dict[str, str]:
        if engine == "katex":
            # KaTeX (fast) – render client-side with auto-render # noqa: RUF003
            # CDN versions can be pinned if you prefer.
            katex_css = (
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css" '  # noqa: E501
                'integrity="sha384-wK3nQhH0cVZr7r8Y8sE0t4f2C7dYc8H3D8uQAu0QH3Tt/3jQ8b0EYYlq6QnZ6Z0v" crossorigin="anonymous">'  # noqa: E501
            )
            katex_js = """
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"
        integrity="sha384-B4s6f0U6d0qf9q0kY1n5i3bU8mQe9f3pTeHqLq5Nn5kQnG7s8oKp4zH2Q6JjQn6b"
        crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js"
        integrity="sha384-vZTG03ZVvbG5B6GJk8GgB4n8x4QzE8q5Z1sBfU+Ww2k7x0c6K7V3WfK8Q+z4i1sY"
        crossorigin="anonymous"></script>
<script>
document.addEventListener("DOMContentLoaded", function() {
  if (typeof renderMathInElement === "function") {
    renderMathInElement(document.body, {
      delimiters: [
        {left: "$$", right: "$$", display: true},
        {left: "$",  right: "$",  display: false},
        {left: "\\\\(", right: "\\\\)", display: false},
        {left: "\\\\[", right: "\\\\]", display: true}
      ],
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"]
    });
  }
});
</script>
"""
            return {"css": katex_css, "scripts": katex_js}

        # Default: MathJax v3
        # Configure inline and display delimiters, escape handling, and skip pre/code.
        mathjax_cfg = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
  }
};
</script>
"""
        mathjax_js = (
            '<script id="MathJax-script" async '
            'src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>'
        )
        return {"css": "", "scripts": mathjax_cfg + mathjax_js}
