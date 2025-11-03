import os
import sys
import pytest
from pathlib import Path

# Add src directory to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
