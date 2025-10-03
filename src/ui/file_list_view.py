"""
File list view widget - displays files and folders in a detailed list
"""
from PyQt6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView,
                             QAbstractItemView, QMenu, QTreeView)
from PyQt6.QtCore import pyqtSignal, Qt, QMimeData, QSortFilterProxyModel, QEvent, QTimer
from PyQt6.QtGui import (
    QIcon, QDrag, QStandardItemModel, QStandardItem, QKeyEvent,
    QPixmap, QPainter
)
from PyQt6.QtWidgets import QFileIconProvider
from PyQt6.QtCore import QSize, QMimeDatabase
from typing import cast
from core.file_operations import FileOperations
from datetime import datetime
import os

class FileSortProxyModel(QSortFilterProxyModel):
    """Custom proxy model that prioritizes directories over files"""

    def filterAcceptsRow(self, source_row, source_parent):
        """Custom filtering logic"""
        if not self.filterRegularExpression().pattern():
            return True  # No filter set, accept all

        model_obj = self.sourceModel()
        if not model_obj:
            return True
        # Cast for item() access (runtime type is QStandardItemModel)
        source_model = cast(QStandardItemModel, model_obj)

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
    escape_pressed = pyqtSignal()  # emitted when Esc pressed while list has focus

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = ""

        # Load sort preferences from settings
        from utils.settings import Settings
        self.settings = Settings()

        # Get sort column - ensure it's an integer
        sort_col = self.settings.get("sort_column", 0)
        if isinstance(sort_col, (int, float)):
            self.sort_column = int(sort_col)
        else:
            self.sort_column = 0

        # Get sort order - ensure it's a valid Qt.SortOrder
        sort_order = self.settings.get("sort_order", 0)
        if isinstance(sort_order, (int, float)):
            self.sort_order = Qt.SortOrder(int(sort_order))
        else:
            self.sort_order = Qt.SortOrder.AscendingOrder

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

        # Apply initial sort indicator after everything is set up
        self.update_sort_indicator()

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
        if header:  # Guard for static analysis
            # All interactive so we can capture exact widths; we emulate stretch manually.
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)

        # Set minimum column widths
        if header:
            header.setMinimumSectionSize(50)

        # Enable sorting and set default
        if header:
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
        # (legacy direct save connection removed; now debounced in _on_section_resized)
        if header:
            header.sectionResized.connect(self._on_section_resized)
        # Internal flags/state for managing programmatic restores
        self._restoring_columns = False
        self._last_saved_all = None  # (name,size,modified)
        self._pending_fit = False
        self._min_widths = [120, 70, 140]  # Minimums for Name, Size, Modified
        self._fit_debounce_ms = 60
        self._save_debounce_ms = 120
        self._pending_save = False
        self._pending_resize_fit = False
        self._icon_provider = QFileIconProvider()
        # MIME database & icon cache (initialized here so type checkers see attributes)
        try:
            self._mime_db = QMimeDatabase()
        except Exception:  # pragma: no cover - fallback if unavailable
            self._mime_db = None
        self._icon_cache = {}
        self._overlay_cache = {}
        self._base_icon_size = QSize(16, 16)  # standard small icon size for list view
        self._overlay_icon_size = QSize(8, 8)

    # already connected above if header available

    def restore_column_widths(self):
        """Restore all three column widths; fallback to defaults with backward compatibility.

        If only 2 widths stored, prepend default for Name; if malformed, use defaults.
        """
        defaults = [200, 100, 150]
        stored = self.settings.get_column_widths(defaults)
        if len(stored) == 2:
            stored = [defaults[0]] + stored
        if len(stored) < 3:
            stored = defaults
        header = self.header()
        QTimer.singleShot(0, lambda w=stored: self._apply_all_widths(w))

    # ---------------- Persistence & Save Logic ----------------
    def _on_section_resized(self, *_):
        """Debounce user-initiated resize operations before saving."""
        if getattr(self, '_restoring_columns', False):
            return
        if not self._pending_save:
            self._pending_save = True
            QTimer.singleShot(self._save_debounce_ms, self._commit_user_widths)

    def _commit_user_widths(self):
        self._pending_save = False
        self.save_column_widths()

    def _apply_all_widths(self, widths):
        header = self.header()
        if not header:
            return
        self._restoring_columns = True
        try:
            for i, w in enumerate(widths):
                if i < header.count() and w > 0:
                    header.resizeSection(i, w)
        finally:
            QTimer.singleShot(30, lambda: setattr(self, '_restoring_columns', False))
        # Schedule a fit pass after layout settles
        QTimer.singleShot(45, self._fit_name_column)

    def save_column_widths(self):
        """Persist all columns (Name, Size, Modified) when user finishes resizing."""
        if getattr(self, '_restoring_columns', False):
            return
        header = self.header()
        if not header:
            return
        widths = [header.sectionSize(i) for i in range(header.count())]
        if len(widths) >= 3 and all(w > 4 for w in widths):
            tup = tuple(widths[:3])
            if self._last_saved_all != tup:
                self.settings.set_column_widths(widths[:3])
                self._last_saved_all = tup

    def set_path(self, path):
        """Set the current directory path and refresh"""
        self.current_path = path
        self.refresh()

    def refresh(self):
        """Refresh the file listing preserving selection and scroll position."""
        had_focus = self.hasFocus()
        # Capture current vertical scroll position & selected paths
        vbar = self.verticalScrollBar() if hasattr(self, 'verticalScrollBar') else None
        prev_scroll = vbar.value() if vbar else 0
        prev_selected = set(self.get_selected_items()) if hasattr(self, 'get_selected_items') else set()
        current_index_path = None
        if self.currentIndex().isValid():
            # Capture current item path for focused restoration preference
            src_idx = self.proxy_model.mapToSource(self.currentIndex())
            if src_idx.isValid():
                item = self.source_model.item(src_idx.row(), 0)
                if item:
                    current_index_path = item.data(Qt.ItemDataRole.UserRole)

        # Save current widths before clearing (all three) for quick intra-refresh restore
        header = self.header()
        self._temp_all = None
        if header and header.count() >= 3:
            self._temp_all = [header.sectionSize(i) for i in range(3)]

        self.source_model.clear()
        self.source_model.setHorizontalHeaderLabels(["Name", "Size", "Modified"])

        # Populate model
        if not self.current_path or not os.path.isdir(self.current_path):
            return

        try:
            entries = FileOperations.list_directory(self.current_path)
        except Exception:
            entries = []

        for entry in entries:
            name_item = QStandardItem(entry['name'])
            name_item.setEditable(False)
            name_item.setData(entry['path'], Qt.ItemDataRole.UserRole)  # store path
            name_item.setData(entry['is_dir'], Qt.ItemDataRole.UserRole + 1)  # directory flag
            try:
                icon = self._icon_for_entry(entry)
                if icon and not icon.isNull():
                    name_item.setIcon(icon)
            except Exception:
                pass
            size_item = QStandardItem("" if entry['is_dir'] else FileOperations.format_size(entry['size']))
            size_item.setEditable(False)
            modified_item = QStandardItem("")
            modified_item.setEditable(False)
            if entry.get('modified') and isinstance(entry['modified'], datetime):
                modified_str = entry['modified'].strftime("%Y-%m-%d %H:%M")
                modified_item.setText(modified_str)
                modified_item.setData(entry['modified'], Qt.ItemDataRole.UserRole)
            self.source_model.appendRow([name_item, size_item, modified_item])

        # Sort and update
        self.proxy_model.sort(self.sort_column, self.sort_order)
        self.update_sort_indicator()

        # Restore selection
        selection_model = self.selectionModel()
        if selection_model and prev_selected:
            selection_model.clearSelection()
            flags = selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows
            preferred_index = None
            for row in range(self.source_model.rowCount()):
                item = self.source_model.item(row, 0)
                if not item:
                    continue
                path = item.data(Qt.ItemDataRole.UserRole)
                if path in prev_selected:
                    src_index = self.source_model.index(row, 0)
                    proxy_index = self.proxy_model.mapFromSource(src_index)
                    if proxy_index.isValid():
                        selection_model.select(proxy_index, flags)
                        if current_index_path and path == current_index_path:
                            preferred_index = proxy_index
            # Restore current index preference (focused item) else first of selection
            if preferred_index is None and selection_model.selectedRows():
                preferred_index = selection_model.selectedRows()[0]
            if preferred_index:
                self.setCurrentIndex(preferred_index)

        # If nothing selected after restore attempt, fallback to first
        self.select_first_item_if_none_selected()

        # Restore widths or use settings
        if header and self._temp_all:
            self._apply_all_widths(self._temp_all)
        else:
            self.restore_column_widths()

        # Defer scroll restoration until layout settles
        def _restore_scroll():
            if vbar:
                # Clamp scroll value to new range
                vbar.setValue(min(prev_scroll, vbar.maximum()))
        QTimer.singleShot(30, _restore_scroll)
        QTimer.singleShot(60, self._fit_columns)

        if had_focus:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---------------- Deterministic Fit Algorithm ----------------
    def _fit_columns(self):
        """Ensure columns fit viewport without horizontal scrollbar by shrinking in priority.

        Priority (shrink first): Modified -> Size -> Name. Expansion goes to Name.
        Does not persist changes. Honors minimum widths defined in self._min_widths.
        """
        if getattr(self, '_restoring_columns', False):
            return
        header = self.header()
        if not header or header.count() < 3:
            return
        vp = self.viewport()
        vp_w = vp.width() if vp else 0
        widths = [header.sectionSize(i) for i in range(3)]
        mins = self._min_widths
        total = sum(widths)
        if vp_w <= 0:
            return
        # Overflow handling
        if total > vp_w:
            overflow = total - vp_w
            order = [2, 1, 0]  # Modified, Size, Name
            idx = 0
            self._restoring_columns = True
            try:
                while overflow > 0 and idx < len(order):
                    col = order[idx]
                    current = widths[col]
                    floor = mins[col]
                    reducible = max(0, current - floor)
                    if reducible > 0:
                        take = min(reducible, overflow)
                        if take > 0:
                            new_w = current - take
                            header.resizeSection(col, new_w)
                            widths[col] = new_w
                            overflow -= take
                    if reducible <= 0:
                        idx += 1
            finally:
                QTimer.singleShot(20, lambda: setattr(self, '_restoring_columns', False))
        else:
            # Slack distribution -> give to Name column only
            slack = vp_w - total
            if slack > 6:
                self._restoring_columns = True
                try:
                    header.resizeSection(0, widths[0] + slack)
                finally:
                    QTimer.singleShot(20, lambda: setattr(self, '_restoring_columns', False))

    # Backward compatibility method name retained (if other code calls it)
    def _fit_name_column(self):  # pragma: no cover - alias
        self._fit_columns()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._pending_resize_fit:
            self._pending_resize_fit = True
            QTimer.singleShot(self._fit_debounce_ms, self._post_resize_fit)

    def _post_resize_fit(self):
        self._pending_resize_fit = False
        self._fit_columns()
        # Removed forced focus to preserve user typing in filter entry

    def on_sort_changed(self, logical_index, order):
        """Handle sort indicator change"""
        self.sort_column = logical_index
        self.sort_order = order

        # Save sort preferences
        self.settings.set("sort_column", logical_index)
        self.settings.set("sort_order", order.value)

    def update_sort_indicator(self):
        """Update the header sort indicator to match current sort state"""
        header = self.header()
        if header:
            header.setSortIndicator(self.sort_column, self.sort_order)

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
        selection_model = self.selectionModel()
        if not selection_model:
            return selected
        for index in selection_model.selectedRows():
            if index.isValid():
                source_index = self.proxy_model.mapToSource(index)
                if source_index.isValid():
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

    def eventFilter(self, object, event):  # parameter name 'object' matches Qt signature
        """Event filter to catch key events before Qt's default processing"""
        if object == self and event.type() == QEvent.Type.KeyPress:
            # Cast safely to QKeyEvent for access to text()/modifiers()
            if isinstance(event, QKeyEvent):
                if event.text() and event.text().isprintable() and not event.modifiers():
                    self.filter_requested.emit(event.text())
                    return True

        # Let the parent handle all other events
        return super().eventFilter(object, event)

    def keyPressEvent(self, event):
        """Handle key press events for navigation and actions"""
        # Emacs-style: Alt+< (M-<) go to beginning, Alt+> (M->) go to end
        # On many layouts this is produced via Alt+Shift+',' and Alt+Shift+'.'
        # We check modifiers and the text to remain layout-agnostic.
        if event.modifiers() & Qt.KeyboardModifier.AltModifier:
            txt = event.text()
            if txt == '<':
                self._jump_to_beginning()
                return
            elif txt == '>':
                self._jump_to_end()
                return
        # Escape: custom behavior requested by main window (hide filter & exit path edit)
        if event.key() == Qt.Key.Key_Escape:
            # Emit signal so container (FileTab/MainWindow) can decide what to do.
            self.escape_pressed.emit()
            return
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

    def _jump_to_beginning(self):
        model = self.model()
        if model and model.rowCount() > 0:
            first = model.index(0, 0)
            if first.isValid():
                self.setCurrentIndex(first)
                self.scrollTo(first, QAbstractItemView.ScrollHint.PositionAtTop)

    def _jump_to_end(self):
        model = self.model()
        if model and model.rowCount() > 0:
            last = model.index(model.rowCount() - 1, 0)
            if last.isValid():
                self.setCurrentIndex(last)
                self.scrollTo(last, QAbstractItemView.ScrollHint.PositionAtBottom)

    def _get_visible_row_count(self):
        """Calculate the number of rows that are currently visible in the view"""
        model = self.model()
        if not model or model.rowCount() == 0:
            return 1

        # Get the height of the viewport
        viewport_height = self.viewport().height()

        # Get the height of a single row (use first row as reference)
        first_index = model.index(0, 0)
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

    # ---------------- Icon Logic ----------------
    def _icon_for_entry(self, entry):
        """Return a QIcon for a directory/file using MIME type detection and theme icons.

        Adds overlays for symlinks and executables.
        Caches results based on key signature.
        """
        path = entry['path']
        is_dir = entry.get('is_dir', False)
        # Additional flags we may want for cache key
        # Determine symlink & executable lazily to avoid repeated os.lstat calls (info already present?)
        # file_operations.get_file_info currently sets 'is_symlink' and we can derive executability via permissions
        is_symlink = entry.get('is_symlink', False)
        # Executable heuristic: non-dir & any execute bit -> treat as executable for overlay and icon bias
        is_executable = False
        if not is_dir:
            # Permissions fields exist in entry from get_file_info
            exec_bits = [entry.get('owner_execute'), entry.get('group_execute'), entry.get('other_execute')]
            is_executable = any(exec_bits)

        cache_key = (is_dir, is_symlink, is_executable, entry.get('name'), entry.get('size', 0))
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        # Base icon selection
        if is_dir:
            # Try to pick up themed folder icon, QFileIconProvider already honors special directories (Desktop, Downloads...) via QFileInfo path.
            # We'll attempt QFileIconProvider for path-specific folder (it can resolve special icons) else fallback to theme.
            try:
                from PyQt6.QtCore import QFileInfo
                fi = QFileInfo(path)
                base_icon = self._icon_provider.icon(fi)  # provider can use platform hints
            except Exception:
                base_icon = QIcon.fromTheme('inode-directory')
            if base_icon.isNull():
                base_icon = QIcon.fromTheme('folder')
            if base_icon.isNull():
                base_icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
        else:
            base_icon = self._file_icon_from_mime(path, is_executable)

        # Apply overlays if needed
        if is_symlink or is_executable:
            composed = self._apply_overlays(base_icon, is_symlink=is_symlink, is_executable=is_executable)
        else:
            composed = base_icon

        self._icon_cache[cache_key] = composed
        return composed

    def _file_icon_from_mime(self, path, is_executable):
        """Resolve icon for a file using MIME database and theme; prefer executable icon when applicable."""
        icon = QIcon()
        try:
            mime_type = None
            if self._mime_db is not None:
                mime_type = self._mime_db.mimeTypeForFile(path, QMimeDatabase.MatchMode.MatchContent)
            if mime_type and mime_type.isValid():
                # Primary attempt: use exact mime name, e.g. text-plain, image-png
                mime_name = mime_type.name().replace('/', '-')
                icon = QIcon.fromTheme(mime_name)
                if icon.isNull():
                    # Generic major type fallback (text, image, audio, video, application)
                    major = mime_name.split('-', 1)[0]
                    generic_map = {
                        'text': 'text-x-generic',
                        'image': 'image-x-generic',
                        'audio': 'audio-x-generic',
                        'video': 'video-x-generic',
                        'application': 'application-x-executable' if is_executable else 'application-octet-stream',
                    }
                    guess = generic_map.get(major)
                    if guess:
                        icon = QIcon.fromTheme(guess)
        except Exception:
            pass

        if is_executable:
            # Prefer explicit executable icon if available
            exec_icon = QIcon.fromTheme('application-x-executable')
            if not exec_icon.isNull() and icon.cacheKey() != exec_icon.cacheKey():
                icon = exec_icon

        if icon.isNull():
            # QFileIconProvider fallback
            icon = self._icon_provider.icon(QFileIconProvider.IconType.File)
        return icon

    def _apply_overlays(self, base_icon, is_symlink=False, is_executable=False):
        """Compose overlay badges (bottom-right) onto base icon.

        We draw tiny emblem-like overlays using theme icons if available (emblem-symbolic-link, emblem-symbolic, application-x-executable),
        else fallback to simple glyph rendering.
        Cache by (id(base_icon.cacheKey), is_symlink, is_executable).
        """
        try:
            key = (base_icon.cacheKey(), is_symlink, is_executable)
            if key in self._overlay_cache:
                return self._overlay_cache[key]

            # Obtain pixmap for base
            pm = base_icon.pixmap(self._base_icon_size)
            if pm.isNull():
                return base_icon

            painter = QPainter(pm)
            try:
                offset = 0
                # Draw overlays stacked horizontally from right edge
                overlays = []
                if is_symlink:
                    overlays.append(self._overlay_pixmap(['emblem-symbolic-link', 'emblem-symlink', 'emblem-symbolic']))
                if is_executable:
                    overlays.append(self._overlay_pixmap(['application-x-executable', 'system-run']))

                for ov_pm in overlays:
                    if ov_pm and not ov_pm.isNull():
                        # Draw bottom-right stacking leftwards
                        x = pm.width() - ov_pm.width() - offset
                        y = pm.height() - ov_pm.height()
                        painter.drawPixmap(x, y, ov_pm)
                        offset += ov_pm.width() - 2  # slight overlap for compactness
            finally:
                painter.end()

            icon = QIcon(pm)
            self._overlay_cache[key] = icon
            return icon
        except Exception:
            return base_icon

    def _overlay_pixmap(self, icon_names):
        """Return a small pixmap for first available icon name else fallback drawn symbol."""
        for name in icon_names:
            ic = QIcon.fromTheme(name)
            if ic and not ic.isNull():
                pm = ic.pixmap(self._overlay_icon_size)
                if not pm.isNull():
                    return pm
        # Fallback: create a simple badge pixmap
        pm = QPixmap(self._overlay_icon_size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.darkGray)
        painter.drawEllipse(0, 0, pm.width(), pm.height())
        painter.end()
        return pm

    def ensure_current_selection_visible(self):
        """Ensure the current selection is visible by scrolling to it if necessary"""
        current_index = self.currentIndex()
        if current_index.isValid():
            self.scrollTo(current_index, QAbstractItemView.ScrollHint.EnsureVisible)
