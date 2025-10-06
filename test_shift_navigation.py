#!/usr/bin/env python3
"""
Test script to verify Shift+navigation key functionality in FileListView
"""
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from pathlib import Path
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ui.file_list_view import FileListView

def test_shift_navigation():
    """Test Shift+navigation key combinations"""
    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the file list view
    file_list = FileListView(window)
    layout.addWidget(file_list)

    # Set a test directory with some files
    test_dir = "/home/magnus/python/LitterBox"
    file_list.set_path(test_dir)

    window.setWindowTitle("Test Shift+Navigation Keys")
    window.resize(800, 600)
    window.show()

    print("Test window created. Test the following key combinations:")
    print("1. Use Arrow keys to navigate normally")
    print("2. Hold Shift and use Arrow Up/Down to extend selection")
    print("3. Hold Shift and use PageUp/PageDown to extend selection")
    print("4. Hold Shift and use Home/End to extend selection")
    print("5. Click without Shift to reset selection anchor")
    print("6. Close the window when done testing")

    sys.exit(app.exec())

if __name__ == "__main__":
    test_shift_navigation()
