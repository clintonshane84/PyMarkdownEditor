from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    path: Path | None
    text: str
    modified: bool = False
