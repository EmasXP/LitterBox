#!/usr/bin/env python3
"""
LitterBox - Main Entry Point
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication
from ui.main_window import MainWindow
from utils.crash_logger import CrashLogger

def main():
    # Install crash logger to catch unhandled exceptions
    CrashLogger.install_exception_handler()

    # Set the application class name before creating QApplication
    # This is crucial for Wayland window identification
    QGuiApplication.setDesktopFileName("litterbox")

    app = QApplication(sys.argv)
    app.setApplicationName("LitterBox")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("LitterBox")
    app.setDesktopFileName("litterbox")  # This helps Wayland match the window to the .desktop file

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
