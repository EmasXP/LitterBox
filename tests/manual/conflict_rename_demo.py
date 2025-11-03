#!/usr/bin/env python3
"""Manual test to demonstrate conflict resolution rename suggestions and validation.

This script creates a test scenario where you can manually verify that
the conflict dialog suggests the correct name when multiple conflicts exist
and that it shows a warning when you enter an existing name.

Usage:
    python tests/manual/conflict_rename_demo.py
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from PyQt6.QtWidgets import QApplication
from ui.conflict_dialog import ConflictDialog


def main():
    """Demonstrate conflict dialog rename suggestions and validation."""
    app = QApplication(sys.argv)

    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Scenario 1: Simple conflict (only foo.txt exists)
        print("=" * 60)
        print("Scenario 1: Only 'test.txt' exists")
        print("=" * 60)
        existing1 = tmpdir_path / "test.txt"
        existing1.touch()

        dlg1 = ConflictDialog(
            filename="test.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing1)
        )
        print(f"Suggested rename: {dlg1.rename_edit.text()}")
        print(f"Expected: test (1).txt")
        print(f"Rename button enabled: {dlg1.ok_btn.isEnabled()}")
        print(f"Warning visible: {dlg1.name_conflict_warning.isVisible()}")
        print()

        # Scenario 2: Multiple conflicts (foo.txt and foo (1).txt exist)
        print("=" * 60)
        print("Scenario 2: 'test.txt' AND 'test (1).txt' exist")
        print("=" * 60)
        existing2 = tmpdir_path / "test (1).txt"
        existing2.touch()

        dlg2 = ConflictDialog(
            filename="test.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing1)  # Still pointing to test.txt
        )
        print(f"Suggested rename: {dlg2.rename_edit.text()}")
        print(f"Expected: test (2).txt")
        print(f"Rename button enabled: {dlg2.ok_btn.isEnabled()}")
        print()

        # Scenario 3: Show warning when user types existing name
        print("=" * 60)
        print("Scenario 3: Real-time validation demo")
        print("=" * 60)
        dlg3 = ConflictDialog(
            filename="test.txt",
            parent=None,
            source_path=None,
            existing_path=str(existing1)
        )
        dlg3.show()  # Must show for visibility to work
        app.processEvents()

        print(f"Initial suggestion: {dlg3.rename_edit.text()}")
        print(f"Button enabled: {dlg3.ok_btn.isEnabled()}")
        print(f"Warning visible: {dlg3.name_conflict_warning.isVisible()}")

        # User types an existing name
        print("\n→ User changes name to 'test (1).txt' (which exists)...")
        dlg3.rename_edit.setText("test (1).txt")
        app.processEvents()
        print(f"Button enabled: {dlg3.ok_btn.isEnabled()}")
        print(f"Warning visible: {dlg3.name_conflict_warning.isVisible()}")
        print(f"Warning text: '{dlg3.name_conflict_warning.text()}'")

        # User types an available name
        print("\n→ User changes name to 'test (3).txt' (available)...")
        dlg3.rename_edit.setText("test (3).txt")
        app.processEvents()
        print(f"Button enabled: {dlg3.ok_btn.isEnabled()}")
        print(f"Warning visible: {dlg3.name_conflict_warning.isVisible()}")

        dlg3.close()

        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("=" * 60)
        print("Features demonstrated:")
        print("✓ Smart initial rename suggestions (finds first available number)")
        print("✓ Real-time validation as user types")
        print("✓ Friendly warning when name already exists")
        print("✓ Rename button disabled for invalid names")
        print("=" * 60)


if __name__ == "__main__":
    main()
