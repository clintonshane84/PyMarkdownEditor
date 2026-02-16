from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class FloatingTimerWindow(QWidget):
    """Small always-on-top window for session countdown control."""

    pause_resume_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Focus Timer")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(240)

        self.time_label = QLabel("50:00", self)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(
            "font-size: 34px; font-weight: 700; padding: 10px; border-radius: 10px;"
        )

        self.pause_btn = QPushButton("Pause", self)
        self.stop_btn = QPushButton("Stop", self)

        root = QVBoxLayout(self)
        root.addWidget(self.time_label)
        root.addWidget(self.pause_btn)
        root.addWidget(self.stop_btn)

        self.pause_btn.clicked.connect(self.pause_resume_clicked.emit)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.set_color_state("green")

    def set_countdown(self, seconds: int) -> None:
        mins, sec = divmod(max(0, seconds), 60)
        self.time_label.setText(f"{mins:02d}:{sec:02d}")

    def set_paused(self, paused: bool) -> None:
        self.pause_btn.setText("Resume" if paused else "Pause")

    def set_color_state(self, level: str) -> None:
        palette = {
            "green": ("#0f3d28", "#9ff7c7"),
            "amber": ("#4a3609", "#ffd483"),
            "red": ("#4a1111", "#ff9f9f"),
        }
        bg, fg = palette.get(level, palette["green"])
        self.time_label.setStyleSheet(
            "font-size: 34px; font-weight: 700; padding: 10px; "
            f"border-radius: 10px; background: {bg}; color: {fg};"
        )
