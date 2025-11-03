"""
Manual demonstration of multi-select delete/trash functionality.

This script creates a simple test environment to manually verify:
1. Multiple selection in the file list
2. Right-click context menu showing item count
3. Delete/Trash operations on multiple files
4. Pretty confirmation dialogs

To run:
    python tests/manual/multi_delete_demo.py
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def create_test_files():
    """Create a temporary directory with test files"""
    temp_dir = tempfile.mkdtemp(prefix='litterbox_multi_delete_test_')

    # Create several test files
    test_files = [
        'document1.txt',
        'document2.txt',
        'document3.txt',
        'image1.jpg',
        'image2.jpg',
        'data.csv',
    ]

    for filename in test_files:
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w') as f:
            f.write(f"Test content for {filename}\n")
            f.write("You can safely delete this file.\n")

    # Create a test folder
    test_folder = os.path.join(temp_dir, 'test_folder')
    os.makedirs(test_folder)

    # Create a file inside the folder
    nested_file = os.path.join(test_folder, 'nested_file.txt')
    with open(nested_file, 'w') as f:
        f.write("File inside test folder\n")

    return temp_dir


def main():
    """Run the manual test"""
    app = QApplication(sys.argv)

    # Create test directory
    test_dir = create_test_files()
    print(f"\n{'='*60}")
    print(f"Test directory created: {test_dir}")
    print(f"{'='*60}\n")

    print("Multi-Select Delete/Trash Test Instructions:")
    print("-" * 60)
    print("1. The LitterBox window will open to the test directory")
    print("2. Select MULTIPLE files by:")
    print("   - Click first file")
    print("   - Hold Ctrl and click additional files")
    print("   - OR: Click first file, hold Shift, click last file")
    print("3. Right-click on one of the selected files")
    print("4. Notice the menu shows:")
    print("   - 'Move to Trash (X items)' or 'Delete (X items)'")
    print("   - Rename is disabled for multiple selections")
    print("   - Open is disabled for multiple selections")
    print("5. Try both 'Move to Trash' and 'Delete':")
    print("   - Delete shows a pretty confirmation dialog")
    print("   - Lists the first 5 items if more are selected")
    print("   - Both operations work on all selected items")
    print("-" * 60)
    print("\nClose the window when done testing.\n")

    # Create main window and navigate to test directory
    window = MainWindow()
    window.show()

    # Navigate to the test directory in the active tab
    if window.tab_widget.count() > 0:
        current_tab = window.tab_widget.currentWidget()
        if current_tab and hasattr(current_tab, 'navigate_to'):
            current_tab.navigate_to(test_dir)

    exit_code = app.exec()

    # Cleanup
    print(f"\nCleaning up test directory: {test_dir}")
    if os.path.exists(test_dir):
        try:
            shutil.rmtree(test_dir)
            print("Test directory removed successfully.")
        except Exception as e:
            print(f"Note: Could not remove test directory: {e}")
            print(f"You may want to manually delete: {test_dir}")

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
