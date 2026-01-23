#!/usr/bin/env python3
"""
Manual test to demonstrate the file count feature in Properties dialog

This script creates a test directory structure with files and folders,
then opens the Properties dialog to show the file count feature.
"""
import sys
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from ui.properties_dialog import PropertiesDialog


def create_test_structure(base_path: Path):
    """Create a test directory structure"""
    print(f"Creating test structure in {base_path}")

    # Create files in root
    (base_path / "file1.txt").write_text("Content 1")
    (base_path / "file2.txt").write_text("Content 2")
    (base_path / "file3.md").write_text("# README")

    # Create subdirectory with files
    docs = base_path / "documents"
    docs.mkdir()
    (docs / "doc1.txt").write_text("Document 1")
    (docs / "doc2.txt").write_text("Document 2")
    (docs / "notes.txt").write_text("Notes")

    # Create nested subdirectory
    reports = docs / "reports"
    reports.mkdir()
    (reports / "report1.pdf").write_text("PDF content 1")
    (reports / "report2.pdf").write_text("PDF content 2")

    # Create another subdirectory
    images = base_path / "images"
    images.mkdir()
    (images / "photo1.jpg").write_text("JPEG data 1")
    (images / "photo2.jpg").write_text("JPEG data 2")
    (images / "photo3.png").write_text("PNG data")

    # Create an empty subdirectory
    empty = base_path / "empty"
    empty.mkdir()

    print(f"\nCreated structure:")
    print(f"  3 files in root")
    print(f"  3 files in documents/")
    print(f"  2 files in documents/reports/")
    print(f"  3 files in images/")
    print(f"  0 files in empty/")
    print(f"\nTotal: 11 files")
    return base_path


def main():
    """Run the manual test"""
    app = QApplication(sys.argv)

    # Create test structure in a temporary directory
    with tempfile.TemporaryDirectory(prefix="litterbox_test_") as tmpdir:
        test_path = Path(tmpdir) / "test_folder"
        test_path.mkdir()
        create_test_structure(test_path)

        print(f"\n{'='*60}")
        print("Opening Properties dialog for test folder...")
        print("You should see:")
        print("  - Size: calculating... (with spinner)")
        print("  - Files: calculating... (with spinner)")
        print("  - Both should update as files are counted")
        print("  - Final count should show '11 files'")
        print(f"{'='*60}\n")

        # Open Properties dialog
        dialog = PropertiesDialog(str(test_path))
        dialog.exec()

        print("\nTest complete!")


if __name__ == "__main__":
    main()
