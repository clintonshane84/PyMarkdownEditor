"""Domain layer: interfaces and simple models (dataclasses)."""

from .interfaces import IExporter, IFileService, IMarkdownRenderer, ISettingsService
from .models import Document

__all__ = [
    "IMarkdownRenderer",
    "IFileService",
    "ISettingsService",
    "IExporter",
    "Document",
]
