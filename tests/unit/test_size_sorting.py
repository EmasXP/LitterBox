"""
Tests for file size sorting functionality
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from ui.file_list_view import FileSortProxyModel


def test_size_sorting_with_different_units():
    """Test that size sorting works correctly with different units (GB, MB, KB)"""
    # Create source model
    source_model = QStandardItemModel()
    source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

    # Add test data with sizes in different units
    # The raw sizes in bytes should be:
    # - 1.8 GB = 1,932,735,283 bytes
    # - 157 MB = 164,626,432 bytes
    # - 500 KB = 512,000 bytes
    # - 10 MB = 10,485,760 bytes
    test_files = [
        ("large_file.mp4", "1.8 GB", 1932735283),
        ("medium_file.zip", "157 MB", 164626432),
        ("small_file.pdf", "500 KB", 512000),
        ("tiny_file.txt", "10 MB", 10485760),
    ]

    for name, size_str, size_bytes in test_files:
        name_item = QStandardItem(name)
        name_item.setData(f"/test/{name}", Qt.ItemDataRole.UserRole)  # path
        name_item.setData(False, Qt.ItemDataRole.UserRole + 1)  # is_dir flag

        size_item = QStandardItem(size_str)
        size_item.setData(size_bytes, Qt.ItemDataRole.UserRole)  # raw size in bytes

        modified_item = QStandardItem("2024-01-01 12:00")

        source_model.appendRow([name_item, size_item, modified_item])

    # Create proxy model and set source
    proxy_model = FileSortProxyModel()
    proxy_model.setSourceModel(source_model)

    # Sort by size column (column 1) in ascending order
    proxy_model.sort(1, Qt.SortOrder.AscendingOrder)

    # Verify the order is correct (smallest to largest)
    # 500 KB < 10 MB < 157 MB < 1.8 GB
    expected_order = ["small_file.pdf", "tiny_file.txt", "medium_file.zip", "large_file.mp4"]

    for i, expected_name in enumerate(expected_order):
        proxy_index = proxy_model.index(i, 0)
        actual_name = proxy_model.data(proxy_index, Qt.ItemDataRole.DisplayRole)
        assert actual_name == expected_name, \
            f"At position {i}, expected {expected_name} but got {actual_name}"

    # Sort by size column in descending order
    proxy_model.sort(1, Qt.SortOrder.DescendingOrder)

    # Verify the order is correct (largest to smallest)
    # 1.8 GB > 157 MB > 10 MB > 500 KB
    expected_order_desc = ["large_file.mp4", "medium_file.zip", "tiny_file.txt", "small_file.pdf"]

    for i, expected_name in enumerate(expected_order_desc):
        proxy_index = proxy_model.index(i, 0)
        actual_name = proxy_model.data(proxy_index, Qt.ItemDataRole.DisplayRole)
        assert actual_name == expected_name, \
            f"At position {i}, expected {expected_name} but got {actual_name}"


def test_size_sorting_with_directories():
    """Test that directories still come first when sorting by size"""
    source_model = QStandardItemModel()
    source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

    # Add directories and files
    test_items = [
        ("documents", "", 0, True),  # directory
        ("large_file.mp4", "1.8 GB", 1932735283, False),
        ("photos", "", 0, True),  # directory
        ("small_file.txt", "10 KB", 10240, False),
    ]

    for name, size_str, size_bytes, is_dir in test_items:
        name_item = QStandardItem(name)
        name_item.setData(f"/test/{name}", Qt.ItemDataRole.UserRole)  # path
        name_item.setData(is_dir, Qt.ItemDataRole.UserRole + 1)  # is_dir flag

        size_item = QStandardItem(size_str)
        if not is_dir:
            size_item.setData(size_bytes, Qt.ItemDataRole.UserRole)  # raw size

        modified_item = QStandardItem("2024-01-01 12:00")

        source_model.appendRow([name_item, size_item, modified_item])

    # Create proxy model
    proxy_model = FileSortProxyModel()
    proxy_model.setSourceModel(source_model)

    # Sort by size column in ascending order
    proxy_model.sort(1, Qt.SortOrder.AscendingOrder)

    # Directories should still come first
    first_name = proxy_model.data(proxy_model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    second_name = proxy_model.data(proxy_model.index(1, 0), Qt.ItemDataRole.DisplayRole)

    assert first_name in ["documents", "photos"], \
        f"First item should be a directory, got {first_name}"
    assert second_name in ["documents", "photos"], \
        f"Second item should be a directory, got {second_name}"


def test_size_sorting_handles_missing_size_data():
    """Test that sorting handles items without size data gracefully"""
    source_model = QStandardItemModel()
    source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

    # Add test data where some items might not have size data
    test_files = [
        ("file_with_size.txt", "10 KB", 10240),
        ("file_without_size.txt", "", None),
        ("another_file.txt", "5 KB", 5120),
    ]

    for name, size_str, size_bytes in test_files:
        name_item = QStandardItem(name)
        name_item.setData(f"/test/{name}", Qt.ItemDataRole.UserRole)
        name_item.setData(False, Qt.ItemDataRole.UserRole + 1)

        size_item = QStandardItem(size_str)
        if size_bytes is not None:
            size_item.setData(size_bytes, Qt.ItemDataRole.UserRole)

        modified_item = QStandardItem("2024-01-01 12:00")

        source_model.appendRow([name_item, size_item, modified_item])

    # Create proxy model and sort
    proxy_model = FileSortProxyModel()
    proxy_model.setSourceModel(source_model)

    # Should not crash when sorting
    proxy_model.sort(1, Qt.SortOrder.AscendingOrder)

    # Verify it sorted without crashing (basic sanity check)
    assert proxy_model.rowCount() == 3
