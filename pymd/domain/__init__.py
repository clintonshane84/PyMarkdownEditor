"""Domain layer: interfaces and simple models (dataclasses)."""

from .interfaces import IMarkdownRenderer, IFileService, ISettingsService, IExporter
from .models import Document

__all__ = [
    "IMarkdownRenderer",
    "IFileService",
    "ISettingsService",
    "IExporter",
    "Document",
]
