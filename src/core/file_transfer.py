"""Asynchronous file transfer utilities with progress, conflicts and cancellation."""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

CHUNK_SIZE = 1024 * 512  # 512KB


def suggest_rename(dest_path: Path) -> Path:
    parent = dest_path.parent
    stem = dest_path.stem
    suffix = dest_path.suffix
    n = 2
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


@dataclass
class ConflictDecision:
    action: str  # overwrite, rename, skip, cancel
    apply_all: bool = False
    new_path: Optional[Path] = None


class FileTransferTask(QObject):
    progress_changed = pyqtSignal(int, int)  # done, total
    finished = pyqtSignal(bool, str)
    file_progress = pyqtSignal(str)

    def __init__(self, sources: List[str], destination_dir: str, move: bool,
                 conflict_callback: Optional[Callable[[Path, Path], ConflictDecision]] = None):
        super().__init__()
        self.sources = [os.path.abspath(s) for s in sources]
        self.destination_dir = os.path.abspath(destination_dir)
        self.move = move
        self.conflict_callback = conflict_callback
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._total = 0
        self._done = 0
        self._apply_all_overwrite = False
        self._last_emit_monotonic = 0.0
        self._emit_interval = 0.2  # seconds

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    # Internal helpers
    def _enumerate(self):
        pairs = []
        for s in self.sources:
            p = Path(s)
            if p.exists():
                pairs.append((p, Path(self.destination_dir) / p.name, p.is_dir()))
        return pairs

    def _compute_total(self, pairs):
        total = 0
        for src, _dest, is_dir in pairs:
            if is_dir:
                for root, _dirs, files in os.walk(src):
                    for f in files:
                        fp = Path(root) / f
                        try:
                            total += fp.stat().st_size
                        except OSError:
                            pass
            else:
                try:
                    total += src.stat().st_size
                except OSError:
                    pass
        self._total = max(1, total)

    def _run(self):
        try:
            pairs = self._enumerate()
            self._compute_total(pairs)
            self.progress_changed.emit(0, self._total)
            for src, dest, is_dir in pairs:
                if self._cancel.is_set():
                    raise RuntimeError('Cancelled')
                # Resolve top-level conflict (folder or file)
                final_dest = self._handle_conflict(src, dest)
                if final_dest is None:
                    if self._cancel.is_set():
                        raise RuntimeError('Cancelled')
                    continue
                if is_dir:
                    # Copy directory tree with per-entry conflict handling (except root already handled)
                    self._copy_dir_with_conflicts(src, final_dest, is_root=True)
                else:
                    self._copy_file(src, final_dest)
                # For move semantics after copy (cross filesystem or rename fallback)
                if self.move and src.exists():
                    try:
                        if src.is_dir():
                            shutil.rmtree(src)
                        else:
                            src.unlink()
                    except OSError:
                        pass
            self.finished.emit(True, '')
        except Exception as e:
            if str(e) == 'Cancelled':
                self.finished.emit(False, 'Cancelled')
            else:
                self.finished.emit(False, str(e))

    def _handle_conflict(self, src: Path, dest: Path):
        if not dest.exists():
            return dest
        if self._apply_all_overwrite:
            return dest
        decision = None
        if self.conflict_callback:
            # Provide existing destination path and source path to callback
            try:
                decision = self.conflict_callback(dest, src)
            except TypeError:
                # Backward compatibility: callback expecting two params but ignoring second
                decision = self.conflict_callback(dest, dest)  # type: ignore
        if not decision:
            decision = ConflictDecision('rename')
        if decision.action == 'overwrite':
            if decision.apply_all:
                self._apply_all_overwrite = True
            return dest
        if decision.action == 'rename':
            return decision.new_path or suggest_rename(dest)
        if decision.action == 'skip':
            return None
        if decision.action == 'cancel':
            self._cancel.set()
            return None
        return dest

    def _copy_dir_with_conflicts(self, src: Path, dest: Path, is_root: bool = False):
        """Recursively copy directory with per-file and per-subdir conflict prompting.

        Root directory conflict is assumed already resolved by caller when is_root=True.
        For nested directories, if destination exists, treat as a conflict (prompt unless apply_all overwrite is set).
        """
        if not is_root:
            if dest.exists():
                final_dest = self._handle_conflict(src, dest)
                if final_dest is None:
                    return  # skip this subtree
                dest = final_dest
        dest.mkdir(parents=True, exist_ok=True)
        try:
            entries = list(src.iterdir())
        except OSError:
            entries = []
        for entry in entries:
            if self._cancel.is_set():
                raise RuntimeError('Cancelled')
            target = dest / entry.name
            if entry.is_dir():
                self._copy_dir_with_conflicts(entry, target, is_root=False)
            else:
                self._copy_file(entry, target)

    def _copy_file(self, src: Path, dest: Path):
        # Check per-file conflict (if destination exists and overwrite-all not set)
        if dest.exists() and not self._apply_all_overwrite:
            new_dest = self._handle_conflict(src, dest)
            if new_dest is None:
                return  # skip
            dest = new_dest
        temp = dest.with_suffix(dest.suffix + '.part')
        try:
            with open(src, 'rb') as rf, open(temp, 'wb') as wf:
                while True:
                    if self._cancel.is_set():
                        raise RuntimeError('Cancelled')
                    chunk = rf.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    wf.write(chunk)
                    self._done += len(chunk)
                    self.progress_changed.emit(self._done, self._total)
                    # Throttle file_progress to reduce UI repaint pressure
                    import time as _t
                    now = _t.monotonic()
                    if now - self._last_emit_monotonic >= self._emit_interval:
                        self._last_emit_monotonic = now
                        self.file_progress.emit(str(dest))
            try:
                shutil.copystat(src, temp)
            except OSError:
                pass
            temp.rename(dest)
            # Final emit for this file
            self.file_progress.emit(str(dest))
        except Exception:
            try:
                if temp.exists():
                    temp.unlink()
            except OSError:
                pass
            raise


class FileTransferManager(QObject):
    task_added = pyqtSignal(FileTransferTask)

    def __init__(self):
        super().__init__()
        self._tasks: List[FileTransferTask] = []

    def start_transfer(self, sources: List[str], destination_dir: str, move: bool,
                       conflict_callback=None) -> FileTransferTask:
        task = FileTransferTask(sources, destination_dir, move, conflict_callback)
        self._tasks.append(task)
        task.finished.connect(lambda *_: self._tasks.remove(task) if task in self._tasks else None)
        self.task_added.emit(task)
        task.start()
        return task

    def active_tasks(self):
        return list(self._tasks)
