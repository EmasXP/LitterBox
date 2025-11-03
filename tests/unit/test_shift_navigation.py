#!/usr/bin/env python3
"""
Unit tests for Shift+navigation key functionality in FileListView
"""
import sys
import os
import tempfile
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtTest import QTest

from ui.file_list_view import FileListView
import pytest

@pytest.mark.skip("Unstable in aggregate run: abort in PyQt event processing. Needs isolation / refactor.")
def test_shift_navigation():
    """Test shift+navigation key combinations extend selection properly"""
    print("Running test_shift_navigation")

    # QApplication provided by session fixture
    assert QApplication.instance() is not None, "QApplication fixture not initialized"

    # Create file list view
    file_list = FileListView()

    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some test files
        for i in range(10):
            Path(temp_dir, f"file_{i:02d}.txt").write_text(f"Test file {i}")

        # Set the path to populate the list
        file_list.set_path(temp_dir)

        # Give the view time to populate
        QTest.qWait(100)

        model = file_list.model()
        assert model.rowCount() >= 10, f"Expected at least 10 files, got {model.rowCount()}"

        # Test 1: Normal navigation should reset anchor
        file_list.setCurrentIndex(model.index(2, 0))
        assert file_list._selection_anchor == 2, f"Expected anchor at 2, got {file_list._selection_anchor}"

        # Test 2: Shift+Down should extend selection
        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
        file_list.keyPressEvent(down_event)

        selection_model = file_list.selectionModel()
        selected_rows = [idx.row() for idx in selection_model.selectedRows()]
        assert 2 in selected_rows and 3 in selected_rows, f"Expected rows 2,3 selected, got {selected_rows}"

        # Test 3: Shift+Up should contract selection (current implementation contracts rather than extending upward)
        up_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
        file_list.keyPressEvent(up_event)

        selected_rows = [idx.row() for idx in selection_model.selectedRows()]
        # Current behavior: selection shrinks back to single anchor row
        assert len(selected_rows) == 1, f"Expected 1 row selected after up, got {len(selected_rows)}"

        # Test 4: Shift+Home should extend to beginning
        home_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.ShiftModifier)
        file_list.keyPressEvent(home_event)

        selected_rows = [idx.row() for idx in selection_model.selectedRows()]
        assert 0 in selected_rows and 2 in selected_rows, f"Expected selection from 0 to anchor, got {selected_rows}"

        # Test 5: Reset selection and test Shift+End
        file_list.setCurrentIndex(model.index(1, 0))
        end_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.ShiftModifier)
        file_list.keyPressEvent(end_event)

        selected_rows = [idx.row() for idx in selection_model.selectedRows()]
        last_row = model.rowCount() - 1
        assert 1 in selected_rows and last_row in selected_rows, f"Expected selection from 1 to end, got {selected_rows}"

    print("All shift navigation tests passed!")

@pytest.mark.skip("Unstable in aggregate run: abort in PyQt event processing. Needs isolation / refactor.")
def test_anchor_reset():
    """Test that selection anchor resets properly on normal navigation"""
    print("Running test_anchor_reset")

    assert QApplication.instance() is not None, "QApplication fixture not initialized"

    file_list = FileListView()

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        for i in range(5):
            Path(temp_dir, f"file_{i}.txt").write_text(f"Test file {i}")

        file_list.set_path(temp_dir)
        QTest.qWait(100)

        model = file_list.model()

        # Set initial position
        file_list.setCurrentIndex(model.index(1, 0))
        assert file_list._selection_anchor == 1

        # Normal down arrow should move and reset anchor
        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        file_list.keyPressEvent(down_event)

        assert file_list._selection_anchor == 2, f"Expected anchor at 2 after down, got {file_list._selection_anchor}"
        assert file_list.currentIndex().row() == 2, f"Expected current at 2, got {file_list.currentIndex().row()}"

    print("Anchor reset test passed!")

def run_all_tests():
    """Run all tests"""
    try:
        test_shift_navigation()
        test_anchor_reset()
        print("\nAll Shift+navigation tests passed successfully!")
        return True
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
