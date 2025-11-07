"""
Properties dialog for files and folders
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QTabWidget, QWidget, QFormLayout, QCheckBox,
                             QComboBox, QGroupBox, QPushButton, QTextEdit,
                             QGridLayout, QSpacerItem, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QMovie
from core.file_operations import FileOperations
from core.application_manager import ApplicationManager, DesktopApplication
from pathlib import Path
import os
import subprocess
import time

class FolderSizeWorker(QObject):
    """Worker that computes folder size recursively with incremental updates.

    NOTE: Using `object` signal type instead of `int` because PyQt's `int` maps to
    C++ int (typically 32-bit). Large folders can exceed 2^31-1 bytes (>2GB) and
    would overflow, producing negative intermediate values in the UI. Emitting a
    Python object preserves the full arbitrary-precision integer size safely.
    """
    # Use Python object for arbitrary large integers to avoid 32-bit overflow
    progress = pyqtSignal(object)      # cumulative size in bytes (int)
    done = pyqtSignal(object)          # final size in bytes (int)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = 0
        last_emit = 0.0
        try:
            for root, dirs, files in os.walk(self.path, followlinks=False):
                if self._stop:
                    break
                # Optionally prune dirs if needed (skip large mounts, etc.)
                for f in files:
                    if self._stop:
                        break
                    fp = os.path.join(root, f)
                    try:
                        if not os.path.islink(fp):
                            total += os.path.getsize(fp)
                    except OSError:
                        continue
                    now = time.time()
                    # Throttle UI updates to ~20/sec
                    if now - last_emit >= 0.05:
                        last_emit = now
                        self.progress.emit(total)
            # Emit final size
            self.done.emit(total)
        except Exception:
            # Still emit what we have to avoid spinner hanging
            self.done.emit(total)

class PropertiesDialog(QDialog):
    """Dialog showing file/folder properties"""

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_info = FileOperations.get_file_info(file_path)
        self.app_manager = ApplicationManager()
        if self.file_info and self.file_info.get('is_file'):
            self.file_info['mime_type'] = self.app_manager.get_mime_type(self.file_path)
        else:
            self.file_info['mime_type'] = 'inode/directory'

        self.available_applications = []
        self.default_application = None

        # Folder size async members
        self.size_thread: QThread | None = None
        self.folder_size_worker: FolderSizeWorker | None = None
        self._last_folder_size = 0
        self.size_value_label: QLabel | None = None
        self.size_spinner_label: QLabel | None = None
        self.spinner_movie: QMovie | None = None

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

        # Mime type
        if self.file_info.get('mime_type'):
            info_layout.addRow("MIME type:", QLabel(self.file_info['mime_type']))

        # Location
        location = str(Path(self.file_path).parent)
        info_layout.addRow("Location:", QLabel(location))

        # Size row (modified to support async folder size)
        if self.file_info['is_dir']:
            # Container for size value + spinner
            size_row_widget = QWidget()
            size_row_layout = QHBoxLayout(size_row_widget)
            size_row_layout.setContentsMargins(0, 0, 0, 0)

            self.size_value_label = QLabel("Calculating...")
            self.size_spinner_label = QLabel()
            # Try loading spinner.gif placed alongside this file
            spinner_path = os.path.join(os.path.dirname(__file__), "spinner.gif")
            if os.path.exists(spinner_path):
                self.spinner_movie = QMovie(spinner_path)
                if self.spinner_movie.isValid():
                    self.size_spinner_label.setMovie(self.spinner_movie)
                    self.spinner_movie.start()
                else:
                    self.size_spinner_label.setText("...")
            else:
                self.size_spinner_label.setText("...")
            size_row_layout.addWidget(self.size_value_label)
            size_row_layout.addWidget(self.size_spinner_label)
            size_row_layout.addStretch()
            info_layout.addRow("Size:", size_row_widget)
            # Start async calculation
            self.start_folder_size_calculation()
        else:
            size_text = FileOperations.format_size(self.file_info['size'])
            self.size_value_label = QLabel(size_text)
            info_layout.addRow("Size:", self.size_value_label)

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

    def start_folder_size_calculation(self):
        """Start background recursive folder size computation."""
        if not self.file_info.get('is_dir'):
            return
        # Safety: avoid duplicate threads
        if self.size_thread and self.size_thread.isRunning():
            return

        self.folder_size_worker = FolderSizeWorker(self.file_path)
        self.size_thread = QThread(self)
        self.folder_size_worker.moveToThread(self.size_thread)

        self.size_thread.started.connect(self.folder_size_worker.run)
        self.folder_size_worker.progress.connect(self.on_folder_size_progress)
        self.folder_size_worker.done.connect(self.on_folder_size_done)
        self.folder_size_worker.done.connect(lambda _: self.size_thread.quit())

        # Ensure cleanup
        self.size_thread.finished.connect(self.size_thread.deleteLater)
        self.size_thread.start()

    def on_folder_size_progress(self, total_bytes: int):
        """Incremental update for folder size."""
        self._last_folder_size = total_bytes
        if self.size_value_label:
            self.size_value_label.setText(FileOperations.format_size(total_bytes))

    def on_folder_size_done(self, final_bytes: int):
        """Finalize folder size display."""
        self._last_folder_size = final_bytes
        if self.size_value_label:
            self.size_value_label.setText(FileOperations.format_size(final_bytes))
        if self.size_spinner_label:
            self.size_spinner_label.hide()
        if self.spinner_movie:
            self.spinner_movie.stop()

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
        if not self.file_info.get('is_file'):
            return
        self.open_with_combo.clear()

        # Get default application
        self.default_application = self.app_manager.get_default_application(self.file_path)

        # Get ranked applications if available
        try:
            self.available_applications = self.app_manager.get_ranked_applications_for_file(self.file_path)
        except AttributeError:
            self.available_applications = self.app_manager.get_applications_for_file(self.file_path)

        if self.default_application:
            self.open_with_combo.addItem(f"{self.default_application.name} (default)")

        for app in self.available_applications:
            if not self.default_application or app.path != self.default_application.path:
                self.open_with_combo.addItem(app.name)

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
        pass

    def get_selected_application(self) -> DesktopApplication:
        """Get the currently selected application from combo box"""
        if not self.file_info.get('is_file'):
            return None
        current_text = self.open_with_combo.currentText()

        if "(default)" in current_text and self.default_application:
            return self.default_application

        for app in self.available_applications:
            if app.name == current_text:
                return app

        return None

    def apply_changes(self):
        """Apply the changes made in the Properties dialog"""
        if not self.file_info['is_file']:
            return

        selected_app = self.get_selected_application()
        if selected_app and selected_app != self.default_application:
            desktop_file = os.path.basename(selected_app.path)
            success = self.app_manager.set_default_application_for_file(self.file_path, desktop_file)

            if success:
                QMessageBox.information(
                    self, "Default Application Changed",
                    f"'{selected_app.name}' is now the default application for this file type."
                )
                self.populate_open_with_applications()
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"Could not set '{selected_app.name}' as the default application."
                )

    def closeEvent(self, event):
        """Ensure background worker stops when dialog closes."""
        if self.folder_size_worker:
            self.folder_size_worker.stop()
        if self.size_thread and self.size_thread.isRunning():
            # Gracefully ask thread to finish
            self.size_thread.quit()
            self.size_thread.wait(500)
        super().closeEvent(event)
