import os
import sys
import subprocess
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(CURRENT_DIR, 'src')
if os.path.isdir(SRC_DIR) and SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.application_manager import ApplicationManager


def test_get_mime_type_caches_results(tmp_path):
    target = tmp_path / 'script.py'
    target.write_text('print("hi")')

    calls = []

    def fake_run(cmd, capture_output=False, text=False, check=False):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='text/x-python\n', stderr='')

    with patch('core.application_manager.subprocess.run', side_effect=fake_run):
        mgr = ApplicationManager()
        mime1 = mgr.get_mime_type(str(target))
        mime2 = mgr.get_mime_type(str(target))

    assert mime1 == 'text/x-python'
    assert mime2 == 'text/x-python'
    assert len(calls) == 1, 'Expected xdg-mime query to be executed only once due to caching'


def test_get_mime_type_skip_system_query_avoids_subprocess(tmp_path):
    target = tmp_path / 'notes.py'
    target.write_text('#!/usr/bin/env python')

    def boom(*_args, **_kwargs):
        raise AssertionError('xdg-mime should not be executed when skip_system_query=True')

    with patch('core.application_manager.subprocess.run', side_effect=boom):
        mgr = ApplicationManager()
        mime = mgr.get_mime_type(str(target), skip_system_query=True)

    assert mime == 'text/x-python'
