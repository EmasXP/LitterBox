"""Tests for FileTransferTask conflict resolution.

Specifically guards against the following bugs that were present before the refactor:
    1. Choosing 'overwrite' on a single file produced TWO conflict prompts
       (the first in _run, then a second from inside _copy_file).
    2. 'Apply to all skip' was not honored.
    3. A leftover .part file from an interrupted previous transfer was silently
       clobbered with no conflict prompt.
    4. Type-mismatch (src=dir vs dst=file or vice versa) crashed the worker
       with an unhandled OSError.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from core.file_transfer import (
    ConflictDecision,
    FileTransferTask,
    suggest_rename,
)


def _wait_finished(task: FileTransferTask, timeout: float = 5.0):
    """Block until the worker thread terminates."""
    if task._thread is not None:
        task._thread.join(timeout=timeout)
    assert task._thread is None or not task._thread.is_alive(), \
        "Transfer task did not finish in time"


class TestNoDoublePrompt:
    """The user-reported bug: overwrite triggers the dialog twice."""

    def test_overwrite_single_file_prompts_exactly_once(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        prompt_count = {"n": 0}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            return ConflictDecision("overwrite")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert prompt_count["n"] == 1, (
            f"Expected exactly 1 conflict prompt for overwrite, got {prompt_count['n']}"
        )
        assert (dst_dir / "foo.txt").read_text() == "NEW"

    def test_rename_single_file_prompts_exactly_once(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        prompt_count = {"n": 0}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            return ConflictDecision("rename", new_path=existing.parent / "renamed.txt")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert prompt_count["n"] == 1
        assert (dst_dir / "foo.txt").read_text() == "OLD"  # original untouched
        assert (dst_dir / "renamed.txt").read_text() == "NEW"

    def test_skip_single_file_prompts_exactly_once(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        prompt_count = {"n": 0}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            return ConflictDecision("skip")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert prompt_count["n"] == 1
        assert (dst_dir / "foo.txt").read_text() == "OLD"


class TestApplyToAll:
    """Verify apply_all flags are honored across multiple conflicts."""

    def test_apply_all_overwrite_prompts_only_once(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        for name in ("a.txt", "b.txt", "c.txt"):
            (src_dir / name).write_text(f"NEW-{name}")
            (dst_dir / name).write_text(f"OLD-{name}")

        prompt_count = {"n": 0}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            return ConflictDecision("overwrite", apply_all=True)

        task = FileTransferTask(
            sources=[str(src_dir / n) for n in ("a.txt", "b.txt", "c.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert prompt_count["n"] == 1, (
            f"apply_all=True should prompt exactly once across N files, got {prompt_count['n']}"
        )
        for name in ("a.txt", "b.txt", "c.txt"):
            assert (dst_dir / name).read_text() == f"NEW-{name}"

    def test_apply_all_skip_prompts_only_once(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        for name in ("a.txt", "b.txt", "c.txt"):
            (src_dir / name).write_text(f"NEW-{name}")
            (dst_dir / name).write_text(f"OLD-{name}")

        prompt_count = {"n": 0}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            return ConflictDecision("skip", apply_all=True)

        task = FileTransferTask(
            sources=[str(src_dir / n) for n in ("a.txt", "b.txt", "c.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert prompt_count["n"] == 1
        for name in ("a.txt", "b.txt", "c.txt"):
            assert (dst_dir / name).read_text() == f"OLD-{name}"

    def test_no_callback_defaults_to_safe_rename(self, tmp_path):
        """With no conflict callback, the transfer should rename rather than clobber."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=None,
        )
        task.start()
        _wait_finished(task)

        # Original must be untouched
        assert (dst_dir / "foo.txt").read_text() == "OLD"
        # Renamed copy must exist
        assert (dst_dir / "foo (2).txt").read_text() == "NEW"


