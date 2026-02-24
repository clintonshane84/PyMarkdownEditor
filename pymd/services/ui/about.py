from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Keep AboutDialog UI-only; configuration/version is injected (DIP).
try:
    # Your new “app config” protocol that includes IniConfigService methods + get_version()
    from pymd.domain.interfaces_config import IAppConfig  # type: ignore
except Exception:  # pragma: no cover
    IAppConfig = object  # type: ignore[misc]


def _asset_path(*parts: str) -> str:
    """
    Resolve an asset path that works both:
      - in source checkout (relative ./assets)
      - in PyInstaller builds (sys._MEIPASS)

    Repo layout:
      pymd/services/ui/about.py -> parents[3] == project root
      so <root>/assets/... is correct.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))  # type: ignore[attr-defined]
    return str(base.joinpath("assets", *parts))


class AboutDialog(QDialog):
    """
    About dialog.

    Responsibilities:
      - display app name
      - display semantic version (injected via config)
      - display splash image (assets/splash.png) if present
    """

    def __init__(self, _editor=None, parent=None, *, config: IAppConfig | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setModal(False)

        self._config = config

        # Widgets
        self.close_btn = QPushButton("OK")

        # Splash image
        splash_label = QLabel(self)
        splash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        splash_path = _asset_path("splash.png")
        pix = QPixmap(splash_path)
        if not pix.isNull():
            splash_label.setPixmap(
                pix.scaled(
                    420,
                    420,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            splash_label.setText("(splash.png missing)")

        # Text
        name_label = QLabel("<b>PyMarkdown Editor</b>")

        version = "0.0.0"
        try:
            # Contract: AppConfig.get_version() reads <root>/version (e.g. v1.0.5) and normalizes.
            if hasattr(self._config, "get_version"):
                version = str(self._config.get_version())  # type: ignore[attr-defined]
            else:
                # Backward-compatible fallback if only IniConfigService-like API is provided.
                version = str(getattr(self._config, "app_version", lambda: "0.0.0")())
        except Exception:
            version = "0.0.0"

        version_label = QLabel(f"Version {version}")
        version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Layouts
        form = QGridLayout()
        form.addWidget(name_label, 0, 0)
        form.addWidget(version_label, 1, 0)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        root = QVBoxLayout(self)
        root.addWidget(splash_label)
        root.addSpacing(8)
        root.addLayout(form)
        root.addLayout(buttons)

        # Signals
        self.close_btn.clicked.connect(self.close)
