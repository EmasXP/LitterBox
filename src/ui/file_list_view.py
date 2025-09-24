"""
File list view widget - displays files and folders in a detailed list
"""
from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView,
                             QAbstractItemView, QMenu, QTreeView)
from PyQt6.QtCore import pyqtSignal, Qt, QMimeData, QSortFilterProxyModel, QEvent, QTimer
from PyQt6.QtGui import QIcon, QDrag, QStandardItemModel, QStandardItem
from core.file_operations import FileOperations
from datetime import datetime
import os

class FileSortProxyModel(QSortFilterProxyModel):
    """Custom proxy model that prioritizes directories over files"""

    def filterAcceptsRow(self, source_row, source_parent):
        """Custom filtering logic"""
        if not self.filterRegularExpression().pattern():
            return True  # No filter set, accept all

        source_model = self.sourceModel()
        if not source_model:
            return True

        # Get the name item (column 0)
        name_index = source_model.index(source_row, 0, source_parent)
        if not name_index.isValid():
            return True

        # Get the file path and extract just the filename
        name_item = source_model.item(source_row, 0)
        if not name_item:
            return True

        file_path = name_item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return True

        filename = os.path.basename(file_path)

        # Check if filename contains the filter text (case insensitive)
        filter_text = self.filterRegularExpression().pattern().lower()
        return filter_text in filename.lower()

    def lessThan(self, left, right):
        """Compare two items for sorting, always prioritizing directories"""
        source_model = self.sourceModel()

        if not source_model or not left.isValid() or not right.isValid():
            return super().lessThan(left, right)

        # Get the name items (column 0) to access the directory information
        left_name_index = source_model.index(left.row(), 0)
        right_name_index = source_model.index(right.row(), 0)

        if not left_name_index.isValid() or not right_name_index.isValid():
            return super().lessThan(left, right)

        # Get directory status from the name items
        left_is_dir = source_model.data(left_name_index, Qt.ItemDataRole.UserRole + 1)
        right_is_dir = source_model.data(right_name_index, Qt.ItemDataRole.UserRole + 1)

        # Convert None to False for safety
        left_is_dir = bool(left_is_dir)
        right_is_dir = bool(right_is_dir)

        # Check current sort order
        current_sort_order = self.sortOrder()

        # If one is a directory and the other isn't, directory comes first
        # We need to account for sort order here
        if left_is_dir and not right_is_dir:
            # Directory should always come first, regardless of sort order
            # In ascending order: return True (left < right)
            # In descending order: return False (left > right) so that right comes after left
            return current_sort_order == Qt.SortOrder.AscendingOrder
        elif not left_is_dir and right_is_dir:
            # File vs Directory: directory should come first
            # In ascending order: return False (left >= right)
            # In descending order: return True (left < right) so that right comes before left
            return current_sort_order == Qt.SortOrder.DescendingOrder

        # Both are the same type (both directories or both files)
        # For the Modified column (column 2), use the datetime data for proper sorting
        if left.column() == 2 and right.column() == 2:
            left_datetime = source_model.data(left, Qt.ItemDataRole.UserRole)
            right_datetime = source_model.data(right, Qt.ItemDataRole.UserRole)
            if left_datetime and right_datetime:
                return left_datetime < right_datetime

        # Use default comparison for other columns
        return super().lessThan(left, right)

