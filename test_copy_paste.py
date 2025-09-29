#!/usr/bin/env python3
"""Basic tests for copy/cut (move) core logic (non-GUI)."""
import os
import sys
import tempfile
import time
from PyQt6.QtCore import QCoreApplication
from pathlib import Path

sys.path.insert(0, 'src')
from core.file_transfer import FileTransferManager, ConflictDecision, suggest_rename

from PyQt6.QtCore import QCoreApplication
app = QCoreApplication.instance() or QCoreApplication([])


def wait_task(task, timeout=5):
    start = time.time()
    done = []
    def finished(success, error):
        done.append((success, error))
    task.finished.connect(finished)
    while time.time() - start < timeout:
        QCoreApplication.processEvents()
        if done:
            return done[0]
        time.sleep(0.05)
    return False, 'timeout'


def create_file(path: Path, size: int, content=b'x'):
    with open(path, 'wb') as f:
        f.write(content * size)


def test_simple_copy():
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        srcf = Path(srcd)/'file.txt'
        create_file(srcf, 10)
        mgr = FileTransferManager()
        task = mgr.start_transfer([str(srcf)], dstd, move=False)
        success, err = wait_task(task)
        assert success, err
        assert (Path(dstd)/'file.txt').exists()
        assert srcf.exists()


def test_move():
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        srcf = Path(srcd)/'file.txt'
        create_file(srcf, 10)
        mgr = FileTransferManager()
        task = mgr.start_transfer([str(srcf)], dstd, move=True)
        success, err = wait_task(task)
        assert success, err
        assert (Path(dstd)/'file.txt').exists()
        assert not srcf.exists()


def test_conflict_rename():
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        # destination has file.txt already
        dest_existing = Path(dstd)/'file.txt'
        create_file(dest_existing, 5)
        srcf = Path(srcd)/'file.txt'
        create_file(srcf, 5)
        def conflict(existing, _hint):
            return ConflictDecision('rename')
        mgr = FileTransferManager()
        task = mgr.start_transfer([str(srcf)], dstd, move=False, conflict_callback=conflict)
        success, err = wait_task(task)
        assert success, err
        # original remains, new suggested name created
        assert dest_existing.exists()
        # find renamed
        files = list(Path(dstd).iterdir())
        assert len(files) == 2


def test_conflict_overwrite_apply_all():
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        f1 = Path(srcd)/'a.txt'; create_file(f1, 5)
        f2 = Path(srcd)/'b.txt'; create_file(f2, 5)
        dest1 = Path(dstd)/'a.txt'; create_file(dest1, 3)
        dest2 = Path(dstd)/'b.txt'; create_file(dest2, 3)
        def conflict(existing, _hint):
            return ConflictDecision('overwrite', apply_all=True)
        mgr = FileTransferManager()
        task = mgr.start_transfer([str(f1), str(f2)], dstd, move=False, conflict_callback=conflict)
        success, err = wait_task(task)
        assert success, err
        # Both should have been overwritten (sizes 5)
        assert (Path(dstd)/'a.txt').stat().st_size == 5
        assert (Path(dstd)/'b.txt').stat().st_size == 5


def test_suggest_rename():
    with tempfile.TemporaryDirectory() as dstd:
        base = Path(dstd)/'file.txt'
        create_file(base, 1)
        r1 = suggest_rename(base)
        create_file(r1, 1)
        r2 = suggest_rename(base)
        assert r1 != base and r2 != base and r1 != r2


if __name__ == '__main__':
    # Run tests manually
    for fn in [test_simple_copy, test_move, test_conflict_rename, test_conflict_overwrite_apply_all, test_suggest_rename]:
        print('Running', fn.__name__)
        fn()
    print('All copy/paste tests passed.')
