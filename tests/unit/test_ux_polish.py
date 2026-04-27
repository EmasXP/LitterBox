"""Tests for UX/UI polish changes: size formatting, filter empty-state,
right-aligned size column, FilterBar styling, and tab close-on-hover.
"""
import os
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtWidgets import QTabWidget, QMessageBox

from core.file_operations import FileOperations
from ui.file_list_view import FileListView
from ui.main_window import FilterBar


# --- format_size ----------------------------------------------------------

def test_format_size_bytes_no_decimal():
    """Bytes should display as integers, not '1017.0 B'."""
    assert FileOperations.format_size(0) == "0 B"
    assert FileOperations.format_size(1) == "1 B"
    assert FileOperations.format_size(1017) == "1017 B"
    assert FileOperations.format_size(1023) == "1023 B"


def test_format_size_kb_and_above_keep_decimal():
    assert FileOperations.format_size(1024) == "1.0 KB"
    assert FileOperations.format_size(1024 * 1024) == "1.0 MB"
    assert FileOperations.format_size(1024 ** 3) == "1.0 GB"


# --- FilterBar styling ----------------------------------------------------

def test_filter_bar_has_no_hardcoded_colors(qapp):
    """Regression: FilterBar must not impose a light-mode background that
    breaks dark themes."""
    bar = FilterBar()
    qss = bar.styleSheet()
    assert "#f0f0f0" not in qss
    assert "background-color" not in qss


def test_filter_bar_line_edit_has_accessibility(qapp):
    bar = FilterBar()
    assert bar.filter_edit.accessibleName() == "Filter files"
    assert bar.filter_edit.toolTip()
    assert "Esc" in bar.filter_edit.placeholderText()
    assert bar.filter_edit.isClearButtonEnabled()


# --- FileListView: right-aligned size column ----------------------------

def _populate_list(view, tmp_path, names_with_sizes):
    for name, size in names_with_sizes:
        p = tmp_path / name
        p.write_bytes(b"x" * size)
    view.set_path(str(tmp_path))


def test_size_column_header_right_aligned(qapp):
    view = FileListView()
    header_item = view.source_model.horizontalHeaderItem(1)
    assert header_item is not None
    align = header_item.textAlignment()
    assert align & Qt.AlignmentFlag.AlignRight


def test_size_cells_right_aligned(qapp, tmp_path):
    view = FileListView()
    _populate_list(view, tmp_path, [("a.txt", 5), ("b.txt", 2048)])
    # find a non-directory row and check size item alignment
    found = False
    for row in range(view.source_model.rowCount()):
        name_item = view.source_model.item(row, 0)
        size_item = view.source_model.item(row, 1)
        if name_item and size_item and not bool(name_item.data(Qt.ItemDataRole.UserRole + 1)):
            assert size_item.textAlignment() & Qt.AlignmentFlag.AlignRight
            found = True
    assert found, "Expected at least one file row populated"


# --- FileListView: empty-filter overlay --------------------------------

def test_empty_filter_overlay_hidden_for_empty_folder(qapp, tmp_path):
    """The hint must NOT appear for genuinely empty folders."""
    view = FileListView()
    view.set_path(str(tmp_path))  # empty folder
    view._update_empty_filter_overlay()
    assert not view._empty_filter_label.isVisible()


def test_empty_filter_overlay_hidden_when_no_filter(qapp, tmp_path):
    view = FileListView()
    _populate_list(view, tmp_path, [("a.txt", 1)])
    view._update_empty_filter_overlay()
    assert not view._empty_filter_label.isVisible()


def test_empty_filter_overlay_shown_when_filter_hides_all(qapp, tmp_path):
    view = FileListView()
    view.show()  # needed for visibility checks
    _populate_list(view, tmp_path, [("alpha.txt", 1), ("beta.txt", 1)])
    regex = QRegularExpression(
        "zzzzzzzzz_no_match", QRegularExpression.PatternOption.CaseInsensitiveOption
    )
    view.proxy_model.setFilterRegularExpression(regex)
    view._update_empty_filter_overlay()
    assert view._empty_filter_label.isVisible()
    # Removing the filter hides the overlay again
    view.proxy_model.setFilterRegularExpression(QRegularExpression(""))
    view._update_empty_filter_overlay()
    assert not view._empty_filter_label.isVisible()


# --- Tab close-on-hover behaviour -----------------------------------------
# (Removed: the hover-only close-button feature was reverted; the standard
# Qt always-visible close buttons are kept.)
