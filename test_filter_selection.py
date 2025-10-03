#!/usr/bin/env python3
"""
Test script to verify filter selection persistence
"""

import sys
import os
sys.path.insert(0, 'src')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow

def test_filter_selection():
    """Test that selection persists when filtering"""
    app = QApplication(sys.argv)

    # Create main window
    window = MainWindow()

    # Navigate to current directory for testing
    test_path = os.getcwd()
    window.navigate_to(test_path)

    # Get file list view
    file_list = window.file_list

    # Print current files
    print(f"Files in {test_path}:")
    for row in range(file_list.source_model.rowCount()):
        item = file_list.source_model.item(row, 0)
        if item:
            print(f"  {item.text()}")

    # Test 1: Select an item and apply filter
    print("\nTest 1: Selection persistence with filtering")
    if file_list.source_model.rowCount() > 1:
        # Select second item
        second_index = file_list.proxy_model.index(1, 0)
        if second_index.isValid():
            file_list.setCurrentIndex(second_index)
            src_index = file_list.proxy_model.mapToSource(second_index)
            selected_item = file_list.source_model.item(src_index.row(), 0)
            selected_name = selected_item.text() if selected_item else "None"
            print(f"Selected item: {selected_name}")

            # Apply a filter that should include this item
            filter_text = selected_name[:2] if len(selected_name) > 2 else selected_name
            print(f"Applying filter: '{filter_text}'")
            window.apply_filter(filter_text)

            # Check if selection is maintained
            current_index = file_list.currentIndex()
            if current_index.isValid():
                src_index = file_list.proxy_model.mapToSource(current_index)
                current_item = file_list.source_model.item(src_index.row(), 0)
                current_name = current_item.text() if current_item else "None"
                print(f"Current selection after filter: {current_name}")

                if current_name == selected_name:
                    print("✓ Selection persistence test PASSED")
                else:
                    print("✗ Selection persistence test FAILED")
            else:
                print("✗ No selection after filter")

            # Clear filter and check visibility
            print("\nTest 2: Visibility after clearing filter")
            window.clear_filter()

            # Check if item is still selected
            current_index = file_list.currentIndex()
            if current_index.isValid():
                src_index = file_list.proxy_model.mapToSource(current_index)
                current_item = file_list.source_model.item(src_index.row(), 0)
                current_name = current_item.text() if current_item else "None"
                print(f"Current selection after clearing filter: {current_name}")
                print("✓ Visibility test completed (selection maintained)")
            else:
                print("✗ No selection after clearing filter")

    print("\nTests completed!")
    return True

if __name__ == "__main__":
    test_filter_selection()
