"""
Places dropdown widget for quick navigation to standard directories
"""
from PyQt6.QtWidgets import QToolButton, QMenu
from PyQt6.QtCore import pyqtSignal
from core.file_operations import FileOperations

class PlacesButton(QToolButton):
    """Button that shows a dropdown with standard places"""

    place_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Places")
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.setup_menu()

    def setup_menu(self):
        """Setup the places menu"""
        menu = QMenu(self)

        places = FileOperations.get_standard_places()
        for name, path in places:
            action = menu.addAction(name)
            action.triggered.connect(lambda checked, p=path: self.place_selected.emit(p))

        self.setMenu(menu)
