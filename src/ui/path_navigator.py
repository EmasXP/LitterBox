"""
Path navigation widget - displays path as clickable buttons
"""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QLineEdit,
                             QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt
from pathlib import Path

class PathNavigator(QWidget):
    """Widget that displays current path as clickable buttons or text input"""

    path_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = Path.home()
        self.edit_mode = False

        self.setup_ui()
        self.update_path_display()

    def setup_ui(self):
        """Initialize the UI components"""
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # Text input for edit mode
        self.path_edit = QLineEdit()
        self.path_edit.setVisible(False)
        self.path_edit.returnPressed.connect(self.confirm_path_edit)
        self.layout.addWidget(self.path_edit)

        # Container for path buttons
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(2)
        self.layout.addWidget(self.button_container)

        # Stretch to push buttons to left
        self.layout.addStretch()

    def set_path(self, path):
        """Set the current path and update display"""
        self.current_path = Path(path).resolve()
        self.update_path_display()

    def update_path_display(self):
        """Update the path button display"""
        # Clear existing buttons
        for i in reversed(range(self.button_layout.count())):
            child = self.button_layout.itemAt(i).widget()
            if child:
                child.deleteLater()

        # Create buttons for each path component
        parts = self.current_path.parts
        current_path_parts = []

        for part in parts:
            current_path_parts.append(part)
            button_path = Path(*current_path_parts)

            # Special handling for root
            if part == '/':
                button_text = '/'
            else:
                button_text = part

            button = QPushButton(button_text)
            button.setFlat(True)
            button.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ccc;
                    padding: 4px 8px;
                    margin: 1px;
                    background-color: #f5f5f5;
                }
                QPushButton:hover {
                    background-color: #e5e5e5;
                }
                QPushButton:pressed {
                    background-color: #d5d5d5;
                }
            """)

            # Store the full path for this button
            button.clicked.connect(lambda checked, p=str(button_path): self.navigate_to_path(p))
            self.button_layout.addWidget(button)

    def navigate_to_path(self, path):
        """Navigate to the specified path"""
        self.set_path(path)
        self.path_changed.emit(str(self.current_path))

    def toggle_edit_mode(self):
        """Toggle between button and text edit mode"""
        if self.edit_mode:
            self.exit_edit_mode()
        else:
            self.enter_edit_mode()

    def enter_edit_mode(self):
        """Enter text edit mode (Ctrl+L)"""
        self.edit_mode = True
        self.path_edit.setText(str(self.current_path))
        self.path_edit.setVisible(True)
        self.button_container.setVisible(False)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def exit_edit_mode(self):
        """Exit text edit mode (Esc)"""
        self.edit_mode = False
        self.path_edit.setVisible(False)
        self.button_container.setVisible(True)

    def confirm_path_edit(self):
        """Confirm the path edit and navigate"""
        new_path = self.path_edit.text().strip()
        if new_path and Path(new_path).exists():
            self.set_path(new_path)
            self.path_changed.emit(str(self.current_path))
        self.exit_edit_mode()

    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Escape and self.edit_mode:
            self.exit_edit_mode()
        else:
            super().keyPressEvent(event)
