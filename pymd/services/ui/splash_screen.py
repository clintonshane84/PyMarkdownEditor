from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QHBoxLayout, QWidget


class SplashScreen(QWidget):
    """
    Simple splash window:
      - image
      - status text
      - centered progress bar

    SRP: display only. No app boot logic inside.
    """

    def __init__(self, *, image_path: Path | None = None, app_title: str = "PyMarkdownEditor") -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)

        # Transparent backgrounds can hide “white” assets depending on compositor/theme.
        # Prefer a styled background for reliability.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            """
            SplashScreen {
                background-color: #1e1e1e;
                border-radius: 14px;
            }
            QLabel { color: white; }
            """
        )

        self.setWindowTitle(app_title)

        self._img = QLabel(self)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setMinimumSize(620, 280)  # ensure layout reserves space
        self._img.setText("")  # avoid placeholder text overlapping

        self._status = QLabel("Starting…", self)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bar = QProgressBar(self)
        self._bar.setTextVisible(False)
        self._bar.setMinimum(0)
        self._bar.setMaximum(0)
        self._bar.setFixedWidth(260)
        self._bar.setFixedHeight(14)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        root.addStretch(1)
        root.addWidget(self._img, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status, alignment=Qt.AlignmentFlag.AlignCenter)

        bar_row = QHBoxLayout()
        bar_row.addStretch(1)
        bar_row.addWidget(self._bar)
        bar_row.addStretch(1)
        root.addLayout(bar_row)
        root.addStretch(1)

        if image_path is not None:
            self.set_image(image_path)

        self.resize(640, 360)

    def set_image(self, path: Path) -> None:
        if not path.exists():
            self._img.setText("Splash image not found")
            self._status.setText(str(path))
            return

        px = QPixmap(str(path))
        if px.isNull():
            # This is the big clue: image plugin/support issue.
            self._img.setText("Failed to load splash image")
            self._status.setText(f"Qt could not load: {path.name}")
            return

        self._img.setPixmap(
            px.scaled(
                620,
                280,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_progress(self, *, value: int | None = None, maximum: int | None = None) -> None:
        if maximum is None:
            self._bar.setMaximum(0)
            return
        self._bar.setMaximum(maximum)
        if value is not None:
            self._bar.setValue(value)
