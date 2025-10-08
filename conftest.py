import os
import pytest

# Force offscreen platform early for all tests before any Qt import to reduce GUI driver related crashes
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Provide a single QApplication instance for the whole test session.

    Avoids creating/destroying multiple QApplication objects which can cause
    segmentation faults in some PyQt builds when tests are run collectively.
    """
    app = QApplication.instance() or QApplication([])
    yield app
