"""Tests for the rename(2) fast path used by move operations.

A move on the same filesystem should be a single ``os.rename`` call rather
than a copy + delete. When ``rename`` fails (different filesystems, gvfs/FUSE
quirks, permission errors), the task must transparently fall back to the
copy + delete behavior.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.file_transfer import FileTransferTask


def _wait(task: FileTransferTask, timeout: float = 5.0):
    task.start()
    if task._thread is not None:
        task._thread.join(timeout=timeout)
    assert task._thread is None or not task._thread.is_alive(), \
        "transfer did not finish in time"
    return {'ok': True, 'msg': ''}


class TestMoveFastPath:
    def test_move_file_uses_rename_when_no_conflict(self, tmp_path):
        """A same-FS move with no conflict must preserve the source inode."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        srcf = src_dir / "data.bin"
        srcf.write_bytes(b"hello world")
        original_inode = srcf.stat().st_ino

        task = FileTransferTask(
            sources=[str(srcf)],
            destination_dir=str(dst_dir),
            move=True,
        )
        result = _wait(task)
        assert result['ok']

        moved = dst_dir / "data.bin"
        assert not srcf.exists()
        assert moved.read_bytes() == b"hello world"
        # Same inode proves we used rename(2) rather than copy + delete.
        assert moved.stat().st_ino == original_inode

    def test_move_directory_uses_rename_when_no_conflict(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        tree = src_dir / "tree"
        tree.mkdir()
        (tree / "a.txt").write_text("A")
        (tree / "sub").mkdir()
        (tree / "sub" / "b.txt").write_text("B")
        original_inode = tree.stat().st_ino

        task = FileTransferTask(
            sources=[str(tree)],
            destination_dir=str(dst_dir),
            move=True,
        )
        result = _wait(task)
        assert result['ok']

        moved = dst_dir / "tree"
        assert not tree.exists()
        assert (moved / "a.txt").read_text() == "A"
        assert (moved / "sub" / "b.txt").read_text() == "B"
        assert moved.stat().st_ino == original_inode

    def test_move_falls_back_to_copy_when_rename_fails(self, tmp_path, monkeypatch):
        """Simulate cross-device EXDEV: rename raises, copy+delete must take over."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        srcf = src_dir / "data.bin"
        srcf.write_bytes(b"payload")

        real_rename = os.rename

        def fake_rename(a, b):
            # Only sabotage the top-level move; let the copy path's internal
            # os.replace (used to atomize the .part -> dest swap) work.
            if str(a) == str(srcf):
                raise OSError(18, "Invalid cross-device link")  # EXDEV
            return real_rename(a, b)

        monkeypatch.setattr(os, 'rename', fake_rename)

        task = FileTransferTask(
            sources=[str(srcf)],
            destination_dir=str(dst_dir),
            move=True,
        )
        result = _wait(task)
        assert result['ok']

        moved = dst_dir / "data.bin"
        assert not srcf.exists()
        assert moved.read_bytes() == b"payload"

    def test_move_with_conflict_still_uses_copy_path(self, tmp_path):
        """When dest exists, fast path is skipped so conflict resolution runs."""
        from core.file_transfer import ConflictDecision

        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        calls = []

        def cb(existing: Path, source: Path) -> ConflictDecision:
            calls.append(existing)
            return ConflictDecision("overwrite")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=True,
            conflict_callback=cb,
        )
        result = _wait(task)
        assert result['ok']

        assert len(calls) == 1, "conflict callback must be invoked exactly once"
        assert (dst_dir / "foo.txt").read_text() == "NEW"
        assert not (src_dir / "foo.txt").exists()
