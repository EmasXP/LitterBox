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
        self.decision = None  # rename | overwrite | skip | cancel
        self.apply_all = False
        self.new_name = None
        self._original_name = filename
        self._source_path = source_path
        self._existing_path = existing_path

        # Determine types for context-aware UI
        self._src_is_dir = False
        self._dst_is_dir = False
        self._type_mismatch = False

        if self._source_path and self._existing_path:
            try:
                self._src_is_dir = Path(self._source_path).is_dir()
                self._dst_is_dir = Path(self._existing_path).is_dir()
                self._type_mismatch = self._src_is_dir != self._dst_is_dir
            except (OSError, AttributeError):
                pass

        # Set context-aware window title
        if self._type_mismatch:
            if self._src_is_dir and not self._dst_is_dir:
                self.setWindowTitle("Already Exists as File")
            elif not self._src_is_dir and self._dst_is_dir:
                self.setWindowTitle("Already Exists as Folder")
            else:
                self.setWindowTitle("Item Already Exists")
        elif self._dst_is_dir:
            self.setWindowTitle("Folder Already Exists")
        else:
            self.setWindowTitle("File Already Exists")

        self._build_ui(filename)

    def _build_ui(self, filename: str):
        layout = QVBoxLayout(self)
        header = QLabel(f"An item named '{filename}' already exists.")
        layout.addWidget(header)

        # Check for type mismatch (file vs directory) - show warning
        if self._type_mismatch:
            mismatch_label = QLabel()
            if self._src_is_dir:
                mismatch_label.setText("⚠️ Warning: Source is a DIRECTORY but destination is a FILE")
            else:
                mismatch_label.setText("⚠️ Warning: Source is a FILE but destination is a DIRECTORY")
            mismatch_label.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 12px;")
            mismatch_label.setWordWrap(True)
            layout.addWidget(mismatch_label)
            layout.addSpacing(5)

        # Size & modification time info section
        if self._source_path and self._existing_path:
            try:
                import os, datetime

                src_path = Path(self._source_path)
                dst_path = Path(self._existing_path)

                # Handle size display differently for files vs directories
                if src_path.is_file():
                    src_size = os.path.getsize(self._source_path)
                    src_size_str = self._format_size(src_size)
                else:
                    # For directories, show item count instead of size
                    try:
                        item_count = sum(1 for _ in src_path.rglob('*'))
                        src_size_str = f"{item_count} items"
                    except (OSError, PermissionError):
                        src_size_str = "Directory"

                if dst_path.is_file():
                    dst_size = os.path.getsize(self._existing_path)
                    dst_size_str = self._format_size(dst_size)
                else:
                    # For directories, show item count
                    try:
                        item_count = sum(1 for _ in dst_path.rglob('*'))
                        dst_size_str = f"{item_count} items"
                    except (OSError, PermissionError):
                        dst_size_str = "Directory"

                src_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self._source_path))
                dst_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self._existing_path))
                fmt = "%Y-%m-%d %H:%M:%S"

                src_type = "Directory" if src_path.is_dir() else "File"
                dst_type = "Directory" if dst_path.is_dir() else "File"

                info_lbl = QLabel(
                    f"Source ({src_type}): {src_size_str} • {src_mtime.strftime(fmt)}\n"
                    f"Existing ({dst_type}): {dst_size_str} • {dst_mtime.strftime(fmt)}"
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

        # Overwrite/Walk into tab
        over_page = QWidget()
        o_layout = QVBoxLayout(over_page)

        # Context-aware tab label and description
        if self._dst_is_dir and not self._type_mismatch:
            tab_label = "Walk into"
            action_desc = "Merge contents into the existing folder."
        else:
            tab_label = "Overwrite"
            action_desc = "Overwrite the existing item with the new one."

        o_layout.addWidget(QLabel(action_desc))
        self.apply_all_cb = QCheckBox("Apply to all subsequent conflicts")
        o_layout.addWidget(self.apply_all_cb)
        o_layout.addStretch(1)

        overwrite_tab_index = self.tabs.addTab(over_page, tab_label)

        # Disable overwrite tab for type mismatches
        if self._type_mismatch:
            self.tabs.setTabEnabled(overwrite_tab_index, False)
            self.tabs.setTabToolTip(overwrite_tab_index,
                "Cannot merge/overwrite items of different types (file vs folder)")

        self._overwrite_tab_index = overwrite_tab_index
        self._overwrite_tab_label = tab_label

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        # Primary action button (label changes per tab)
        self.ok_btn = QPushButton("Rename")  # default tab is Rename
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
        self.tabs.currentChanged.connect(self._on_tab_changed)
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
            enable = bool(txt) and txt != self._original_name
        else:
            enable = True
        self.ok_btn.setEnabled(enable)

    def _on_tab_changed(self, index: int):  # noqa: ARG002 (index not used besides logic)
        # Update button label according to selected tab
        if self._current_mode() == 'rename':
            self.ok_btn.setText("Rename")
        else:
            # Use the context-aware label (Walk into or Overwrite)
            self.ok_btn.setText(self._overwrite_tab_label)
        self._update_ok_state()

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
