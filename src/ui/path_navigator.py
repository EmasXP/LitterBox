"""
Path navigation widget - displays path as clickable buttons
"""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QLineEdit,
                             QSizePolicy, QCompleter)
from PyQt6.QtCore import pyqtSignal, Qt, QDir
from PyQt6.QtGui import QKeyEvent, QFileSystemModel
from pathlib import Path
from typing import List

class PathNavigator(QWidget):
    """Widget that displays current path as clickable buttons or text input"""

    path_changed = pyqtSignal(str)
    edit_mode_exited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = Path.home()
        self.edit_mode = False
        self._pending_selection_names: List[str] = []

        self.setup_ui()
        self.update_path_display()

    def setup_ui(self):
        """Initialize the UI components"""
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)

        # Text input for edit mode
        self.path_edit = QLineEdit()
        self.path_edit.setVisible(False)
        self.path_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.path_edit.returnPressed.connect(self.confirm_path_edit)

        # Setup autocomplete for path input
        self.completer = QCompleter()
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath("")
        self.fs_model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        self.completer.setModel(self.fs_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.path_edit.setCompleter(self.completer)

        # Install event filter to handle Tab key
        self.path_edit.installEventFilter(self)

        # Connect textChanged to update completer (but avoid during completer navigation)
        self._updating_from_completer = False
        self.path_edit.textChanged.connect(self.update_completer)

        self._layout.addWidget(self.path_edit, 1)  # stretch factor of 1 to fill space

        # Container for path buttons
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(2)
        self._layout.addWidget(self.button_container)

        # Stretch to push buttons to left
        self._layout.addStretch()

    def set_path(self, path):
        """Set the current path and update display"""
        self.current_path = Path(path).resolve()
        self.update_path_display()

    def update_path_display(self):
        """Update the path button display"""
        # Clear existing buttons
        for i in reversed(range(self.button_layout.count())):
            item = self.button_layout.itemAt(i)
            child = item.widget() if item else None
            if child:
                child.deleteLater()

        # Create buttons for each path component
        parts = self.current_path.parts
        current_path_parts = []

        total_parts = len(parts)
        for idx, part in enumerate(parts):
            current_path_parts.append(part)
            button_path = Path(*current_path_parts)

            # Special handling for root
            if part == '/':
                button_text = '/'
            else:
                button_text = part

            button = QPushButton(button_text)
            button.setFlat(True)
            button.setProperty("pathRole", "segment")
            button.setStyleSheet("""
                QPushButton {
                    border: 1px solid palette(mid);
                    padding: 4px 8px;
                    margin: 0px;
                }
                QPushButton[pathRole="segment"] {
                    background-color: palette(button);
                }
                QPushButton[pathRole="segment"]:hover {
                    background-color: palette(light);
                    border: 1px solid palette(highlight);
                }
                QPushButton[pathRole="segment"]:pressed {
                    background-color: palette(midlight);
                }
                QPushButton[pathRole="segment"]:focus {
                    border: 1px solid palette(highlight);
                    background-color: palette(light);
                    outline: none;
                }
                /* Current (last) path segment styling */
                QPushButton[pathRole="current"] {
                    font-weight: bold;
                    background-color: palette(window);
                    color: palette(windowText);
                }
                QPushButton[pathRole="current"]:hover {
                    /* Keep it stable on hover so it feels selected */
                    background-color: palette(window);
                }
                QPushButton[pathRole="current"]:pressed {
                    background-color: palette(window);
                }
            """)

            # Store the full path for this button
            is_last = (idx == total_parts - 1)
            if is_last:
                button.setProperty("pathRole", "current")
                # Prevent navigation while leaving the button enabled (no-op)
                button.clicked.connect(lambda checked: None)
            else:
                next_part = parts[idx + 1] if idx + 1 < total_parts else None
                button.clicked.connect(
                    lambda checked=False, p=str(button_path), child=next_part: self.navigate_to_path(p, child)
                )

            self.button_layout.addWidget(button)

    def navigate_to_path(self, path, select_child=None):
        """Navigate to the specified path and remember which child to select."""
        self._pending_selection_names = []
        if select_child:
            self._pending_selection_names.append(str(select_child))
        self.set_path(path)
        self.path_changed.emit(str(self.current_path))

    def take_selection_hints(self) -> List[str]:
        """Return and clear pending selection hints for the next navigation."""
        hints = self._pending_selection_names
        self._pending_selection_names = []
        return hints

    def update_completer(self, text):
        """Update completer based on current text"""
        if not text or self._updating_from_completer:
            return

        # Get the parent directory of the current text
        path = Path(text)
        if path.is_dir() and text.endswith('/'):
            # If it's a directory with trailing slash, show its contents
            parent_dir = text.rstrip('/')
        else:
            # If it's incomplete, show parent directory contents
            parent_dir = str(path.parent) if path.parent != path else "/"

        # Ensure the filesystem model has fetched this directory
        index = self.fs_model.index(parent_dir)
        if index.isValid():
            self.fs_model.fetchMore(index)

    def toggle_edit_mode(self):
        """Toggle between button and text edit mode"""
        if self.edit_mode:
            self.exit_edit_mode()
        else:
            self.enter_edit_mode()

    def enter_edit_mode(self):
        """Enter text edit mode (Ctrl+L)"""
        self.edit_mode = True
        path_text = str(self.current_path)
        self.path_edit.setText(path_text)
        self.path_edit.setVisible(True)
        self.button_container.setVisible(False)
        self.path_edit.setFocus()
        self.path_edit.selectAll()
        # Trigger completer update
        self.update_completer(path_text)

    def exit_edit_mode(self):
        """Exit text edit mode (Esc)"""
        self.edit_mode = False
        self.path_edit.setVisible(False)
        self.button_container.setVisible(True)
        self.edit_mode_exited.emit()

    def confirm_path_edit(self):
        """Confirm the path edit and navigate"""
        new_path = self.path_edit.text().strip()
        if new_path and Path(new_path).exists():
            self.set_path(new_path)
            self.path_changed.emit(str(self.current_path))
        self.exit_edit_mode()

    def eventFilter(self, obj, event):
        """Handle events for path_edit, specifically Tab key for autocomplete"""
        if obj == self.path_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Tab:
                # Tab key: autocomplete but don't navigate
                if self.completer.popup().isVisible():
                    # If popup is visible, use the current completion
                    current_completion = self.completer.currentCompletion()
                    if current_completion:
                        self.path_edit.setText(current_completion)
                        self.path_edit.setFocus()
                        # Trigger completer again to show next level suggestions
                        self.completer.complete()
                        return True
                return True  # Consume Tab key event
        return super().eventFilter(obj, event)

    def keyPressEvent(self, a0: QKeyEvent | None):
        """Handle key press events"""
        if a0 is None:
            super().keyPressEvent(a0)
            return
        if a0.key() == Qt.Key.Key_Escape and self.edit_mode:
            self.exit_edit_mode()
        else:
            super().keyPressEvent(a0)
