"""Asynchronous file transfer utilities with progress, conflicts and cancellation."""
from __future__ import annotations

import os
import shutil
import threading
import tempfile
import urllib.request
import urllib.parse
import re
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


class DownloadTask(QObject):
    """Task for downloading files from remote URLs."""
    progress_changed = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)
    file_progress = pyqtSignal(str)

    def __init__(self, urls: List[str], destination_dir: str,
                 conflict_callback: Optional[Callable[[Path, Path], ConflictDecision]] = None):
        super().__init__()
        self.sources = list(urls)
        self.destination_dir = os.path.abspath(destination_dir)
        self.conflict_callback = conflict_callback
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._total = 1
        self._done = 0
        self._apply_all_overwrite = False

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _compute_total_estimate(self):
        total = 0
        for url in self.sources:
            try:
                request = urllib.request.Request(url, method='HEAD')
                with urllib.request.urlopen(request, timeout=10) as response:
                    length = response.headers.get('Content-Length')
                    if length and length.isdigit():
                        total += int(length)
            except Exception:
                continue
        self._total = max(total, 1)

    def _run(self):
        try:
            self._compute_total_estimate()
            self.progress_changed.emit(0, self._total)
            for index, url in enumerate(self.sources):
                if self._cancel.is_set():
                    raise RuntimeError('Cancelled')
                self._download_single(index, url)
            self.finished.emit(True, '')
        except Exception as e:
            if str(e) == 'Cancelled':
                self.finished.emit(False, 'Cancelled')
            else:
                self.finished.emit(False, str(e))

    def _download_single(self, index: int, url: str):
        request = urllib.request.Request(url, headers={'User-Agent': 'LitterBox/1.0'})
        with urllib.request.urlopen(request, timeout=30) as response:
            filename = self._derive_filename(index, url, response)
            final_dest = Path(self.destination_dir) / filename
            temp_file = tempfile.NamedTemporaryFile(delete=False, dir=self.destination_dir, suffix='.download')
            temp_path = Path(temp_file.name)
            try:
                with temp_file:
                    while True:
                        if self._cancel.is_set():
                            raise RuntimeError('Cancelled')
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        temp_file.write(chunk)
                        self._done += len(chunk)
                        self._total = max(self._total, self._done)
                        self.progress_changed.emit(self._done, max(self._total, 1))
                        self.file_progress.emit(str(final_dest))
            except Exception:
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass
                raise
        self._finalize_download(temp_path, final_dest)

    def _derive_filename(self, index: int, url: str, response):
        disposition = response.headers.get('Content-Disposition', '')
        if disposition:
            match = re.search(r'filename\*?=([^;]+)', disposition, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip().strip('"')
                if name.lower().startswith("utf-8''"):
                    name = name[7:]
                candidate = os.path.basename(urllib.parse.unquote(name))
                if candidate:
                    return candidate
        parsed = urllib.parse.urlparse(url)
        if parsed.path:
            candidate = os.path.basename(parsed.path.rstrip('/'))
            candidate = urllib.parse.unquote(candidate)
            if candidate:
                return candidate
        return f'downloaded-file-{index + 1}'

    def _finalize_download(self, temp_path: Path, final_dest: Path):
        dest = final_dest
        if dest.exists():
            if self._apply_all_overwrite:
                self._overwrite_existing(dest)
            else:
                decision = self._request_conflict(dest, temp_path)
                if decision.action == 'overwrite':
                    if decision.apply_all:
                        self._apply_all_overwrite = True
                    self._overwrite_existing(dest)
                elif decision.action == 'rename':
                    dest = decision.new_path or suggest_rename(dest)
                elif decision.action == 'skip':
                    temp_path.unlink(missing_ok=True)
                    return
                elif decision.action == 'cancel':
                    temp_path.unlink(missing_ok=True)
                    self._cancel.set()
                    raise RuntimeError('Cancelled')
                else:
                    temp_path.unlink(missing_ok=True)
                    return
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            temp_path.replace(dest)
        except Exception:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            raise
        self.file_progress.emit(str(dest))

    def _overwrite_existing(self, dest: Path):
        try:
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        except OSError:
            pass

    def _request_conflict(self, existing: Path, temp_source: Path) -> ConflictDecision:
        decision = None
        if self.conflict_callback:
            try:
                decision = self.conflict_callback(existing, temp_source)
            except TypeError:
                decision = self.conflict_callback(existing, existing)  # type: ignore
        if not decision:
            decision = ConflictDecision('rename')
        if decision.action == 'rename' and not decision.new_path:
            decision = ConflictDecision('rename', new_path=suggest_rename(existing))
        return decision


class FileTransferManager(QObject):
    task_added = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._tasks: List[QObject] = []

    def start_transfer(self, sources: List[str], destination_dir: str, move: bool,
                       conflict_callback=None) -> FileTransferTask:
        task = FileTransferTask(sources, destination_dir, move, conflict_callback)
        self._tasks.append(task)
        task.finished.connect(lambda *_: self._tasks.remove(task) if task in self._tasks else None)
        self.task_added.emit(task)
        task.start()
        return task

    def start_download(self, urls: List[str], destination_dir: str,
                       conflict_callback=None) -> DownloadTask:
        task = DownloadTask(urls, destination_dir, conflict_callback)
        self._tasks.append(task)
        task.finished.connect(lambda *_: self._tasks.remove(task) if task in self._tasks else None)
        self.task_added.emit(task)
        task.start()
        return task

    def active_tasks(self):
        return list(self._tasks)
