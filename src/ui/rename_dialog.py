"""Rename dialog with intelligent base-name preselection.

Behavior:
  hello.txt            -> select "hello"
  hello.tar.gz         -> select "hello"
  archive.backup.tar.gz-> select "archive"
  Makefile             -> select entire name
  .bashrc              -> select entire name (hidden file w/out further dots)
  .config.json         -> select ".config"

This mirrors common file manager UX making it harder to accidentally alter extensions.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox
)
from PyQt6.QtCore import Qt

def _selection_span(filename: str) -> tuple[int, int]:
    """Return (start, length) for portion to preselect based on rules.

    Rules:
      - Skip a single leading dot when searching for first extension separator.
      - First dot after leading dot (or at position 0 if not hidden) terminates selection.
      - If no such dot, select whole name.
    """
    if not filename:
        return 0, 0
    search_from = 1 if filename.startswith('.') else 0
    dot_index = filename.find('.', search_from)
    if dot_index == -1:
        return 0, len(filename)
    return 0, dot_index

class RenameDialog(QDialog):
    def __init__(self, original_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename")
        self._original_name = original_name
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Rename '{self._original_name}' to:"))

        self.line_edit = QLineEdit(self._original_name)
        layout.addWidget(self.line_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.resize(420, 110)
        self.line_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        start, length = _selection_span(self._original_name)
        if length:
            self.line_edit.setSelection(start, length)

    @property
    def new_name(self) -> str:
        return self.line_edit.text().strip()

def get_rename(parent, original_name: str):
    """Show dialog and return (new_name, ok)."""
    dlg = RenameDialog(original_name, parent=parent)
    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return dlg.new_name, ok
