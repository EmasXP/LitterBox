"""
Places dropdown widget for quick navigation to standard directories
"""
from PyQt6.QtWidgets import QToolButton, QMenu
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon
from core.places_manager import PlacesManager

class PlacesButton(QToolButton):
    """Button that shows a dropdown with standard places using XDG standards"""

    place_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Try different icon options - prefer sidebar/navigation icons
        icon = QIcon.fromTheme("view-sidetree")  # Sidebar icon (common in KDE/Plasma)
        if icon.isNull():
            icon = QIcon.fromTheme("folder-home")  # Home folder icon
        if icon.isNull():
            icon = QIcon.fromTheme("go-home")  # Navigation home icon
        if icon.isNull():
            icon = QIcon.fromTheme("user-home")  # User home icon
        if icon.isNull():
            icon = QIcon.fromTheme("folder")  # Generic folder fallback

        self.setIcon(icon)
        self.setToolTip("Places")
        # Use InstantPopup so clicking anywhere opens the menu
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.places_manager = PlacesManager()

        self.setup_menu()

    def setup_menu(self):
        """Setup the places menu with XDG directories and bookmarks"""
        menu = QMenu(self)

        places = self.places_manager.get_all_places()

        # Track when we transition from builtin to bookmarks for separator
        added_separator = False

        for place in places:
            # Add separator between builtin places and bookmarks
            if not place.builtin and not added_separator:
                menu.addSeparator()
                added_separator = True

            # Create action with icon
            action = menu.addAction(place.name)

            # Add icon if available
            if place.icon:
                icon = QIcon.fromTheme(place.icon)
                if not icon.isNull():
                    action.setIcon(icon)

            action.triggered.connect(lambda checked, p=place.path: self.place_selected.emit(p))

        self.setMenu(menu)

    def refresh_places(self):
        """Refresh the places menu (useful after adding/removing bookmarks)"""
        self.places_manager.clear_cache()
        self.setup_menu()