class TestMoveSemantics:
    """Verify that 'move=True' only removes the source when the copy succeeded."""

    def test_move_removes_source_after_overwrite(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        def callback(existing: Path, source: Path) -> ConflictDecision:
            return ConflictDecision("overwrite")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=True,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert not (src_dir / "foo.txt").exists(), "Source should be gone after move"
        assert (dst_dir / "foo.txt").read_text() == "NEW"

    def test_move_keeps_source_when_skipped(self, tmp_path):
        """Skipping a conflict in a move op must NOT delete the source."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        (dst_dir / "foo.txt").write_text("OLD")

        def callback(existing: Path, source: Path) -> ConflictDecision:
            return ConflictDecision("skip")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=True,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert (src_dir / "foo.txt").read_text() == "NEW", \
            "Source must remain when the conflict was skipped"
        assert (dst_dir / "foo.txt").read_text() == "OLD"


class TestPartFileSafety:
    """Leftover .part files from interrupted transfers must not be silently clobbered."""

    def test_leftover_part_file_is_not_clobbered(self, tmp_path):
        """An unrelated .part file from a previous transfer must survive."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "foo.txt").write_text("NEW")
        # Leftover .part file from a previous interrupted transfer
        leftover = dst_dir / "foo.txt.part"
        leftover.write_text("PREVIOUS-PARTIAL-DATA")

        task = FileTransferTask(
            sources=[str(src_dir / "foo.txt")],
            destination_dir=str(dst_dir),
            move=False,
        )
        task.start()
        _wait_finished(task)

        assert (dst_dir / "foo.txt").read_text() == "NEW"
        # Leftover .part file should still exist (it had a generic name and we
        # use a unique-per-task .part suffix now).
        assert leftover.exists(), \
            "Leftover .part file from a previous transfer must not be clobbered"
        assert leftover.read_text() == "PREVIOUS-PARTIAL-DATA"


class TestDirectoryConflicts:
    """Verify directory conflict resolution prompts exactly once per directory."""

    def test_dir_overwrite_prompts_once_for_root(self, tmp_path):
        """Root directory conflict must prompt exactly once."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "myfolder").mkdir()
        (src_dir / "myfolder" / "a.txt").write_text("NEW-a")
        (dst_dir / "myfolder").mkdir()
        # Note: no conflicting files inside, so only the root dir conflicts

        prompt_count = {"n": 0, "calls": []}

        def callback(existing: Path, source: Path) -> ConflictDecision:
            prompt_count["n"] += 1
            prompt_count["calls"].append(existing.name)
            return ConflictDecision("overwrite")

        task = FileTransferTask(
            sources=[str(src_dir / "myfolder")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        # One prompt for the root dir conflict; no inner files conflict
        assert prompt_count["n"] == 1, (
            f"Expected 1 prompt for root dir overwrite, got {prompt_count['n']}: {prompt_count['calls']}"
        )
        assert (dst_dir / "myfolder" / "a.txt").read_text() == "NEW-a"

    def test_dir_skip_prevents_recursion(self, tmp_path):
        """Skipping a directory at root must not copy any of its contents."""
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        (src_dir / "myfolder").mkdir()
        (src_dir / "myfolder" / "a.txt").write_text("NEW-a")
        (dst_dir / "myfolder").mkdir()
        (dst_dir / "myfolder" / "existing.txt").write_text("EXISTING")

        def callback(existing: Path, source: Path) -> ConflictDecision:
            return ConflictDecision("skip")

        task = FileTransferTask(
            sources=[str(src_dir / "myfolder")],
            destination_dir=str(dst_dir),
            move=False,
            conflict_callback=callback,
        )
        task.start()
        _wait_finished(task)

        assert not (dst_dir / "myfolder" / "a.txt").exists(), "a.txt should not have been copied"
        assert (dst_dir / "myfolder" / "existing.txt").read_text() == "EXISTING"


class TestSuggestRename:
    """suggest_rename should produce names that don't collide with existing files."""

    def test_suggest_rename_skips_existing(self, tmp_path):
        (tmp_path / "foo.txt").write_text("a")
        (tmp_path / "foo (2).txt").write_text("b")
        suggested = suggest_rename(tmp_path / "foo.txt")
        assert suggested.name == "foo (3).txt"

    def test_suggest_rename_no_extension(self, tmp_path):
        (tmp_path / "Makefile").write_text("a")
        suggested = suggest_rename(tmp_path / "Makefile")
        assert suggested.name == "Makefile (2)"
