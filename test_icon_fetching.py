import os
import sys

import pytest  # type: ignore[import]
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CURRENT_DIR, 'src')
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ui.file_list_view import FileListView


class DummyMime:
    def __init__(self, name):
        self._name = name

    def isValid(self):
        return self._name is not None

    def name(self):
        return self._name


class DummyMimeDatabase:
    def __init__(self, name):
        self._name = name

    def mimeTypeForFile(self, _path, _mode):
        return DummyMime(self._name)


class RecordingManager:
    def __init__(self, result='text/x-python'):
        self.calls = []
        self.result = result

    def get_mime_type(self, path, skip_system_query=False):
        self.calls.append((path, skip_system_query))
        return self.result


class DummyIconProvider:
    def icon(self, *_args, **_kwargs):
        return QIcon()


@pytest.fixture(scope='session')
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_file_icon_skips_manager_for_specific_mime(qt_app):
    view = FileListView()
    view._mime_db = DummyMimeDatabase('text/x-python')  # type: ignore[assignment]
    recorder = RecordingManager()
    view._application_manager = recorder  # type: ignore[assignment]
    view._icon_provider = DummyIconProvider()  # type: ignore[assignment]

    icon = view._file_icon_from_mime('foo.py', False)

    assert isinstance(icon, QIcon)
    assert recorder.calls == []
    view.deleteLater()


def test_file_icon_uses_manager_for_generic_mime(qt_app):
    view = FileListView()
    view._mime_db = DummyMimeDatabase('text/plain')  # type: ignore[assignment]
    recorder = RecordingManager('text/x-python')
    view._application_manager = recorder  # type: ignore[assignment]
    view._icon_provider = DummyIconProvider()  # type: ignore[assignment]

    icon = view._file_icon_from_mime('foo.py', False)

    assert isinstance(icon, QIcon)
    assert recorder.calls == [('foo.py', True)]
    view.deleteLater()
