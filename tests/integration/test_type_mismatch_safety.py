"""Regression tests for type-mismatch overwrite safety (bug #9).

Two scenarios:
1. A stale ``apply_all_overwrite`` flag must NOT cause the worker to silently
   ``rmtree`` a non-empty directory in order to drop a file in its place.
2. A direct (non-UI) caller forcing ``overwrite`` on a file-vs-dir conflict
   must be refused when the destination directory has contents.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.file_transfer import (  # noqa: E402
    ConflictDecision,
    FileTransferTask,
)


def _run(task: FileTransferTask, timeout: float = 10.0):
    result = {"ok": True, "msg": ""}

    def cb(ok, msg):
        result["ok"] = ok
        result["msg"] = msg

    task.finished.connect(cb)
    task.start()
    if task._thread is not None:
        task._thread.join(timeout=timeout)
    return result["ok"], result["msg"]


class TestApplyAllDoesNotPropagateAcrossTypeMismatch:
    def test_apply_all_overwrite_does_not_destroy_dir(self, tmp_path):
        """User says 'overwrite all' on file-vs-file; later file-vs-dir must re-prompt."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        # Two source files. Both names already exist in dest, but with
        # different types so we can verify the dir survives.
        (src_dir / "a.txt").write_text("new A")
        (src_dir / "b.txt").write_text("new B")

        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        (dst_dir / "a.txt").write_text("OLD A")  # plain file conflict
        # 'b.txt' on the destination is actually a NON-EMPTY DIRECTORY.
        b_dir = dst_dir / "b.txt"
        b_dir.mkdir()
        precious = b_dir / "precious.txt"
        precious.write_text("DO NOT DELETE")

        prompts = []

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompts.append(existing.name)
            # First prompt (a.txt, file vs file): overwrite + apply_all.
            # Second prompt (b.txt, file vs dir): would be re-prompted; skip it.
            if existing.name == "a.txt":
                return ConflictDecision("overwrite", apply_all=True)
            return ConflictDecision("skip")

        task = FileTransferTask(
            sources=[str(src_dir / "a.txt"), str(src_dir / "b.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        ok, _ = _run(task)
        assert ok

        # a.txt: overwritten by the apply_all flag.
        assert (dst_dir / "a.txt").read_text() == "new A"
        # b.txt: the directory and its contents are untouched.
        assert b_dir.is_dir(), "Bug #9: file-vs-dir overwrite blew away the directory"
        assert precious.read_text() == "DO NOT DELETE"
        # The callback was called twice (re-prompted for the type mismatch).
        assert prompts.count("b.txt") == 1, (
            "Bug #9: type-mismatch conflict should re-prompt instead of "
            "inheriting apply_all_overwrite"
        )


class TestForcedOverwriteRefusesNonEmptyDir:
    def test_forced_overwrite_does_not_rmtree_nonempty_dir(self, tmp_path):
        """Direct callers can't sneak past the dialog and rmtree a populated dir."""
        src = tmp_path / "src.txt"
        src.write_text("source")

        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        target = dst_dir / "src.txt"
        target.mkdir()  # destination "src.txt" is a non-empty directory
        (target / "child.txt").write_text("PRESERVE ME")

        # Forced overwrite via the callback (the UI would not allow this).
        cb = lambda existing, source: ConflictDecision("overwrite")

        task = FileTransferTask(
            sources=[str(src)],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=cb,
        )
        ok, _ = _run(task)
        assert ok  # the worker doesn't crash, it just refuses this item

        # The directory and its contents must be intact.
        assert target.is_dir()
        assert (target / "child.txt").read_text() == "PRESERVE ME"
        # The source is also untouched.
        assert src.read_text() == "source"
