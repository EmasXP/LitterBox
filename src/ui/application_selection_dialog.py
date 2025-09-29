"""
Application selection dialog for "Open with" functionality
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton,
                             QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont
from core.application_manager import ApplicationManager, DesktopApplication
from typing import Optional, List


class ApplicationListItem(QListWidgetItem):
    """Custom list item for applications"""

    def __init__(self, application: DesktopApplication, is_default: bool = False):
        super().__init__()
        self.application = application
        self.is_default = is_default

        # Set the display text
        display_text = application.name
        if is_default:
            display_text += " (default)"

        self.setText(display_text)

        # Store the application as user data
        self.setData(Qt.ItemDataRole.UserRole, application)
        self.setData(Qt.ItemDataRole.UserRole + 1, is_default)

        # Make default application bold
        if is_default:
            font = self.font()
            font.setBold(True)
            self.setFont(font)


class ApplicationSelectionDialog(QDialog):
    """Dialog for selecting an application to open a file"""

    # Emitted when user selects "Open" with an application
    application_selected = pyqtSignal(object)  # DesktopApplication

    # Emitted when user wants to set a new default application
    default_changed = pyqtSignal(object)  # DesktopApplication

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.app_manager = ApplicationManager()
        self.applications = []
        self.default_application = None

        self.setup_ui()
        self.load_applications()

    def setup_ui(self):
        """Setup the dialog UI"""
        filename = os.path.basename(self.file_path)
        self.setWindowTitle(f"Open with - {filename}")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Header label
        header_label = QLabel(f"Choose an application to open '{os.path.basename(self.file_path)}':")
        header_label.setWordWrap(True)
        layout.addWidget(header_label)

        # Application list
        self.app_list = QListWidget()
        self.app_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.app_list)

        # Button layout
        button_layout = QHBoxLayout()

        # Set as default button
        self.set_default_btn = QPushButton("Set as Default")
        self.set_default_btn.clicked.connect(self.set_as_default)
        self.set_default_btn.setEnabled(False)
        button_layout.addWidget(self.set_default_btn)

        button_layout.addStretch()

        # Open button
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.open_with_selected)
        open_btn.setDefault(True)
        button_layout.addWidget(open_btn)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Connect selection change
        self.app_list.itemSelectionChanged.connect(self.on_selection_changed)

    def load_applications(self):
        """Load available applications for the file"""
        # Get default application
        self.default_application = self.app_manager.get_default_application(self.file_path)

        # Get ranked applications (improved heuristic list)
        try:
            self.applications = self.app_manager.get_ranked_applications_for_file(self.file_path)
        except AttributeError:
            # Fallback if running with older ApplicationManager
            self.applications = self.app_manager.get_applications_for_file(self.file_path)

        # Clear the list
        self.app_list.clear()

        # Add default application first (if found)
        if self.default_application:
            default_item = ApplicationListItem(self.default_application, is_default=True)
            self.app_list.addItem(default_item)

            # Add separator line
            separator = QListWidgetItem()
            separator.setText("─" * 50)  # Horizontal line
            separator.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-selectable
            font = separator.font()
            font.setPointSize(font.pointSize() - 2)
            separator.setFont(font)
            separator.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.app_list.addItem(separator)

        # Add other applications (excluding the default one)
        other_apps = [app for app in self.applications
                     if not self.default_application or app.path != self.default_application.path]

        for app in other_apps:
            item = ApplicationListItem(app, is_default=False)
            self.app_list.addItem(item)

        # Select the first selectable item
        if self.app_list.count() > 0:
            self.app_list.setCurrentRow(0)

    def on_selection_changed(self):
        """Handle selection change"""
        current_item = self.app_list.currentItem()

        # Check if current item is valid and selectable
        if current_item and current_item.flags() & Qt.ItemFlag.ItemIsSelectable:
            application = current_item.data(Qt.ItemDataRole.UserRole)
            is_default = current_item.data(Qt.ItemDataRole.UserRole + 1)

            # Enable "Set as Default" button only if this is not already the default
            self.set_default_btn.setEnabled(not is_default)
        else:
            self.set_default_btn.setEnabled(False)

    def on_item_double_clicked(self, item: QListWidgetItem):
        """Handle item double click - open with the application"""
        if item.flags() & Qt.ItemFlag.ItemIsSelectable:
            self.open_with_selected()

    def get_selected_application(self) -> Optional[DesktopApplication]:
        """Get the currently selected application"""
        current_item = self.app_list.currentItem()
        if current_item and current_item.flags() & Qt.ItemFlag.ItemIsSelectable:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    def open_with_selected(self):
        """Open file with selected application"""
        application = self.get_selected_application()
        if application:
            self.application_selected.emit(application)
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select an application first.")

    def set_as_default(self):
        """Set selected application as default for this file type"""
        application = self.get_selected_application()
        if not application:
            QMessageBox.warning(self, "No Selection", "Please select an application first.")
            return

        # Confirm the action
        reply = QMessageBox.question(
            self, "Set Default Application",
            f"Set '{application.name}' as the default application for this file type?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Extract desktop filename from the path
            desktop_file = os.path.basename(application.path)

            success = self.app_manager.set_default_application_for_file(self.file_path, desktop_file)
            if success:
                self.default_changed.emit(application)
                QMessageBox.information(
                    self, "Default Application Set",
                    f"'{application.name}' is now the default application for this file type."
                )
                # Reload the list to show the new default
                self.load_applications()
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"Could not set '{application.name}' as the default application."
                )


import os
