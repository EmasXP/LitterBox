"""Regression tests for disastrous file-transfer bugs.

Covers data-loss / data-corruption corner cases:

- Bug #1: cut+paste in same dir with 'overwrite' must not delete the file.
- Bug #2: move with a skipped sub-file must NOT delete the skipped source file.
- Bug #3: copying a directory tree containing a symlink loop must not
  recurse forever or copy the link target.
- Bug #4: a conflict-rename decision must not be allowed to escape the
  destination directory via path-traversal in ``new_path``.
- Bug #7: the move fast path must not silently overwrite an existing
  destination created in a TOCTOU window.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

# Make src/ importable (mirrors project conftest, but be explicit here too)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.file_transfer import (  # noqa: E402
    ConflictDecision,
    FileTransferTask,
    _atomic_rename_noreplace,
    _is_safe_sibling,
    _same_path,
)


def _run_task(task: FileTransferTask, timeout: float = 10.0) -> tuple[bool, str]:
    """Run a transfer task synchronously and return (success, message).

    Joins the worker thread directly rather than waiting on the ``finished``
    Qt signal, because the test environment doesn't run a Qt event loop.
    """
    result = {"ok": True, "msg": ""}

    def _on_finished(ok: bool, msg: str):
        result["ok"] = ok
        result["msg"] = msg

    task.finished.connect(_on_finished)
    task.start()
    if task._thread is not None:
        task._thread.join(timeout=timeout)
    assert task._thread is None or not task._thread.is_alive(), (
        "transfer task did not finish in time"
    )
    return result["ok"], result["msg"]


# ---------------------------------------------------------------------------
# Bug #1: same-directory cut+paste with 'overwrite' must preserve the file.
# ---------------------------------------------------------------------------
class TestSameDirOverwrite:
    def test_move_onto_self_does_not_delete(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("important data")

        # Always say 'overwrite' on conflict (worst case).
        cb = lambda existing, source: ConflictDecision("overwrite", apply_all=True)

        task = FileTransferTask([str(src)], str(tmp_path), move=True, conflict_callback=cb)
        ok, _ = _run_task(task)
        assert ok
        assert src.exists(), "Bug #1: same-dir move-with-overwrite deleted the file"
        assert src.read_text() == "important data"

    def test_copy_onto_self_does_not_delete(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("important data")

        # Auto-rename on conflict (the same-path branch should also trigger).
        cb = lambda existing, source: ConflictDecision("overwrite", apply_all=True)

        task = FileTransferTask([str(src)], str(tmp_path), move=False, conflict_callback=cb)
        ok, _ = _run_task(task)
        assert ok
        assert src.exists()
        assert src.read_text() == "important data"


# ---------------------------------------------------------------------------
# Bug #2: skipped sub-files in a moved directory must NOT be deleted.
# ---------------------------------------------------------------------------
class TestSkippedSubfileMove:
    def test_skipped_child_survives_move(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "keep.txt").write_text("keep me")
        (src_dir / "replace.txt").write_text("source content")

        dest_dir = tmp_path / "dst"
        dest_dir.mkdir()
        # Pre-create the destination dir so the per-child callback gets used.
        (dest_dir / "src").mkdir()
        (dest_dir / "src" / "keep.txt").write_text("EXISTING - DO NOT TOUCH")

        # Skip on file conflict, but "walk into" (overwrite) the destination
        # directory so the merge actually happens.
        def cb(existing: Path, source: Path) -> ConflictDecision:
            if existing.is_dir():
                return ConflictDecision("overwrite")
            return ConflictDecision("skip")

        task = FileTransferTask([str(src_dir)], str(dest_dir), move=True, conflict_callback=cb)
        ok, _ = _run_task(task)
        assert ok

        # The skipped source file must still exist after a "move".
        assert (src_dir / "keep.txt").exists(), (
            "Bug #2: move with skipped child deleted the source file"
        )
        assert (src_dir / "keep.txt").read_text() == "keep me"
        # The other file was actually moved.
        assert not (src_dir / "replace.txt").exists()
        assert (dest_dir / "src" / "replace.txt").read_text() == "source content"
        # The pre-existing destination was preserved.
        assert (dest_dir / "src" / "keep.txt").read_text() == "EXISTING - DO NOT TOUCH"


# ---------------------------------------------------------------------------
# Bug #3: symlink loops must not cause infinite recursion / disk blowup.
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported")
class TestSymlinkLoops:
    def test_self_pointing_symlink_is_copied_as_symlink(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        # Create a symlink loop: src/loop -> src
        loop = src_dir / "loop"
        try:
            os.symlink(str(src_dir), str(loop))
        except (OSError, NotImplementedError):
            pytest.skip("cannot create symlink in this environment")
        (src_dir / "data.txt").write_text("hello")

        dest_dir = tmp_path / "dst"
        dest_dir.mkdir()

        cb = lambda *a, **k: ConflictDecision("rename")
        task = FileTransferTask([str(src_dir)], str(dest_dir), move=False, conflict_callback=cb)
        # Must finish in finite time; the bug would loop forever filling disk.
        ok, msg = _run_task(task, timeout=10.0)
        assert ok, msg

        copied = dest_dir / "src"
        assert copied.is_dir()
        assert (copied / "data.txt").read_text() == "hello"
        # The loop was preserved as a symlink (not recursed into).
        assert (copied / "loop").is_symlink()


# ---------------------------------------------------------------------------
# Bug #4: a 'rename' conflict decision must not be able to escape destdir.
# ---------------------------------------------------------------------------
class TestConflictRenameSafety:
    def test_traversal_path_is_rejected(self, tmp_path):
        outside = tmp_path / "secret.txt"
        outside.write_text("DO NOT TOUCH")

        dest_dir = tmp_path / "dst"
        dest_dir.mkdir()
        target = dest_dir / "doc.txt"
        target.write_text("existing in dst")

        src = tmp_path / "src" / "doc.txt"
        src.parent.mkdir()
        src.write_text("source content")

        # Malicious decision: try to write outside dest_dir.
        evil_path = dest_dir / ".." / "secret.txt"

        def cb(existing, source):
            return ConflictDecision("rename", new_path=evil_path)

        task = FileTransferTask([str(src)], str(dest_dir), move=False, conflict_callback=cb)
        ok, _ = _run_task(task)
        assert ok

        # The outside file must be untouched.
        assert outside.read_text() == "DO NOT TOUCH", (
            "Bug #4: conflict-rename allowed path traversal outside destination"
        )
        # And SOMETHING ended up in dest_dir (auto-renamed) instead.
        new_files = [p for p in dest_dir.iterdir() if p.name != "doc.txt"]
        assert new_files, "expected an auto-renamed copy in destination"
        assert (dest_dir / "doc.txt").read_text() == "existing in dst"

    def test_is_safe_sibling_unit(self, tmp_path):
        dest = tmp_path / "dst" / "doc.txt"
        dest.parent.mkdir()
        dest.touch()

        assert _is_safe_sibling(dest.parent / "ok.txt", dest)
        assert not _is_safe_sibling(dest.parent / ".." / "evil.txt", dest)
        assert not _is_safe_sibling(Path("/etc/passwd"), dest)
        assert not _is_safe_sibling(dest.parent / "..", dest)
        assert not _is_safe_sibling(dest.parent / "sub" / "x.txt", dest)


# ---------------------------------------------------------------------------
# Bug #7: move fast path must not silently overwrite (atomic noreplace).
# ---------------------------------------------------------------------------
class TestAtomicRenameNoReplace:
    def test_refuses_to_overwrite_existing(self, tmp_path):
        src = tmp_path / "src.txt"
        dest = tmp_path / "dst.txt"
        src.write_text("new")
        dest.write_text("OLD - MUST SURVIVE")

        ok = _atomic_rename_noreplace(src, dest)
        assert ok is False, "fast-path must refuse to clobber existing dest"
        assert dest.read_text() == "OLD - MUST SURVIVE"
        assert src.exists()

    def test_succeeds_when_dest_absent(self, tmp_path):
        src = tmp_path / "src.txt"
        dest = tmp_path / "dst.txt"
        src.write_text("new")

        assert _atomic_rename_noreplace(src, dest) is True
        assert dest.read_text() == "new"
        assert not src.exists()


# ---------------------------------------------------------------------------
# Bonus: _same_path helper sanity checks.
# ---------------------------------------------------------------------------
class TestSamePathHelper:
    def test_same_path_true_for_identical(self, tmp_path):
        f = tmp_path / "x.txt"
        f.touch()
        assert _same_path(f, f)
        assert _same_path(f, Path(str(f)))

    def test_same_path_false_for_different(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.touch()
        b.touch()
        assert not _same_path(a, b)

    @pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unsupported")
    def test_same_path_follows_symlinks(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("data")
        link = tmp_path / "link.txt"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            pytest.skip("cannot create symlink")
        assert _same_path(target, link)
