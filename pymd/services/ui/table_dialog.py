from __future__ import annotations

from typing import Protocol

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

# -------------------------
# Ports / Model / Service
# -------------------------

class EditorPort(Protocol):
    def textCursor(self) -> QTextCursor: ...
    def setTextCursor(self, c: QTextCursor) -> None: ...
    def document(self): ...


class TableDialog(QDialog):
    """Dialog for inserting markdown tables with configurable rows, columns, and alignment."""

    def __init__(self, editor: EditorPort, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert Table")
        self.setModal(True)
        self._ed = editor

        # Widgets
        self.rows_spin = QSpinBox()
        self.rows_spin.setMinimum(1)
        self.rows_spin.setMaximum(50)
        self.rows_spin.setValue(3)

        self.cols_spin = QSpinBox()
        self.cols_spin.setMinimum(1)
        self.cols_spin.setMaximum(20)
        self.cols_spin.setValue(3)

        self.include_header = QCheckBox("Include header row")
        self.include_header.setChecked(True)

        # Alignment radio buttons
        self.align_left = QRadioButton("Left")
        self.align_center = QRadioButton("Center")
        self.align_right = QRadioButton("Right")
        self.align_left.setChecked(True)

        self.align_group = QButtonGroup()
        self.align_group.addButton(self.align_left)
        self.align_group.addButton(self.align_center)
        self.align_group.addButton(self.align_right)

        self.insert_btn = QPushButton("Insert Table")
        self.cancel_btn = QPushButton("Cancel")

        # Layout
        form = QGridLayout()
        form.addWidget(QLabel("Rows:"), 0, 0)
        form.addWidget(self.rows_spin, 0, 1)
        form.addWidget(QLabel("Columns:"), 1, 0)
        form.addWidget(self.cols_spin, 1, 1)
        form.addWidget(self.include_header, 2, 0, 1, 2)

        # Alignment section
        align_layout = QVBoxLayout()
        align_layout.addWidget(QLabel("Column Alignment:"))
        align_layout.addWidget(self.align_left)
        align_layout.addWidget(self.align_center)
        align_layout.addWidget(self.align_right)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.insert_btn)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addLayout(align_layout)
        root.addLayout(buttons)

        # Signals
        self.insert_btn.clicked.connect(self._on_insert)
        self.cancel_btn.clicked.connect(self.reject)

        # Set default button
        self.insert_btn.setDefault(True)
        self.insert_btn.setFocus()

    def _on_insert(self) -> None:
        """Generate and insert the markdown table."""
        table_md = self._generate_table()
        self._insert_table(table_md)
        self.accept()

    def _generate_table(self) -> str:
        """Generate markdown table string based on dialog settings."""
        rows = self.rows_spin.value()
        cols = self.cols_spin.value()
        include_header = self.include_header.isChecked()

        # Determine alignment marker
        if self.align_center.isChecked():
            sep = ":---:"
        elif self.align_right.isChecked():
            sep = "---:"
        else:  # left or default
            sep = "---"

        lines = []

        # Header row
        if include_header:
            header_cells = [f"Column {i + 1}" for i in range(cols)]
            lines.append("| " + " | ".join(header_cells) + " |")
            # Separator row
            lines.append("| " + " | ".join([sep] * cols) + " |")
            # Adjust remaining rows (header already added)
            data_rows = rows - 1 if rows > 1 else 0
        else:
            # No header, so separator still needed but with generic labels
            lines.append("| " + " | ".join([" "] * cols) + " |")
            lines.append("| " + " | ".join([sep] * cols) + " |")
            data_rows = rows - 1 if rows > 0 else 0

        # Data rows (empty cells)
        for _ in range(data_rows):
            lines.append("| " + " | ".join([" "] * cols) + " |")

        return "\n".join(lines)

    def _insert_table(self, table_md: str) -> None:
        """Insert the table markdown at the current cursor position."""
        cur = self._ed.textCursor()

        # Ensure we're on a new line
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        if not cur.atBlockStart():
            cur.insertText("\n")

        # Insert the table
        start_pos = cur.position()
        cur.insertText(table_md)
        cur.insertText("\n")

        # Position cursor at the first cell (after "| ")
        if self.include_header.isChecked():
            # First header cell
            cur.setPosition(start_pos + 2)  # After "| "
        else:
            # First data cell (skip the empty header and separator)
            first_newline = table_md.find("\n")
            second_newline = table_md.find("\n", first_newline + 1)
            cur.setPosition(start_pos + second_newline + 3)  # After second "| "

        self._ed.setTextCursor(cur)

    def show_table_dialog(self) -> int:
        """Public API used by MainWindow wiring."""
        return self.exec()
