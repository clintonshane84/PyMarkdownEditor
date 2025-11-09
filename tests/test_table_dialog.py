from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit

from pymd.services.ui.table_dialog import TableDialog


@pytest.fixture()
def editor(qapp) -> QTextEdit:
    """Create a QTextEdit instance for testing."""
    edit = QTextEdit()
    edit.show()
    qapp.processEvents()
    return edit


@pytest.fixture()
def dialog(qapp, editor: QTextEdit) -> TableDialog:
    """Create a TableDialog instance for testing."""
    dlg = TableDialog(editor)
    return dlg


def test_dialog_initialization(dialog: TableDialog):
    """Test that the dialog initializes with correct default values."""
    assert dialog.windowTitle() == "Insert Table"
    assert dialog.rows_spin.value() == 3
    assert dialog.cols_spin.value() == 3
    assert dialog.include_header.isChecked() is True
    assert dialog.align_left.isChecked() is True


def test_dialog_min_max_values(dialog: TableDialog):
    """Test that spinboxes have correct min/max values."""
    assert dialog.rows_spin.minimum() == 1
    assert dialog.rows_spin.maximum() == 50
    assert dialog.cols_spin.minimum() == 1
    assert dialog.cols_spin.maximum() == 20


def test_generate_table_with_header_left_align(dialog: TableDialog):
    """Test table generation with header row and left alignment."""
    dialog.rows_spin.setValue(3)
    dialog.cols_spin.setValue(3)
    dialog.include_header.setChecked(True)
    dialog.align_left.setChecked(True)

    table = dialog._generate_table()

    expected = (
        "| Column 1 | Column 2 | Column 3 |\n"
        "| --- | --- | --- |\n"
        "|   |   |   |\n"
        "|   |   |   |"
    )
    assert table == expected


def test_generate_table_with_header_center_align(dialog: TableDialog):
    """Test table generation with header row and center alignment."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(True)
    dialog.align_center.setChecked(True)

    table = dialog._generate_table()

    expected = (
        "| Column 1 | Column 2 |\n"
        "| :---: | :---: |\n"
        "|   |   |"
    )
    assert table == expected


def test_generate_table_with_header_right_align(dialog: TableDialog):
    """Test table generation with header row and right alignment."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(True)
    dialog.align_right.setChecked(True)

    table = dialog._generate_table()

    expected = (
        "| Column 1 | Column 2 |\n"
        "| ---: | ---: |\n"
        "|   |   |"
    )
    assert table == expected


def test_generate_table_without_header(dialog: TableDialog):
    """Test table generation without header row."""
    dialog.rows_spin.setValue(3)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(False)

    table = dialog._generate_table()

    expected = (
        "|   |   |\n"
        "| --- | --- |\n"
        "|   |   |\n"
        "|   |   |"
    )
    assert table == expected


def test_generate_table_minimum_size(dialog: TableDialog):
    """Test table generation with minimum rows and columns."""
    dialog.rows_spin.setValue(1)
    dialog.cols_spin.setValue(1)
    dialog.include_header.setChecked(True)

    table = dialog._generate_table()

    expected = (
        "| Column 1 |\n"
        "| --- |"
    )
    assert table == expected


def test_generate_table_large_size(dialog: TableDialog):
    """Test table generation with many columns."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(5)
    dialog.include_header.setChecked(True)

    table = dialog._generate_table()

    assert "| Column 1 | Column 2 | Column 3 | Column 4 | Column 5 |" in table
    assert "| --- | --- | --- | --- | --- |" in table
    # Should have 1 data row (total 2 rows - 1 header)
    assert table.count("\n") == 2


def test_insert_table_into_empty_editor(qapp, editor: QTextEdit, dialog: TableDialog):
    """Test inserting a table into an empty editor."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(True)

    table = dialog._generate_table()
    dialog._insert_table(table)
    qapp.processEvents()

    content = editor.toPlainText()
    assert "| Column 1 | Column 2 |" in content
    assert "| --- | --- |" in content

    # Cursor should be positioned at first cell (after "| ")
    cursor = editor.textCursor()
    assert cursor.position() > 0


def test_insert_table_into_editor_with_content(qapp, editor: QTextEdit, dialog: TableDialog):
    """Test inserting a table into an editor that already has content."""
    editor.setPlainText("# Existing Header\n\nSome text here.")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    qapp.processEvents()

    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(True)

    table = dialog._generate_table()
    dialog._insert_table(table)
    qapp.processEvents()

    content = editor.toPlainText()
    assert "# Existing Header" in content
    assert "Some text here." in content
    assert "| Column 1 | Column 2 |" in content
    assert "| --- | --- |" in content


def test_insert_table_cursor_positioning_with_header(qapp, editor: QTextEdit, dialog: TableDialog):
    """Test that cursor is positioned correctly after insertion with header."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(True)

    table = dialog._generate_table()
    dialog._insert_table(table)
    qapp.processEvents()

    cursor = editor.textCursor()
    # Cursor should be in the first header cell
    # Get text before cursor
    cursor.movePosition(cursor.MoveOperation.StartOfBlock)
    cursor.movePosition(cursor.MoveOperation.EndOfBlock, cursor.MoveMode.KeepAnchor)
    line = cursor.selectedText()

    # Should be in the first line of the table
    assert "Column 1" in line or "Column 2" in line


def test_insert_table_cursor_positioning_without_header(qapp, editor: QTextEdit, dialog: TableDialog):
    """Test that cursor is positioned correctly after insertion without header."""
    dialog.rows_spin.setValue(2)
    dialog.cols_spin.setValue(2)
    dialog.include_header.setChecked(False)

    table = dialog._generate_table()
    dialog._insert_table(table)
    qapp.processEvents()

    cursor = editor.textCursor()
    # Cursor should be in a data row (not the separator)
    assert cursor.position() > 0


def test_dialog_buttons_exist(dialog: TableDialog):
    """Test that dialog has Insert and Cancel buttons."""
    assert dialog.insert_btn is not None
    assert dialog.cancel_btn is not None
    assert dialog.insert_btn.text() == "Insert Table"
    assert dialog.cancel_btn.text() == "Cancel"


def test_alignment_radio_buttons_mutually_exclusive(dialog: TableDialog):
    """Test that alignment radio buttons are mutually exclusive."""
    dialog.align_left.setChecked(True)
    assert dialog.align_left.isChecked() is True
    assert dialog.align_center.isChecked() is False
    assert dialog.align_right.isChecked() is False

    dialog.align_center.setChecked(True)
    assert dialog.align_left.isChecked() is False
    assert dialog.align_center.isChecked() is True
    assert dialog.align_right.isChecked() is False

    dialog.align_right.setChecked(True)
    assert dialog.align_left.isChecked() is False
    assert dialog.align_center.isChecked() is False
    assert dialog.align_right.isChecked() is True
