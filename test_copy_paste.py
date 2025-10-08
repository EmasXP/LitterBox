#!/usr/bin/env python3
"""Basic tests for copy/cut (move) core logic (non-GUI)."""
import os
import sys
import tempfile
import time
from PyQt6.QtWidgets import QApplication
import pytest
from pathlib import Path

sys.path.insert(0, 'src')
from core.file_transfer import FileTransferManager, ConflictDecision, suggest_rename

@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):  # noqa: PT004
    """Ensure QApplication exists for these tests (qapp fixture from conftest)."""
    return qapp


def wait_task(task, timeout=10):
    """Wait for a FileTransferTask to finish with improved event pumping.

    Some CI / headless environments can be slower to spin up threads; extend
    timeout and use shorter sleeps to reduce probability of spurious timeout.
    """
    start = time.time()
    done = []

    def finished(success, error):
        done.append((success, error))

    task.finished.connect(finished)

    while True:
        QApplication.processEvents()
        if done:
            return done[0]
        if time.time() - start >= timeout:
            return False, 'timeout'
        time.sleep(0.01)


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


def test_nested_conflicts_overwrite_each():
    """Without apply_all, each file conflict should invoke callback separately.

    We emulate this by counting how many times the conflict callback is called when
    copying a directory tree with two conflicting files into a destination that already
    contains both files.
    """
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        # Build source tree
        src_root = Path(srcd)/'folder'
        (src_root/'sub').mkdir(parents=True)
        create_file(src_root/'a.txt', 5)
        create_file(src_root/'sub'/'b.txt', 5)
        # Destination already has target structure with same names
        dest_root = Path(dstd)/'folder'
        (dest_root/'sub').mkdir(parents=True)
        create_file(dest_root/'a.txt', 3)
        create_file(dest_root/'sub'/'b.txt', 3)

        calls = []
        def conflict(existing, _src):
            calls.append(existing)
            return ConflictDecision('overwrite', apply_all=False)

        mgr = FileTransferManager()
        task = mgr.start_transfer([str(src_root)], dstd, move=False, conflict_callback=conflict)
        success, err = wait_task(task)
        assert success, err
        # Expect four conflicts: root folder, a.txt, sub folder, b.txt
        assert len(calls) == 4, f"expected 4 conflict prompts, got {len(calls)}"
        # Sizes should be updated
        assert (dest_root/'a.txt').stat().st_size == 5
        assert (dest_root/'sub'/'b.txt').stat().st_size == 5


def test_nested_conflicts_overwrite_apply_all():
    """With apply_all set on first conflict, subsequent file conflicts skip callback."""
    with tempfile.TemporaryDirectory() as srcd, tempfile.TemporaryDirectory() as dstd:
        src_root = Path(srcd)/'folder'
        (src_root/'sub').mkdir(parents=True)
        create_file(src_root/'a.txt', 5)
        create_file(src_root/'sub'/'b.txt', 5)
        dest_root = Path(dstd)/'folder'
        (dest_root/'sub').mkdir(parents=True)
        create_file(dest_root/'a.txt', 3)
        create_file(dest_root/'sub'/'b.txt', 3)

        calls = []
        def conflict(existing, _src):
            calls.append(existing)
            # First call sets apply_all, others should not occur
            return ConflictDecision('overwrite', apply_all=True)

        mgr = FileTransferManager()
        task = mgr.start_transfer([str(src_root)], dstd, move=False, conflict_callback=conflict)
        success, err = wait_task(task)
        assert success, err
        # Only root folder conflict should be prompted
        assert len(calls) == 1, f"expected 1 conflict prompt, got {len(calls)}"
        assert (dest_root/'a.txt').stat().st_size == 5
        assert (dest_root/'sub'/'b.txt').stat().st_size == 5
