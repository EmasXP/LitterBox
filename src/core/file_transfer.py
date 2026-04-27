"""Asynchronous file transfer utilities with progress, conflicts and cancellation."""
from __future__ import annotations

import os
import shutil
import threading
import tempfile
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

CHUNK_SIZE = 1024 * 512  # 512KB


# --- Linux renameat2 / RENAME_NOREPLACE support (best-effort) ---------------
_RENAME_NOREPLACE = 1
_renameat2 = None
try:  # pragma: no cover - platform dependent
    import ctypes
    import ctypes.util

    _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    if hasattr(_libc, "renameat2"):
        _renameat2 = _libc.renameat2
        _renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p,
            ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        _renameat2.restype = ctypes.c_int
except Exception:  # pragma: no cover
    _renameat2 = None

_AT_FDCWD = -100


def _atomic_rename_noreplace(src: Path, dest: Path) -> bool:
    """Atomically rename ``src`` to ``dest`` only if ``dest`` does not exist.

    Uses Linux's renameat2(RENAME_NOREPLACE) to close the TOCTOU window
    between an exists() check and rename(). Returns True on success, False
    on any error (caller should fall back to the copy path).
    """
    if _renameat2 is not None:
        try:
            import ctypes
            res = _renameat2(
                _AT_FDCWD, os.fsencode(str(src)),
                _AT_FDCWD, os.fsencode(str(dest)),
                _RENAME_NOREPLACE,
            )
            if res == 0:
                return True
            # Any error (EEXIST, EXDEV, EINVAL on unsupported FS, ...) -> fallback
            return False
        except Exception:
            return False
    # Fallback for non-Linux: best-effort exists()+rename. Race window is
    # small and the caller will fall through to the copy path on failure.
    try:
        if dest.exists():
            return False
        os.rename(src, dest)
        return True
    except OSError:
        return False


def _same_path(a: Path, b: Path) -> bool:
    """Return True if two paths refer to the same filesystem entry.

    Resilient to non-existent destinations: compares by ``samefile`` when
    both exist, otherwise by resolved string. Never raises.
    """
    try:
        if a.exists() and b.exists():
            return a.samefile(b)
    except OSError:
        pass
    try:
        return os.path.realpath(str(a)) == os.path.realpath(str(b))
    except OSError:
        return False


def _is_safe_sibling(candidate: Path, dest: Path) -> bool:
    """Return True if ``candidate`` lives directly inside ``dest.parent``.

    Used to defend against path-traversal in user-supplied rename targets
    (e.g. '../../etc/passwd'). Compares resolved parents so that '..',
    symlinks, and absolute paths cannot escape the destination directory.
    """
    try:
        parent_resolved = dest.parent.resolve()
        candidate_parent_resolved = candidate.parent.resolve()
    except OSError:
        return False
    if candidate_parent_resolved != parent_resolved:
        return False
    name = candidate.name
    if not name or name in ('.', '..'):
        return False
    if '/' in name or '\\' in name or '\x00' in name:
        return False
    return True


