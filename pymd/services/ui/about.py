# pymd/services/ui/about.py
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# Keep this tiny and self-contained. No link-creation APIs here.
class AboutDialog(QDialog):
    def __init__(self, _editor=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setModal(False)

        # Widgets
        self.close_btn = QPushButton("OK")

        # Static text; if you have a config/version provider, format it in MainWindow before showing
        name_label = QLabel("PyMarkdown Editor")
        version_label = QLabel("Version {version} (build {commit}, {build_date})")

        # Layouts
        form = QGridLayout()
        form.addWidget(name_label, 0, 0)
        form.addWidget(version_label, 1, 0)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(buttons)

        # Signals
        self.close_btn.clicked.connect(self.close)