class FileListView(QTreeView):
    """Tree view for displaying files and folders with custom sorting"""

    item_double_clicked = pyqtSignal(str, bool)  # path, is_directory
    context_menu_requested = pyqtSignal(str, object)  # path, position
    rename_requested = pyqtSignal(str)  # path to rename
    filter_requested = pyqtSignal(str)  # character typed for filtering
    parent_navigation_requested = pyqtSignal(str, str)  # parent_path, folder_to_select

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""

        # Load sort preferences from settings
        from utils.settings import Settings
        self.settings = Settings()
        self.sort_column = self.settings.get("sort_column", 0)
        self.sort_order = Qt.SortOrder(self.settings.get("sort_order", 0))

        # Create model and proxy
        self.source_model = QStandardItemModel()
        self.proxy_model = FileSortProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.setModel(self.proxy_model)

        self.setup_ui()
        self.setup_connections()

        # Restore column widths after everything is set up
        self.restore_column_widths()

        # Install event filter to catch key events before Qt's built-in handling
        self.installEventFilter(self)

    def setup_ui(self):
        """Initialize the UI"""
        # Set up columns
        self.source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

        # Configure view properties
        self.setRootIsDecorated(False)  # No expand/collapse icons
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Disable inline editing - we want to use modal dialogs for rename
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Configure header
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)

        # Set minimum column widths
        header.setMinimumSectionSize(50)

        # Enable sorting and set default
        header.setSortIndicatorShown(True)
        header.sortIndicatorChanged.connect(self.on_sort_changed)

        # Focus policy to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Disable built-in keyboard search to prevent it from consuming our key events
        self.setAutoScroll(False)

    def setup_connections(self):
        """Set up signal connections"""
        self.doubleClicked.connect(self.on_item_double_clicked)
        self.customContextMenuRequested.connect(self.on_context_menu_requested)

        # Connect to header section resize signal to save column widths
        header = self.header()
        header.sectionResized.connect(self.save_column_widths)

    def restore_column_widths(self):
        """Restore column widths from settings"""
        default_widths = [200, 100, 150]  # Name, Size, Modified
        column_widths = self.settings.get_column_widths(default_widths)

        header = self.header()
        # Try to restore using QTimer to ensure the view is fully initialized
        QTimer.singleShot(0, lambda: self._apply_column_widths(column_widths))

    def _apply_column_widths(self, widths):
        """Apply column widths after a short delay"""
        header = self.header()
        for i, width in enumerate(widths):
            if i < header.count():
                header.resizeSection(i, width)
                actual_width = header.sectionSize(i)
                if actual_width != width:
                    # Try again with a small delay if it didn't take
                    QTimer.singleShot(10, lambda i=i, w=width: header.resizeSection(i, w))

    def save_column_widths(self):
        """Save current column widths to settings"""
        header = self.header()
        widths = []
        for i in range(header.count()):
            widths.append(header.sectionSize(i))

        self.settings.set_column_widths(widths)

    def set_path(self, path):
        """Set the current directory path and refresh"""
        self.current_path = path
        self.refresh()

    def refresh(self):
        """Refresh the file listing"""
        # Save current column widths before clearing model
        header = self.header()
        self.temp_saved_widths = []
        for i in range(header.count()):
            self.temp_saved_widths.append(header.sectionSize(i))

        self.source_model.clear()
        self.source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

        if not self.current_path:
            return

        # Get directory contents
        entries = FileOperations.list_directory(self.current_path, show_hidden=True)

        for entry in entries:
            # Create row items
            name_item = QStandardItem()
            size_item = QStandardItem()
            modified_item = QStandardItem()

            # Name column (with icon placeholder)
            name = entry['name']
            if entry['is_dir']:
                name = f"📁 {name}"
            else:
                name = f"📄 {name}"
            name_item.setText(name)

            # Store full path as data
            name_item.setData(entry['path'], Qt.ItemDataRole.UserRole)

            # Store whether it's a directory
            name_item.setData(entry['is_dir'], Qt.ItemDataRole.UserRole + 1)

            # Size column
            if entry['is_dir']:
                size_item.setText("—")
            else:
                size_item.setText(FileOperations.format_size(entry['size']))

            # Modified column
            modified_str = entry['modified'].strftime("%Y-%m-%d %H:%M")
            modified_item.setText(modified_str)

            # Store datetime for proper sorting
            modified_item.setData(entry['modified'], Qt.ItemDataRole.UserRole)

            # Add row to model
            self.source_model.appendRow([name_item, size_item, modified_item])

        # Apply current sorting through proxy model
        self.proxy_model.sort(self.sort_column, self.sort_order)

        # Select first item if no item is currently selected
        self.select_first_item_if_none_selected()

        # Restore column widths directly from saved widths or settings
        if hasattr(self, 'temp_saved_widths') and self.temp_saved_widths:
            header = self.header()
            for i, width in enumerate(self.temp_saved_widths):
                if i < header.count():
                    header.resizeSection(i, width)
        else:
            self.restore_column_widths()

        # Ensure file list has focus for keyboard navigation
        self.setFocus()

    def on_sort_changed(self, logical_index, order):
        """Handle sort indicator change"""
        self.sort_column = logical_index
        self.sort_order = order

        # Save sort preferences
        self.settings.set("sort_column", logical_index)
        self.settings.set("sort_order", order.value)

    def on_item_double_clicked(self, index):
        """Handle item double click"""
        if not index.isValid():
            return

        # Map from proxy to source model
        source_index = self.proxy_model.mapToSource(index)
        if not source_index.isValid():
            return

        # Get the item from the first column (name column)
        name_item = self.source_model.item(source_index.row(), 0)
        if not name_item:
            return

        path = name_item.data(Qt.ItemDataRole.UserRole)
        is_dir = name_item.data(Qt.ItemDataRole.UserRole + 1)
        self.item_double_clicked.emit(path, is_dir)

    def on_context_menu_requested(self, position):
        """Handle context menu request"""
        index = self.indexAt(position)
        if index.isValid():
            # Map from proxy to source model
            source_index = self.proxy_model.mapToSource(index)
            if source_index.isValid():
                # Get the item from the first column (name column)
                name_item = self.source_model.item(source_index.row(), 0)
                if name_item:
                    path = name_item.data(Qt.ItemDataRole.UserRole)
                    global_pos = self.mapToGlobal(position)
                    self.context_menu_requested.emit(path, global_pos)

    def get_selected_items(self):
        """Get list of selected item paths"""
        selected = []
        for index in self.selectionModel().selectedRows():
            if index.isValid():
                # Map from proxy to source model
                source_index = self.proxy_model.mapToSource(index)
                if source_index.isValid():
                    # Get the item from the first column (name column)
                    name_item = self.source_model.item(source_index.row(), 0)
                    if name_item:
                        path = name_item.data(Qt.ItemDataRole.UserRole)
                        selected.append(path)
        return selected

    def select_item_by_name(self, name):
        """Select an item by filename"""
        for row in range(self.source_model.rowCount()):
            item = self.source_model.item(row, 0)
            if item:
                item_path = item.data(Qt.ItemDataRole.UserRole)
                if os.path.basename(item_path) == name:
                    # Map to proxy model index and select
                    source_index = self.source_model.index(row, 0)
                    proxy_index = self.proxy_model.mapFromSource(source_index)
                    if proxy_index.isValid():
                        self.setCurrentIndex(proxy_index)
                        return True
        return False

    def select_first_item_if_none_selected(self):
        """Select the first item if no item is currently selected"""
        if self.proxy_model.rowCount() > 0 and not self.currentIndex().isValid():
            first_index = self.proxy_model.index(0, 0)
            if first_index.isValid():
                self.setCurrentIndex(first_index)

    def eventFilter(self, obj, event):
        """Event filter to catch key events before Qt's default processing"""
        if obj == self and event.type() == QEvent.Type.KeyPress:
            # Check for printable characters FIRST to prevent Qt's default handling
            if event.text() and event.text().isprintable() and not event.modifiers():
                # Printable character: request filter
                self.filter_requested.emit(event.text())
                # Return True to consume the event
                return True

        # Let the parent handle all other events
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Handle key press events for navigation and actions"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Enter: open selected item
            current_index = self.currentIndex()
            if current_index.isValid():
                self.on_item_double_clicked(current_index)
        elif event.key() == Qt.Key.Key_F2:
            # F2: rename selected item
            current_index = self.currentIndex()
            if current_index.isValid():
                # Map from proxy to source model
                source_index = self.proxy_model.mapToSource(current_index)
                if source_index.isValid():
                    # Get the item from the first column (name column)
                    name_item = self.source_model.item(source_index.row(), 0)
                    if name_item:
                        path = name_item.data(Qt.ItemDataRole.UserRole)
                        # Emit signal for rename request
                        self.rename_requested.emit(path)
        elif event.key() == Qt.Key.Key_Backspace:
            # Backspace: go to parent directory
            if self.current_path:
                parent = os.path.dirname(self.current_path)
                if parent and parent != self.current_path:
                    # Remember current folder name to select it in parent
                    current_folder_name = os.path.basename(self.current_path)
                    # Emit both parent path and folder name to select
                    self.parent_navigation_requested.emit(parent, current_folder_name)
        elif event.key() in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp,
                           Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_End]:
            # Handle navigation keys with proper scrolling
            self._handle_navigation_key(event)
        else:
            # Let parent handle other keys
            super().keyPressEvent(event)

    def _handle_navigation_key(self, event):
        """Handle navigation keys with proper scrolling"""
        current_index = self.currentIndex()
        model = self.model()

        if not model or model.rowCount() == 0:
            return

        # Store the current selection
        old_index = current_index

        # Calculate new index based on key pressed
        new_index = None

        if event.key() == Qt.Key.Key_Up:
            if current_index.isValid() and current_index.row() > 0:
                new_index = model.index(current_index.row() - 1, 0)

        elif event.key() == Qt.Key.Key_Down:
            if current_index.isValid() and current_index.row() < model.rowCount() - 1:
                new_index = model.index(current_index.row() + 1, 0)
            elif not current_index.isValid():
                # If no selection, select first item
                new_index = model.index(0, 0)

        elif event.key() == Qt.Key.Key_PageUp:
            # Move up by the number of visible rows
            visible_rows = self._get_visible_row_count()
            if current_index.isValid():
                new_row = max(0, current_index.row() - visible_rows)
                new_index = model.index(new_row, 0)
            else:
                new_index = model.index(0, 0)

        elif event.key() == Qt.Key.Key_PageDown:
            # Move down by the number of visible rows
            visible_rows = self._get_visible_row_count()
            if current_index.isValid():
                new_row = min(model.rowCount() - 1, current_index.row() + visible_rows)
                new_index = model.index(new_row, 0)
            else:
                new_index = model.index(0, 0)

        elif event.key() == Qt.Key.Key_Home:
            # Move to first item
            new_index = model.index(0, 0)

        elif event.key() == Qt.Key.Key_End:
            # Move to last item
            new_index = model.index(model.rowCount() - 1, 0)

        # Apply the new selection and ensure it's visible
        if new_index and new_index.isValid():
            self.setCurrentIndex(new_index)
            self.scrollTo(new_index, QAbstractItemView.ScrollHint.EnsureVisible)

    def _get_visible_row_count(self):
        """Calculate the number of rows that are currently visible in the view"""
        if not self.model() or self.model().rowCount() == 0:
            return 1

        # Get the height of the viewport
        viewport_height = self.viewport().height()

        # Get the height of a single row (use first row as reference)
        first_index = self.model().index(0, 0)
        row_height = self.rowHeight(first_index)

        if row_height <= 0:
            return 1

        # Calculate visible rows (subtract 1 to be conservative)
        visible_rows = max(1, (viewport_height // row_height) - 1)
        return visible_rows

    def keyboardSearch(self, search):
        """Override QTreeView's built-in keyboard search to use our filter instead"""
        if search and search.isprintable():
            self.filter_requested.emit(search)
        # Don't call parent's keyboardSearch to prevent default behavior