def check_infinite_recursion(sources: List[str], destination_dir: str) -> Optional[str]:
    """Check if copying/moving would cause infinite recursion.

    Returns None if safe, or an error message string if recursion would occur.
    """
    dest_path = Path(os.path.abspath(destination_dir))

    for source in sources:
        src_path = Path(os.path.abspath(source))

        # Skip if source doesn't exist or is not a directory
        if not src_path.exists() or not src_path.is_dir():
            continue

        # Check if destination is inside the source directory
        try:
            # Use resolve() to handle symlinks and normalize paths
            resolved_dest = dest_path.resolve()
            resolved_src = src_path.resolve()

            # Check if destination is the source itself or a subdirectory
            if resolved_dest == resolved_src:
                return f"Cannot copy '{src_path.name}' into itself."

            # Check if destination is inside source
            try:
                resolved_dest.relative_to(resolved_src)
                # If we get here, dest is inside src - this would cause infinite recursion
                return f"Cannot copy '{src_path.name}' into its own subdirectory '{dest_path.name}'.\n\nThis would create an infinite loop."
            except ValueError:
                # dest is not inside src, this is fine
                pass

        except (OSError, RuntimeError):
            # If we can't resolve paths (broken symlinks, etc), skip check for this source
            continue

    return None


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
        self._apply_all_skip = False
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

    def _path_size(self, path: Path) -> int:
        """Return total byte size of a file or directory tree (best effort)."""
        try:
            if path.is_dir():
                total = 0
                for root, _dirs, files in os.walk(path):
                    for f in files:
                        try:
                            total += (Path(root) / f).stat().st_size
                        except OSError:
                            pass
                return total
            return path.stat().st_size
        except OSError:
            return 0

    def _run(self):
        try:
            pairs = self._enumerate()
            self._compute_total(pairs)
            self.progress_changed.emit(0, self._total)
            for src, dest, is_dir in pairs:
                if self._cancel.is_set():
                    raise RuntimeError('Cancelled')

                # Same-path no-op detection: cut+paste in same dir, or drag
                # to current dir. Without this, the move post-copy unlink
                # would delete the file we just "moved" onto itself.
                if _same_path(src, dest):
                    if self.move:
                        # No-op move; account for size and continue.
                        size = self._path_size(src)
                        self._done += size
                        self.progress_changed.emit(self._done, self._total)
                        self.file_progress.emit(str(dest))
                        continue
                    # Copy in place: auto-rename so we don't clobber the source.
                    dest = suggest_rename(dest)

                # Fast path: for move with no destination conflict, try an
                # atomic rename. Use renameat2(RENAME_NOREPLACE) on Linux
                # when available to close the TOCTOU window between
                # exists()-check and rename(). Falls back to the copy +
                # per-file delete path on EXDEV or any other OSError.
                if self.move and not dest.exists():
                    size = self._path_size(src)
                    if _atomic_rename_noreplace(src, dest):
                        self._done += size
                        self.progress_changed.emit(self._done, self._total)
                        self.file_progress.emit(str(dest))
                        continue

                # Conflict resolution happens inside the copier (exactly once per item).
                # Per-file move semantics: _copy_file / _copy_dir_with_conflicts
                # remove each successfully-copied source themselves, so files
                # the user chose to skip are NOT deleted from the source.
                if is_dir:
                    self._copy_dir_with_conflicts(src, dest)
                else:
                    self._copy_file(src, dest)
            self.finished.emit(True, '')
        except Exception as e:
            if str(e) == 'Cancelled':
                self.finished.emit(False, 'Cancelled')
            else:
                self.finished.emit(False, str(e))

    def _resolve_conflict(self, src: Path, dest: Path) -> Optional[Path]:
        """Resolve a destination conflict, prompting the user if needed.

        Returns the destination Path to use (possibly renamed), or None to skip.
        Sets the cancel flag if the user picks 'cancel'.
        Honors the 'apply to all' flags for overwrite and skip.
        """
        if not dest.exists():
            return dest

        # Type-mismatch protection: if the source and existing destination
        # are different kinds (file vs directory), do NOT honor a previous
        # 'apply to all overwrite' decision \u2014 silently rmtree-ing a
        # directory to make room for a single file is a data-loss footgun.
        # Always re-prompt in that case.
        try:
            src_is_dir = src.is_dir() and not src.is_symlink()
            dst_is_dir = dest.is_dir() and not dest.is_symlink()
            type_mismatch = src_is_dir != dst_is_dir
        except OSError:
            type_mismatch = False

        if not type_mismatch:
            if self._apply_all_overwrite:
                return dest
            if self._apply_all_skip:
                return None

        decision = None
        if self.conflict_callback:
            try:
                decision = self.conflict_callback(dest, src)
            except TypeError:
                # Backward compatibility: callback expecting two params but ignoring second
                decision = self.conflict_callback(dest, dest)  # type: ignore
        if not decision:
            decision = ConflictDecision('rename')

        if decision.action == 'overwrite':
            # Never let an 'apply to all' propagate from a type-mismatch
            # decision; the next file might be homogeneous and shouldn't
            # inherit a destructive choice.
            if decision.apply_all and not type_mismatch:
                self._apply_all_overwrite = True
            return dest
        if decision.action == 'rename':
            new_path = decision.new_path or suggest_rename(dest)
            # SECURITY: confine the renamed target to dest.parent to prevent
            # path-traversal via crafted new_name (e.g. '../../etc/passwd').
            # If the proposed path escapes the destination directory, fall
            # back to a safe auto-suggested name.
            if not _is_safe_sibling(new_path, dest):
                new_path = suggest_rename(dest)
            # Defensive: if proposed rename also exists, fall back to suggest_rename
            if new_path.exists():
                new_path = suggest_rename(dest)
            return new_path
        if decision.action == 'skip':
            if decision.apply_all and not type_mismatch:
                self._apply_all_skip = True
            return None
        if decision.action == 'cancel':
            self._cancel.set()
            return None
        return dest

    # Backward-compatibility alias (older callers / tests may still reference _handle_conflict).
    def _handle_conflict(self, src: Path, dest: Path):  # pragma: no cover
        return self._resolve_conflict(src, dest)

    def _copy_dir_with_conflicts(self, src: Path, dest: Path) -> bool:
        """Recursively copy a directory tree, prompting per-conflict.

        Conflict resolution for ``dest`` happens exactly once at the start.
        Returns True if the directory was copied (or no-oped) cleanly with
        every child accounted for; False if any child was skipped, failed,
        or if the user skipped this directory entirely. The return value is
        used to decide whether the source can be removed for moves.
        """
        # If the source is itself a symlink, copy it as a symlink rather
        # than recursing into its target (avoids cycles and preserves
        # link semantics). For top-level symlinked directories, _enumerate
        # currently treats them as directories; handle that here.
        if src.is_symlink():
            return self._copy_symlink(src, dest)

        resolved = self._resolve_conflict(src, dest)
        if resolved is None:
            return False  # skip
        dest = resolved

        # Type-mismatch guard: cannot create a directory where a file exists
        if dest.exists() and not dest.is_dir():
            # User chose 'overwrite' on a file with a directory source — replace it
            try:
                dest.unlink()
            except OSError:
                return False

        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False

        try:
            entries = list(src.iterdir())
        except OSError:
            entries = []
        all_copied = True
        for entry in entries:
            if self._cancel.is_set():
                raise RuntimeError('Cancelled')
            target = dest / entry.name
            # SECURITY: do not follow symlinks into arbitrary places (could
            # produce cycles or copy unrelated trees). Recreate the symlink
            # at the destination instead.
            if entry.is_symlink():
                if not self._copy_symlink(entry, target):
                    all_copied = False
                continue
            if entry.is_dir():
                if not self._copy_dir_with_conflicts(entry, target):
                    all_copied = False
            else:
                if not self._copy_file(entry, target):
                    all_copied = False

        # For moves: remove the now-empty source dir. rmdir only succeeds
        # if every child was copied (and removed). If the user skipped any
        # child, the source dir keeps the skipped file(s) and is preserved.
        if self.move and all_copied:
            try:
                src.rmdir()
            except OSError:
                # Non-empty (skipped children) or permission issue — leave it.
                all_copied = False
        return all_copied

    def _copy_file(self, src: Path, dest: Path) -> bool:
        """Copy a single file. Returns True on success, False if skipped.

        For moves, the source file is removed after a successful copy of
        *this* file (per-file move semantics). This guarantees that files
        the user chose to skip are never deleted from the source.
        """
        # Symlinks: recreate at destination instead of dereferencing.
        if src.is_symlink():
            return self._copy_symlink(src, dest)

        resolved = self._resolve_conflict(src, dest)
        if resolved is None:
            return False
        dest = resolved

        # Same-file no-op (covers in-tree corner cases beyond top-level
        # detection in _run, e.g. when 'overwrite' resolves to the source).
        if _same_path(src, dest):
            # Account for the size so progress completes; do NOT delete src.
            try:
                self._done += src.stat().st_size
            except OSError:
                pass
            self.progress_changed.emit(self._done, self._total)
            self.file_progress.emit(str(dest))
            return True

        # Type-mismatch guard: cannot write a file where a directory exists
        if dest.exists() and dest.is_dir() and not dest.is_symlink():
            # SAFETY: refuse to silently rmtree a non-empty directory just
            # to drop a file in its place. The conflict dialog disables
            # this case in the UI; reaching it means a programmatic caller
            # forced an overwrite. Skip rather than destroy user data.
            try:
                has_content = any(dest.iterdir())
            except OSError:
                has_content = True
            if has_content:
                return False
            try:
                shutil.rmtree(dest)
            except OSError:
                return False

        # Use a process-unique .part filename to avoid clobbering concurrent / leftover transfers
        temp = dest.with_suffix(dest.suffix + f'.part.{os.getpid()}.{id(self)}')
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
                    now = time.monotonic()
                    if (now - self._last_emit_monotonic) >= self._emit_interval:
                        self._last_emit_monotonic = now
                        self.file_progress.emit(str(dest))
            try:
                shutil.copystat(src, temp)
            except OSError:
                pass
            os.replace(temp, dest)  # atomic; overwrites destination on POSIX
            # For move: remove the source file now that the copy succeeded.
            # Defensive: never unlink if src and dest resolve to the same
            # path (would lose the only copy of the data).
            if self.move and not _same_path(src, dest):
                try:
                    src.unlink()
                except OSError:
                    pass
            # Final emit for this file
            self.file_progress.emit(str(dest))
            return True
        except Exception:
            try:
                if temp.exists():
                    temp.unlink()
            except OSError:
                pass
            raise

    def _copy_symlink(self, src: Path, dest: Path) -> bool:
        """Recreate a symlink at ``dest`` pointing to the same target as ``src``.

        Never follows the link. Returns True on success or no-op skip handling,
        False if the operation could not be completed.
        """
        try:
            link_target = os.readlink(src)
        except OSError:
            return False

        # Conflict resolution if something already lives at dest.
        if dest.exists() or dest.is_symlink():
            resolved = self._resolve_conflict(src, dest)
            if resolved is None:
                return False
            dest = resolved
            # Remove existing entry if we're going to overwrite.
            if dest.exists() or dest.is_symlink():
                try:
                    if dest.is_symlink() or dest.is_file():
                        dest.unlink()
                    elif dest.is_dir():
                        shutil.rmtree(dest)
                except OSError:
                    return False

        try:
            os.symlink(link_target, dest)
        except OSError:
            return False

        if self.move and not _same_path(src, dest):
            try:
                src.unlink()
            except OSError:
                pass
        self.file_progress.emit(str(dest))
        return True


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

    def validate_transfer(self, sources: List[str], destination_dir: str) -> Optional[str]:
        """Validate that a transfer operation is safe to perform.

        Returns None if valid, or an error message string if invalid.
        """
        return check_infinite_recursion(sources, destination_dir)

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
