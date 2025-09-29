"""Tabbed conflict resolution dialog with Rename / Overwrite / Skip options.

Decisions exposed:
    - rename   -> user provided a new name (``new_name``)
    - overwrite-> overwrite existing (optionally apply to all)
    - skip     -> skip just this single conflicting item
    - cancel   -> cancel the entire transfer
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QCheckBox,
    QTabWidget, QWidget, QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt
from pathlib import Path


class ConflictDialog(QDialog):
    """Provides two tabs:
    - Rename (default): shows an editable suggested new name
    - Overwrite: shows overwrite explanation + apply to all checkbox
    Exposes attributes:
        decision: 'rename' | 'overwrite' | 'cancel'
        apply_all: bool (only meaningful for overwrite)
        new_name: str | None (valid when decision == 'rename')
    """

    def __init__(self, filename: str, parent=None, source_path=None, existing_path=None):
        super().__init__(parent)
        self.setWindowTitle("File Already Exists")
        self.decision = None  # rename | overwrite | skip | cancel
        self.apply_all = False
        self.new_name = None
        self._original_name = filename
        self._source_path = source_path
        self._existing_path = existing_path
        self._build_ui(filename)

    def _build_ui(self, filename: str):
        layout = QVBoxLayout(self)
        header = QLabel(f"An item named '{filename}' already exists.")
        layout.addWidget(header)

        # Size & modification time info section
        if self._source_path and self._existing_path:
            try:
                import os, datetime
                src_size = os.path.getsize(self._source_path)
                dst_size = os.path.getsize(self._existing_path)
                src_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self._source_path))
                dst_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self._existing_path))
                fmt = "%Y-%m-%d %H:%M:%S"
                info_lbl = QLabel(
                    f"Source: {self._format_size(src_size)} • {src_mtime.strftime(fmt)}\n"
                    f"Existing: {self._format_size(dst_size)} • {dst_mtime.strftime(fmt)}"
                )
                info_lbl.setStyleSheet("color: #555; font-size: 11px;")
                layout.addWidget(info_lbl)
                layout.addSpacing(10)
            except OSError:
                pass

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Rename tab
        rename_page = QWidget()
        r_layout = QFormLayout(rename_page)
        r_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.rename_edit = QLineEdit(self._suggest_initial_rename(filename))
        r_layout.addRow("New name:", self.rename_edit)
        self.tabs.addTab(rename_page, "Rename")

        # Overwrite tab
        over_page = QWidget()
        o_layout = QVBoxLayout(over_page)
        o_layout.addWidget(QLabel("Overwrite the existing item with the new one."))
        self.apply_all_cb = QCheckBox("Apply Overwrite to all subsequent conflicts")
        o_layout.addWidget(self.apply_all_cb)
        o_layout.addStretch(1)
        self.tabs.addTab(over_page, "Overwrite")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.ok_btn = QPushButton("OK")
        self.skip_btn = QPushButton("Skip")
        self.cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.skip_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        # Default to rename tab
        self.tabs.setCurrentIndex(0)
        self._update_ok_state()

        # Connections
        self.ok_btn.clicked.connect(self._accept)
        self.skip_btn.clicked.connect(self._skip)
        self.cancel_btn.clicked.connect(self._cancel)
        self.tabs.currentChanged.connect(lambda _: self._update_ok_state())
        self.rename_edit.textChanged.connect(self._update_ok_state)

        self.resize(420, 200)
        # Focus behavior: select name (without extension) when showing
        self.rename_edit.setFocus()
        stem = Path(self.rename_edit.text()).stem
        # Highlight only stem portion
        if stem:
            self.rename_edit.setSelection(0, len(stem))

    def _suggest_initial_rename(self, filename: str) -> str:
        # Add " (1)" before extension if possible
        p = Path(filename)
        stem = p.stem
        suffix = p.suffix
        return f"{stem} (1){suffix}" if stem else filename

    def _format_size(self, n: int) -> str:
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        f = float(n)
        for u in units:
            if f < 1024 or u == units[-1]:
                return f"{f:.1f} {u}" if u != 'B' else f"{int(f)} B"
            f /= 1024
        return f"{int(f)} B"  # Fallback (should not reach)

    def _current_mode(self) -> str:
        return 'rename' if self.tabs.currentIndex() == 0 else 'overwrite'

    def _update_ok_state(self):
        if self._current_mode() == 'rename':
            txt = self.rename_edit.text().strip()
            # Disable OK if empty or identical to original
            enable = bool(txt) and txt != self._original_name
            self.ok_btn.setEnabled(enable)
        else:
            self.ok_btn.setEnabled(True)

    def _accept(self):
        mode = self._current_mode()
        if mode == 'rename':
            self.decision = 'rename'
            self.new_name = self.rename_edit.text().strip()
        else:
            self.decision = 'overwrite'
            self.apply_all = self.apply_all_cb.isChecked()
        self.accept()

    def _cancel(self):
        self.decision = 'cancel'
        self.reject()

    def _skip(self):
        self.decision = 'skip'
        self.accept()
