"""
Main window for the LitterBox file manager
"""
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QToolBar, QPushButton, QTabWidget, QLineEdit,
                             QMessageBox, QInputDialog, QSplitter, QFrame,
                             QMenu, QDialog, QTabBar)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QFileSystemWatcher, QObject, QEventLoop
from PyQt6.QtGui import QKeySequence, QShortcut, QAction
from pathlib import Path
import os

from ui.path_navigator import PathNavigator
from ui.places_button import PlacesButton
from ui.file_list_view import FileListView
from core.file_operations import FileOperations
from utils.settings import Settings
from core.clipboard_manager import ClipboardManager
from core.file_transfer import FileTransferManager, ConflictDecision, suggest_rename
from typing import Optional

class FilterBar(QFrame):
    """Filter bar that appears at the bottom when typing"""

    filter_changed = pyqtSignal(str)
    filter_cleared = pyqtSignal()
    navigate_list = pyqtSignal(str)  # 'up', 'down', 'left', 'right'
    item_activated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setVisible(False)

    def setup_ui(self):
        """Setup the filter bar UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter files...")
        self.filter_edit.textChanged.connect(self.filter_changed)
        layout.addWidget(self.filter_edit)

        # Set focus policy
        self.filter_edit.setFocus()

    def show_filter(self, initial_text=""):
        """Show the filter bar with optional initial text"""
        self.filter_edit.setText(initial_text)
        self.setVisible(True)
        self.filter_edit.setFocus()

    def hide_filter(self):
        """Hide the filter bar and clear text"""
        self.filter_edit.clear()
        self.setVisible(False)
        self.filter_cleared.emit()

    def keyPressEvent(self, event):
        """Handle key events in filter bar"""
        if event.key() == Qt.Key.Key_Escape:
            self.hide_filter()
        elif event.key() == Qt.Key.Key_Up:
            self.navigate_list.emit('up')
        elif event.key() == Qt.Key.Key_Down:
            self.navigate_list.emit('down')
        elif event.key() == Qt.Key.Key_Left:
            self.navigate_list.emit('left')
        elif event.key() == Qt.Key.Key_Right:
            self.navigate_list.emit('right')
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.item_activated.emit()
        else:
            super().keyPressEvent(event)

class FileTab(QWidget):
    """Individual LitterBox tab"""

    path_changed = pyqtSignal(str)  # Emitted when current path changes

    def __init__(self, initial_path=None, parent=None):
        super().__init__(parent)
        self.current_path = initial_path or str(Path.home())
        # Unique watch id (use object id to avoid collisions) for FileWatcherManager
        self._watch_id = f"tab-{id(self)}"
        # Qt native watcher (more reliable on some systems than watchdog alone)
        self._dir_watcher = QFileSystemWatcher(self)
        self._dir_watcher.directoryChanged.connect(self._on_directory_changed)
        # Debounce timer for refresh
        self._watch_refresh_timer = QTimer(self)
        self._watch_refresh_timer.setSingleShot(True)
        self._watch_refresh_timer.setInterval(250)
        self._watch_refresh_timer.timeout.connect(self._on_debounced_refresh)
        # Periodic polling fallback (in case native events miss something)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)  # 2s lightweight polling
        self._poll_timer.timeout.connect(self._poll_refresh_if_needed)
        self._poll_timer.start()
        self._last_snapshot = set()

        self.setup_ui()
        self.setup_connections()

        # Navigate to initial path
        self.navigate_to(self.current_path)

    def setup_ui(self):
        """Setup the tab UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # File list view (path navigator moved to main toolbar)
        self.file_list = FileListView()
        layout.addWidget(self.file_list)

        # Filter bar (hidden by default)
        self.filter_bar = FilterBar()
        layout.addWidget(self.filter_bar)

    def setup_connections(self):
        """Setup signal connections"""
        self.file_list.item_double_clicked.connect(self.on_item_activated)
        self.file_list.context_menu_requested.connect(self.show_context_menu)

        # Filter connections
        self.filter_bar.filter_changed.connect(self.apply_filter)
        self.filter_bar.filter_cleared.connect(self.clear_filter)
        self.filter_bar.navigate_list.connect(self.handle_filter_navigation)
        self.filter_bar.item_activated.connect(self.activate_current_item)

        # Connect filter request from file list
        self.file_list.filter_requested.connect(self.on_filter_requested)

        # Connect parent navigation request
        self.file_list.parent_navigation_requested.connect(self.navigate_to_parent_and_select)

        # Connect rename request from F2 key
        self.file_list.rename_requested.connect(self.rename_item)

    def navigate_to(self, path):
        """Navigate to the specified path"""
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_dir():
            self.current_path = str(path_obj.resolve())
            self.file_list.set_path(self.current_path)
            # Update QFileSystemWatcher path list (single path per tab)
            try:
                existing_paths = self._dir_watcher.directories()
                if existing_paths:
                    self._dir_watcher.removePaths(existing_paths)
                self._dir_watcher.addPath(self.current_path)
            except Exception:
                pass
            # Clear and hide filter when navigating to a new directory
            if self.filter_bar.isVisible():
                self.filter_bar.hide_filter()
            # Emit signal for tab title update and toolbar path update
            self.path_changed.emit(self.current_path)
            # Ensure file list has focus for keyboard navigation
            self.file_list.setFocus()
            # Record snapshot after navigation
            self._update_snapshot()

    def _on_debounced_refresh(self):
        """Execute a refresh after debounce interval and update snapshot."""
        self.file_list.refresh()
        self._update_snapshot()

    def _on_directory_changed(self, changed_path):
        """Handle directory change events (debounced)."""
        # Restart debounce timer unconditionally for reliability
        self._watch_refresh_timer.start()
        # Snapshot will be updated inside the debounced refresh handler

    def _poll_refresh_if_needed(self):
        """Periodic fallback to detect missed changes by comparing snapshots."""
        if not self.current_path:
            return
        try:
            from core.file_operations import FileOperations
            entries = FileOperations.list_directory(self.current_path)
            names = {e['name'] for e in entries}
            if names != self._last_snapshot:
                # Something changed that we didn't catch; refresh immediately
                self.file_list.refresh()
                self._last_snapshot = names
        except Exception:
            pass

    def _update_snapshot(self):
        try:
            from core.file_operations import FileOperations
            if self.current_path:
                entries = FileOperations.list_directory(self.current_path)
                self._last_snapshot = {e['name'] for e in entries}
        except Exception:
            pass

    def on_item_activated(self, path, is_directory):
        """Handle item activation (double-click or enter)"""
        if is_directory:
            self.navigate_to(path)
        else:
            # Check if file is executable
            if FileOperations.is_executable(path):
                self.handle_executable_activation(path)
            else:
                # Open file with default application
                FileOperations.open_with_default(path)

    def handle_executable_activation(self, path):
        """Handle activation of executable files with smart detection"""
        filename = os.path.basename(path)
        executable_type = FileOperations.get_executable_type(path)

        if executable_type == 'gui':
            # GUI applications - run directly without asking
            success, error = FileOperations.run_executable(path)
            if not success:
                QMessageBox.warning(self, "Run Failed", f"Could not run executable:\n{error}")
            return

        # For console applications and scripts, show dialog with options
        type_description = {
            'console': 'console application',
            'script': 'script',
            None: 'executable file'
        }.get(executable_type, 'executable file')

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Executable File")
        dialog.setText(f"'{filename}' is a {type_description}.")
        dialog.setInformativeText("How would you like to run it?")

        # Add buttons based on executable type
        run_terminal_button = dialog.addButton("Run in Terminal", QMessageBox.ButtonRole.ActionRole)
        run_direct_button = dialog.addButton("Run Directly", QMessageBox.ButtonRole.ActionRole)

        # Only add edit button if the file appears to be a text file
        edit_button = None
        if FileOperations.is_text_file(path):
            edit_button = dialog.addButton("Edit", QMessageBox.ButtonRole.ActionRole)

        cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        # Set default button based on type
        if executable_type == 'script':
            dialog.setDefaultButton(run_terminal_button)
        else:
            dialog.setDefaultButton(run_direct_button)

        # Show dialog and handle response
        dialog.exec()
        clicked_button = dialog.clickedButton()

        if clicked_button == run_terminal_button:
            success, error = FileOperations.run_executable(path, force_terminal=True)
            if not success:
                QMessageBox.warning(self, "Run Failed", f"Could not run executable:\n{error}")
        elif clicked_button == run_direct_button:
            success, error = FileOperations.run_executable_direct(path)
            if not success:
                QMessageBox.warning(self, "Run Failed", f"Could not run executable:\n{error}")
        elif clicked_button == edit_button:
            success, error = FileOperations.open_with_editor(path)
            if not success:
                QMessageBox.warning(self, "Edit Failed", f"Could not open editor:\n{error}")

    def show_context_menu(self, path, position):
        """Show context menu for file/folder"""
        menu = QMenu(self)

        # Open
        open_action = menu.addAction("Open")
        if FileOperations.is_executable(path):
            open_action.triggered.connect(lambda: self.handle_executable_activation(path))
        else:
            open_action.triggered.connect(lambda: FileOperations.open_with_default(path))

        # Open with...
        open_with_action = menu.addAction("Open with...")
        # Delegate to MainWindow if available
        open_with_action.triggered.connect(lambda: self.parent().show_open_with_dialog(path) if self.parent() and hasattr(self.parent(), 'show_open_with_dialog') else None)

        menu.addSeparator()

        # Rename
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self.rename_item(path))

        menu.addSeparator()

        # Move to trash
        trash_action = menu.addAction("Move to Trash")
        trash_action.triggered.connect(lambda: self.move_to_trash(path))

        # Delete
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_item(path))

        menu.addSeparator()

        # Properties
        properties_action = menu.addAction("Properties")
        properties_action.triggered.connect(lambda: self.parent().show_properties(path) if self.parent() and hasattr(self.parent(), 'show_properties') else None)

        # Clipboard actions
        menu.addSeparator()
        # Resolve main window (safer than parent() for nested widgets)
        main_window = self.window()

        def _do_copy():
            if main_window and hasattr(main_window, 'copy_selection'):
                main_window.copy_selection(False)

        def _do_cut():
            if main_window and hasattr(main_window, 'copy_selection'):
                main_window.copy_selection(True)

        def _do_paste():
            if main_window and hasattr(main_window, 'paste_into_current'):
                main_window.paste_into_current()

        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(_do_copy)
        cut_action = menu.addAction("Cut")
        cut_action.triggered.connect(_do_cut)
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(_do_paste)

        menu.exec(position)

    def rename_item(self, path):
        """Rename file or folder"""
        current_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(
            self, "Rename", f"Rename '{current_name}' to:", text=current_name
        )

        if ok and new_name and new_name != current_name:
            success, result = FileOperations.rename_item(path, new_name)
            if not success:
                QMessageBox.warning(self, "Rename Failed", f"Could not rename item:\n{result}")
            else:
                self.file_list.refresh()
                self._update_snapshot()

    def move_to_trash(self, path):
        """Move item to trash"""
        success, result = FileOperations.move_to_trash(path)
        if not success:
            QMessageBox.warning(self, "Trash Failed", f"Could not move to trash:\n{result}")
        else:
            self.file_list.refresh()
            self._update_snapshot()

    def delete_item(self, path):
        """Delete item permanently"""
        name = os.path.basename(path)
        reply = QMessageBox.question(
            self, "Delete Permanently",
            f"Are you sure you want to permanently delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, result = FileOperations.delete_item(path)
            if not success:
                QMessageBox.warning(self, "Delete Failed", f"Could not delete item:\n{result}")
            else:
                self.file_list.refresh()
                self._update_snapshot()

    # Removed show_properties & show_open_with_dialog from FileTab; these live on MainWindow

    # open_with_application and on_default_application_changed now live on MainWindow

    def apply_filter(self, filter_text):
        """Apply filter to file list"""
        if not filter_text:
            self.clear_filter()
            return

        # Apply filter through the proxy model using regex for partial matching
        from PyQt6.QtCore import QRegularExpression
        regex = QRegularExpression(filter_text, QRegularExpression.PatternOption.CaseInsensitiveOption)
        self.file_list.proxy_model.setFilterRegularExpression(regex)

        # Select first visible item
        if self.file_list.proxy_model.rowCount() > 0:
            first_index = self.file_list.proxy_model.index(0, 0)
            if first_index.isValid():
                self.file_list.setCurrentIndex(first_index)

    def clear_filter(self):
        """Clear the filter"""
        # Clear filter on the proxy model
        from PyQt6.QtCore import QRegularExpression
        self.file_list.proxy_model.setFilterRegularExpression(QRegularExpression(""))

        # Select first item if none selected
        self.file_list.select_first_item_if_none_selected()

        # Return focus to file list for keyboard navigation
        self.file_list.setFocus()

    def handle_filter_navigation(self, direction):
        """Handle navigation while filter is active"""
        current_index = self.file_list.currentIndex()
        if not current_index.isValid():
            return

        if direction == 'up':
            # Move to previous item
            if current_index.row() > 0:
                new_index = self.file_list.proxy_model.index(current_index.row() - 1, 0)
                if new_index.isValid():
                    self.file_list.setCurrentIndex(new_index)
        elif direction == 'down':
            # Move to next item
            if current_index.row() < self.file_list.proxy_model.rowCount() - 1:
                new_index = self.file_list.proxy_model.index(current_index.row() + 1, 0)
                if new_index.isValid():
                    self.file_list.setCurrentIndex(new_index)

    def activate_current_item(self):
        """Activate the currently selected item from filter"""
        current_index = self.file_list.currentIndex()
        if current_index.isValid():
            # Map to source model to get data
            source_index = self.file_list.proxy_model.mapToSource(current_index)
            if source_index.isValid():
                name_item = self.file_list.source_model.item(source_index.row(), 0)
                if name_item:
                    is_directory = name_item.data(Qt.ItemDataRole.UserRole + 1)
                    self.file_list.on_item_double_clicked(current_index)
                    # Only hide filter if navigating to a directory
                    if is_directory:
                        self.filter_bar.hide_filter()

    def on_filter_requested(self, character):
        """Handle filter request from file list"""
        self.filter_bar.show_filter(character)

    def navigate_to_parent_and_select(self, parent_path, folder_to_select):
        """Navigate to parent directory and select the specified folder"""
        self.navigate_to(parent_path)
        # Use a timer to select the folder after the navigation completes
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(10, lambda: self.file_list.select_item_by_name(folder_to_select))

    def create_new_folder(self):
        """Create a new folder in current directory"""
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            success, result = FileOperations.create_folder(self.current_path, name)
            if not success:
                QMessageBox.warning(self, "Create Folder Failed", f"Could not create folder:\n{result}")
            else:
                self.file_list.refresh()
                self._update_snapshot()
                self.file_list.select_item_by_name(name)

    def create_new_file(self):
        """Create a new file in current directory"""
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            success, result = FileOperations.create_file(self.current_path, name)
            if not success:
                QMessageBox.warning(self, "Create File Failed", f"Could not create file:\n{result}")
            else:
                self.file_list.refresh()
                self._update_snapshot()
                self.file_list.select_item_by_name(name)

class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.transfer_manager = FileTransferManager()
        # Signal-based conflict dialog marshaling
        # We'll create a lightweight helper QObject living in the GUI thread to show the dialog.
        class _ConflictBridge(QObject):
            request = pyqtSignal(object, object, object)  # existing Path, source Path, completion callback
        self._conflict_bridge = _ConflictBridge()
        self._conflict_bridge.request.connect(self._show_conflict_dialog)
        # Debounced refresh timer for file copy progress (avoids rapid repaint churn)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)  # ms
        self._refresh_timer.timeout.connect(self._refresh_visible_tab)

        # Track recently used tab order (most recent first) for Ctrl+Tab switching
        self.recent_tab_order = []

        self.setup_ui()
        self.setup_shortcuts()
        self.restore_settings()

    def setup_ui(self):
        """Setup the main window UI"""
        self.setWindowTitle("LitterBox")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.create_toolbar()

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        # Make tabs reorderable via drag & drop
        bar = self.tab_widget.tabBar()
        # Guard for static analysis: ensure bar is a QTabBar instance
        if isinstance(bar, QTabBar):  # pragma: no branch
            try:
                bar.setMovable(True)  # type: ignore[attr-defined]
                # Update recent tab order bookkeeping when tabs are moved
                bar.tabMoved.connect(self.on_tab_moved)  # type: ignore[attr-defined]
            except Exception:
                # Fail silently if platform/Qt version does not support movable tabs
                pass
        layout.addWidget(self.tab_widget)

        # Transfer panel
        from ui.transfer_panel import TransferPanel
        self.transfer_panel = TransferPanel()
        self.transfer_panel.setVisible(False)
        layout.addWidget(self.transfer_panel)
        self.transfer_manager.task_added.connect(self._on_task_added)

        # Create initial tab
        self.add_new_tab()

    def create_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Places button
        self.places_button = PlacesButton()
        self.places_button.place_selected.connect(self.navigate_to_place)
        toolbar.addWidget(self.places_button)

        toolbar.addSeparator()

        # Path navigator in toolbar
        self.toolbar_path_navigator = PathNavigator()
        self.toolbar_path_navigator.path_changed.connect(self.navigate_current_tab_to_path)
        toolbar.addWidget(self.toolbar_path_navigator)

        toolbar.addSeparator()

        # New folder button
        new_folder_btn = QPushButton("New Folder")
        new_folder_btn.clicked.connect(self.create_new_folder)
        toolbar.addWidget(new_folder_btn)

        # New file button
        new_file_btn = QPushButton("New File")
        new_file_btn.clicked.connect(self.create_new_file)
        toolbar.addWidget(new_file_btn)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+L: Toggle path edit mode
        ctrl_l = QShortcut(QKeySequence("Ctrl+L"), self)
        ctrl_l.activated.connect(self.toggle_path_edit)

        # Ctrl+W: Close current tab
        ctrl_w = QShortcut(QKeySequence("Ctrl+W"), self)
        ctrl_w.activated.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))

        # Ctrl+T: New tab
        ctrl_t = QShortcut(QKeySequence("Ctrl+T"), self)
        ctrl_t.activated.connect(self.add_new_tab)

        # Alt+Enter: Properties (standard in many file managers)
        alt_enter = QShortcut(QKeySequence("Alt+Return"), self)
        alt_enter.activated.connect(self.show_current_properties)

        # Ctrl+Enter: Open with dialog
        ctrl_enter = QShortcut(QKeySequence("Ctrl+Return"), self)
        ctrl_enter.activated.connect(self.show_current_open_with)

        # Ctrl+PageUp: Switch to left tab
        ctrl_page_up = QShortcut(QKeySequence("Ctrl+PgUp"), self)
        ctrl_page_up.activated.connect(self.switch_to_left_tab)

        # Ctrl+PageDown: Switch to right tab
        ctrl_page_down = QShortcut(QKeySequence("Ctrl+PgDown"), self)
        ctrl_page_down.activated.connect(self.switch_to_right_tab)

        # Ctrl+Tab: Switch tabs by recently used order
        ctrl_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        ctrl_tab.activated.connect(self.switch_to_recent_tab)

        # Copy/Cut/Paste
        sc_copy = QShortcut(QKeySequence.StandardKey.Copy, self)
        sc_copy.activated.connect(self.copy_selection)
        sc_cut = QShortcut(QKeySequence.StandardKey.Cut, self)
        sc_cut.activated.connect(lambda: self.copy_selection(cut=True))
        sc_paste = QShortcut(QKeySequence.StandardKey.Paste, self)
        sc_paste.activated.connect(self.paste_into_current)

    def add_new_tab(self, path=None):
        """Add a new tab"""
        # If no path provided, use current tab's path
        if path is None:
            current_tab = self.get_current_tab()
            if current_tab:
                path = current_tab.current_path

        tab = FileTab(path)

        # Tab title based on path
        if path:
            title = os.path.basename(path) or path
        else:
            title = "Home"

        index = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(index)

        # Connect path change signal to update tab title and toolbar path
        tab.path_changed.connect(lambda new_path, t=tab: self.update_tab_title_for_tab(t, new_path))
        tab.path_changed.connect(lambda new_path, t=tab: self.update_toolbar_path_if_current(t, new_path))

        # Update tab visibility
        self.update_tab_visibility()

        # Update toolbar path navigator to show the new tab's path
        self.toolbar_path_navigator.set_path(tab.current_path)

        return tab

    def close_tab(self, index):
        """Close a tab"""
        if self.tab_widget.count() > 1:
            # Update recent tab order before closing
            self.update_recent_tab_order_on_close(index)
            self.tab_widget.removeTab(index)
            self.update_tab_visibility()
        # Don't close the last tab

    def update_tab_visibility(self):
        """Show/hide tab bar based on number of tabs"""
        bar = self.tab_widget.tabBar()
        if isinstance(bar, QTabBar):  # pragma: no branch
            bar.setVisible(self.tab_widget.count() > 1)  # type: ignore[attr-defined]

    def update_tab_title_for_tab(self, tab, path):
        """Update the title for a specific tab widget"""
        tab_index = self.tab_widget.indexOf(tab)
        if tab_index >= 0:
            title = os.path.basename(path) or path
            if title == "":  # Root directory
                title = "/"
            self.tab_widget.setTabText(tab_index, title)

    def update_toolbar_path_if_current(self, tab, path):
        """Update toolbar path navigator if this is the current tab"""
        current_tab = self.get_current_tab()
        if current_tab == tab:
            self.toolbar_path_navigator.set_path(path)

    def on_tab_changed(self, index):
        """Handle tab change - update toolbar path navigator"""
        if index >= 0:
            # Update recently used tab order
            self.update_recent_tab_order(index)
            tab_widget = self.tab_widget.widget(index)
            if isinstance(tab_widget, FileTab):
                self.toolbar_path_navigator.set_path(tab_widget.current_path)
                tab_widget.file_list.setFocus()

    def navigate_current_tab_to_path(self, path):
        """Navigate current tab to specified path (from toolbar path navigator)"""
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.navigate_to(path)

    def get_current_tab(self) -> Optional['FileTab']:
        """Get the current active tab as FileTab (None if not a FileTab)"""
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, FileTab) else None

    def navigate_to_place(self, path):
        """Navigate current tab to a place"""
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.navigate_to(path)

    def toggle_path_edit(self):
        """Toggle path edit mode in toolbar path navigator"""
        self.toolbar_path_navigator.toggle_edit_mode()

    def create_new_folder(self):
        """Create new folder in current tab"""
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.create_new_folder()

    def create_new_file(self):
        """Create new file in current tab"""
        current_tab = self.get_current_tab()
        if current_tab:
            current_tab.create_new_file()

    def show_current_open_with(self):
        """Show Open with dialog for currently selected item"""
        current_tab = self.get_current_tab()
        if current_tab:
            selected_items = current_tab.file_list.get_selected_items()
            if selected_items:
                self.show_open_with_dialog(selected_items[0])

    def show_current_properties(self):
        """Show properties for currently selected item"""
        current_tab = self.get_current_tab()
        if current_tab:
            selected_items = current_tab.file_list.get_selected_items()
            if selected_items:
                self.show_properties(selected_items[0])

    def show_properties(self, path):
        """Show properties dialog"""
        from ui.properties_dialog import PropertiesDialog
        dialog = PropertiesDialog(path, self)
        dialog.exec()

    def show_open_with_dialog(self, path):
        """Show Open with dialog"""
        from ui.application_selection_dialog import ApplicationSelectionDialog
        dialog = ApplicationSelectionDialog(path, self)
        dialog.application_selected.connect(lambda app: self.open_with_application(path, app))
        dialog.default_changed.connect(lambda app: self.on_default_application_changed(path, app))
        dialog.exec()

    def open_with_application(self, path, application):
        """Open file with the specified application"""
        from core.application_manager import ApplicationManager
        app_manager = ApplicationManager()
        success, error = app_manager.open_with_application(path, application)
        if not success:
            QMessageBox.warning(self, "Open Failed", f"Could not open with {application.name}:\n{error}")

    def on_default_application_changed(self, path, application):
        """Handle default application change (placeholder)"""
        # Change already applied system-wide; nothing extra needed.
        pass

    def switch_to_left_tab(self):
        """Switch to the tab on the left (previous tab)"""
        current_index = self.tab_widget.currentIndex()
        if current_index > 0:
            self.tab_widget.setCurrentIndex(current_index - 1)
        elif self.tab_widget.count() > 1:
            # Wrap around to the last tab
            self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

    def switch_to_right_tab(self):
        """Switch to the tab on the right (next tab)"""
        current_index = self.tab_widget.currentIndex()
        if current_index < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current_index + 1)
        elif self.tab_widget.count() > 1:
            # Wrap around to the first tab
            self.tab_widget.setCurrentIndex(0)

    def switch_to_recent_tab(self):
        """Switch to the most recently used tab (Ctrl+Tab behavior)"""
        if len(self.recent_tab_order) < 2:
            return  # Need at least 2 tabs to switch

        # Get the most recent tab that isn't the current one
        current_index = self.tab_widget.currentIndex()
        for tab_index in self.recent_tab_order:
            if tab_index != current_index and tab_index < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(tab_index)
                return

    def update_recent_tab_order(self, index):
        """Update the recently used tab order"""
        # Remove the index if it's already in the list
        if index in self.recent_tab_order:
            self.recent_tab_order.remove(index)

        # Add the index at the beginning (most recent)
        self.recent_tab_order.insert(0, index)

        # Keep only the last few tabs in history (prevent unlimited growth)
        max_history = 10
        self.recent_tab_order = self.recent_tab_order[:max_history]

    def update_recent_tab_order_on_close(self, closed_index):
        """Update recent tab order when a tab is closed"""
        # Remove the closed tab from the order
        if closed_index in self.recent_tab_order:
            self.recent_tab_order.remove(closed_index)

        # Adjust indices for tabs that come after the closed tab
        # (their indices will shift down by 1)
        for i in range(len(self.recent_tab_order)):
            if self.recent_tab_order[i] > closed_index:
                self.recent_tab_order[i] -= 1

    def keyPressEvent(self, a0):  # type: ignore[override]
        """Handle global key events (delegate to base)."""
        super().keyPressEvent(a0)

    def on_tab_moved(self, from_index: int, to_index: int):
        """Adjust internal recent_tab_order indices after a drag reorder.

        When a tab is moved, intermediate tabs shift left/right. We adjust
        stored indices so Ctrl+Tab recent switching keeps working correctly.
        """
        if from_index == to_index:
            return

        updated = []
        for idx in self.recent_tab_order:
            if idx == from_index:
                updated.append(to_index)
            elif from_index < to_index:
                # Moved right: tabs between (from_index, to_index] shift left by 1
                if from_index < idx <= to_index:
                    updated.append(idx - 1)
                else:
                    updated.append(idx)
            else:  # from_index > to_index
                # Moved left: tabs between [to_index, from_index) shift right by 1
                if to_index <= idx < from_index:
                    updated.append(idx + 1)
                else:
                    updated.append(idx)

        # Deduplicate while preserving order (in rare pathological cases)
        seen = set()
        deduped = []
        for val in updated:
            if val not in seen:
                seen.add(val)
                deduped.append(val)
        self.recent_tab_order = deduped

    # ---- Copy/Cut/Paste ----
    def copy_selection(self, cut: bool = False):
        current_tab = self.get_current_tab()
        if not current_tab:
            return
        selected = current_tab.file_list.get_selected_items()
        if not selected:
            return
        ClipboardManager.set_files(selected, operation='cut' if cut else 'copy')

    def paste_into_current(self):
        current_tab = self.get_current_tab()
        if not current_tab:
            return
        clip = ClipboardManager.get_files()
        if not clip or not clip.paths:
            return
        dest_dir = current_tab.current_path
        move = (clip.operation == 'cut')
        task = self.transfer_manager.start_transfer(
            clip.paths,
            dest_dir,
            move=move,
            conflict_callback=self._conflict_handler
        )
        # Debounced refresh trigger on progress + on finish (final state)
        task.file_progress.connect(self._schedule_refresh)
        task.finished.connect(lambda *_: self._schedule_refresh(""))
        self.transfer_panel.setVisible(True)

    def _conflict_handler(self, existing, source):
        """Called in worker thread: synchronously obtain a ConflictDecision via GUI thread signal."""
        import threading
        result_holder = {}
        done = threading.Event()

        def complete(decision: ConflictDecision):
            result_holder['d'] = decision
            done.set()

        # Emit to GUI thread
        self._conflict_bridge.request.emit(existing, source, complete)

        # Wait (blocking this worker) until decision made or cancellation
        while not done.is_set():
            done.wait(0.05)
            if self.transfer_manager is None:
                break
        return result_holder.get('d', ConflictDecision('skip'))

    def _show_conflict_dialog(self, existing, source, complete_cb):
        from ui.conflict_dialog import ConflictDialog
        dlg = ConflictDialog(existing.name, self, source_path=source, existing_path=existing)
        dlg.exec()
        if dlg.decision == 'overwrite':
            complete_cb(ConflictDecision('overwrite', apply_all=dlg.apply_all))
            return
        if dlg.decision == 'rename':
            # Use user-entered new name if provided, else fallback to internal suggestion
            if dlg.new_name:
                from pathlib import Path
                complete_cb(ConflictDecision('rename', new_path=existing.parent / dlg.new_name))
            else:
                complete_cb(ConflictDecision('rename', new_path=suggest_rename(existing)))
            return
        if dlg.decision == 'skip':
            complete_cb(ConflictDecision('skip'))
            return
        if dlg.decision == 'cancel':
            complete_cb(ConflictDecision('cancel'))
            return
        complete_cb(ConflictDecision('skip'))

    def _on_task_added(self, task):
        self.transfer_panel.setVisible(True)
        self.transfer_panel.add_task(task)
        task.finished.connect(lambda *_: self._maybe_hide_panel())

    def _maybe_hide_panel(self):
        if not self.transfer_manager.active_tasks():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self.transfer_panel.setVisible(False) if not self.transfer_manager.active_tasks() else None)

    # ---- Debounced UI refresh helpers ----
    def _schedule_refresh(self, _path: str):
        # Only schedule once per interval
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _refresh_visible_tab(self):
        tab = self.get_current_tab()
        if tab and hasattr(tab, 'file_list'):
            tab.file_list.refresh()

    def restore_settings(self):
        """Restore window settings"""
        geometry = self.settings.get("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def save_settings(self):
        """Save window settings"""
        self.settings.set("window_geometry", self.saveGeometry())

    def closeEvent(self, a0):  # type: ignore[override]
        """Handle window close event and persist settings."""
        self.save_settings()
        super().closeEvent(a0)
