from __future__ import annotations
import markdown

from pymd.domain.interfaces import IMarkdownRenderer
from pymd.utils.constants import CSS_PREVIEW, HTML_TEMPLATE


class MarkdownRenderer(IMarkdownRenderer):
    """Single responsibility: convert Markdown text to HTML using python-markdown."""

    def to_html(self, markdown_text: str) -> str:
        body = markdown.markdown(
            markdown_text,
            extensions=[
                "extra",
                "fenced_code",
                "codehilite",
                "toc",
                "sane_lists",
                "smarty",
            ],
            extension_configs={"codehilite": {"guess_lang": True, "noclasses": True}},
            output_format="html5",
        )
        return HTML_TEMPLATE.format(css=CSS_PREVIEW, body=body)
