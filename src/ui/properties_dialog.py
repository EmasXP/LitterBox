"""
Properties dialog for files and folders
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QTabWidget, QWidget, QFormLayout, QCheckBox,
                             QComboBox, QGroupBox, QPushButton, QTextEdit,
                             QGridLayout, QSpacerItem, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt
from core.file_operations import FileOperations
from core.application_manager import ApplicationManager, DesktopApplication
from pathlib import Path
import os
import subprocess

class PropertiesDialog(QDialog):
    """Dialog showing file/folder properties"""

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_info = FileOperations.get_file_info(file_path)
        self.app_manager = ApplicationManager()
        self.available_applications = []
        self.default_application = None

        if not self.file_info:
            self.close()
            return

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle(f"Properties - {self.file_info['name']}")
        self.setMinimumSize(400, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Tab widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # General tab
        self.create_general_tab(tab_widget)

        # Permissions tab
        self.create_permissions_tab(tab_widget)

        # Button box
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Apply button (only show if file has "Open with" section)
        if self.file_info['is_file']:
            apply_btn = QPushButton("Apply")
            apply_btn.clicked.connect(self.apply_changes)
            button_layout.addWidget(apply_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def create_general_tab(self, tab_widget):
        """Create the general information tab"""
        general_widget = QWidget()
        layout = QFormLayout(general_widget)

        # Basic information
        info_group = QGroupBox("Information")
        info_layout = QFormLayout(info_group)

        # Name
        info_layout.addRow("Name:", QLabel(self.file_info['name']))

        # Type
        if self.file_info['is_dir']:
            file_type = "Folder"
        elif self.file_info['is_symlink']:
            file_type = "Symbolic Link"
        else:
            file_type = "File"
        info_layout.addRow("Type:", QLabel(file_type))

        # Location
        location = str(Path(self.file_path).parent)
        info_layout.addRow("Location:", QLabel(location))

        # Size
        if self.file_info['is_dir']:
            size_text = "—"
        else:
            size_text = FileOperations.format_size(self.file_info['size'])
        info_layout.addRow("Size:", QLabel(size_text))

        # Dates
        created_text = self.file_info['created'].strftime("%Y-%m-%d %H:%M:%S")
        modified_text = self.file_info['modified'].strftime("%Y-%m-%d %H:%M:%S")

        info_layout.addRow("Created:", QLabel(created_text))
        info_layout.addRow("Modified:", QLabel(modified_text))

        layout.addWidget(info_group)

        # Open with section (for files only)
        if self.file_info['is_file']:
            open_with_group = QGroupBox("Open With")
            open_with_layout = QFormLayout(open_with_group)

            self.open_with_combo = QComboBox()
            self.open_with_combo.currentTextChanged.connect(self.on_application_changed)
            self.populate_open_with_applications()
            open_with_layout.addRow("Default application:", self.open_with_combo)

            layout.addWidget(open_with_group)

        # Add stretch
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        tab_widget.addTab(general_widget, "General")

    def create_permissions_tab(self, tab_widget):
        """Create the permissions tab"""
        permissions_widget = QWidget()
        layout = QVBoxLayout(permissions_widget)

        # Permissions display
        perm_display_group = QGroupBox("Current Permissions")
        perm_display_layout = QFormLayout(perm_display_group)
        perm_display_layout.addRow("Permissions:", QLabel(self.file_info['permissions']))
        layout.addWidget(perm_display_group)

        # Permissions grid
        perm_group = QGroupBox("Edit Permissions")
        perm_layout = QGridLayout(perm_group)

        # Headers
        perm_layout.addWidget(QLabel(""), 0, 0)
        perm_layout.addWidget(QLabel("Read"), 0, 1)
        perm_layout.addWidget(QLabel("Write"), 0, 2)
        perm_layout.addWidget(QLabel("Execute"), 0, 3)

        # Owner permissions
        perm_layout.addWidget(QLabel("Owner:"), 1, 0)
        self.owner_read_cb = QCheckBox()
        self.owner_write_cb = QCheckBox()
        self.owner_execute_cb = QCheckBox()
        perm_layout.addWidget(self.owner_read_cb, 1, 1)
        perm_layout.addWidget(self.owner_write_cb, 1, 2)
        perm_layout.addWidget(self.owner_execute_cb, 1, 3)

        # Group permissions
        perm_layout.addWidget(QLabel("Group:"), 2, 0)
        self.group_read_cb = QCheckBox()
        self.group_write_cb = QCheckBox()
        self.group_execute_cb = QCheckBox()
        perm_layout.addWidget(self.group_read_cb, 2, 1)
        perm_layout.addWidget(self.group_write_cb, 2, 2)
        perm_layout.addWidget(self.group_execute_cb, 2, 3)

        # Others permissions
        perm_layout.addWidget(QLabel("Others:"), 3, 0)
        self.other_read_cb = QCheckBox()
        self.other_write_cb = QCheckBox()
        self.other_execute_cb = QCheckBox()
        perm_layout.addWidget(self.other_read_cb, 3, 1)
        perm_layout.addWidget(self.other_write_cb, 3, 2)
        perm_layout.addWidget(self.other_execute_cb, 3, 3)

        layout.addWidget(perm_group)

        # Apply permissions button
        apply_perm_btn = QPushButton("Apply Permissions")
        apply_perm_btn.clicked.connect(self.apply_permissions)
        layout.addWidget(apply_perm_btn)

        # Add stretch
        layout.addStretch()

        tab_widget.addTab(permissions_widget, "Permissions")

    def load_data(self):
        """Load data into the dialog"""
        # Load permission checkboxes
        if hasattr(self, 'owner_read_cb'):
            self.owner_read_cb.setChecked(self.file_info['owner_read'])
            self.owner_write_cb.setChecked(self.file_info['owner_write'])
            self.owner_execute_cb.setChecked(self.file_info['owner_execute'])

            self.group_read_cb.setChecked(self.file_info['group_read'])
            self.group_write_cb.setChecked(self.file_info['group_write'])
            self.group_execute_cb.setChecked(self.file_info['group_execute'])

            self.other_read_cb.setChecked(self.file_info['other_read'])
            self.other_write_cb.setChecked(self.file_info['other_write'])
            self.other_execute_cb.setChecked(self.file_info['other_execute'])

    def populate_open_with_applications(self):
        """Populate the open with applications combo box"""
        self.open_with_combo.clear()

        # Get default application
        self.default_application = self.app_manager.get_default_application(self.file_path)

        # Get ranked applications for improved suggestions
        try:
            self.available_applications = self.app_manager.get_ranked_applications_for_file(self.file_path)
        except AttributeError:
            self.available_applications = self.app_manager.get_applications_for_file(self.file_path)

        # Track current selection index
        current_selection = 0

        # Add applications to combo box
        if self.default_application:
            # Add default application first
            self.open_with_combo.addItem(f"{self.default_application.name} (default)")

        # Add other applications
        for app in self.available_applications:
            if not self.default_application or app.path != self.default_application.path:
                self.open_with_combo.addItem(app.name)

        # If no applications available, show a message
        if not self.available_applications:
            self.open_with_combo.addItem("No applications available")
            self.open_with_combo.setEnabled(False)

    def apply_permissions(self):
        """Apply the permission changes"""
        try:
            # Calculate new permission mode
            mode = 0

            # Owner permissions
            if self.owner_read_cb.isChecked():
                mode |= 0o400
            if self.owner_write_cb.isChecked():
                mode |= 0o200
            if self.owner_execute_cb.isChecked():
                mode |= 0o100

            # Group permissions
            if self.group_read_cb.isChecked():
                mode |= 0o040
            if self.group_write_cb.isChecked():
                mode |= 0o020
            if self.group_execute_cb.isChecked():
                mode |= 0o010

            # Others permissions
            if self.other_read_cb.isChecked():
                mode |= 0o004
            if self.other_write_cb.isChecked():
                mode |= 0o002
            if self.other_execute_cb.isChecked():
                mode |= 0o001

            # Apply permissions
            os.chmod(self.file_path, mode)

            # Refresh file info
            self.file_info = FileOperations.get_file_info(self.file_path)

        except OSError as e:
            QMessageBox.warning(self, "Permission Error", f"Could not change permissions:\n{str(e)}")

    def on_application_changed(self):
        """Handle application selection change"""
        # This is called when user changes the combo box selection
        # The actual change is applied when Apply button is clicked
        pass

    def get_selected_application(self) -> DesktopApplication:
        """Get the currently selected application from combo box"""
        current_index = self.open_with_combo.currentIndex()
        current_text = self.open_with_combo.currentText()

        # If it's the default application (contains "(default)")
        if "(default)" in current_text and self.default_application:
            return self.default_application

        # Otherwise, find the application by name from available applications
        for app in self.available_applications:
            if app.name == current_text:
                return app

        return None

    def apply_changes(self):
        """Apply the changes made in the Properties dialog"""
        if not self.file_info['is_file']:
            return

        # Check if application selection has changed
        selected_app = self.get_selected_application()
        if selected_app and selected_app != self.default_application:
            # User wants to change the default application
            desktop_file = os.path.basename(selected_app.path)
            success = self.app_manager.set_default_application_for_file(self.file_path, desktop_file)

            if success:
                QMessageBox.information(
                    self, "Default Application Changed",
                    f"'{selected_app.name}' is now the default application for this file type."
                )
                # Refresh the combo box to show the new default
                self.populate_open_with_applications()
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"Could not set '{selected_app.name}' as the default application."
                )
