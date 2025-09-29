"""Filesystem watching utilities for LitterBox.

Non-recursive directory monitoring per open tab using watchdog.
Each watched directory is refreshed (debounced) on create, delete, move, or
metadata/content modification of its immediate children (not deep descendants).

If watchdog isn't available at runtime, the module degrades gracefully;
FileWatcherManager.start_watch will return False and no automatic refresh
occurs (manual refreshes still work through existing operations).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional, Any
import threading

# Watchdog imports guarded so the rest of the app can still run if missing
try:  # pragma: no cover - import error path is environment dependent
    from watchdog.observers import Observer  # type: ignore
    from watchdog.events import FileSystemEventHandler, FileSystemEvent  # type: ignore
    _WATCHDOG_AVAILABLE = True
except Exception:  # noqa: BLE001
    from typing import Any as Observer  # type: ignore
    from typing import Any as FileSystemEventHandler  # type: ignore
    from typing import Any as FileSystemEvent  # type: ignore
    _WATCHDOG_AVAILABLE = False

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# ---------------- Internal Event Handler ---------------- #
class _DirectoryEventHandler(FileSystemEventHandler):  # type: ignore[misc]
    """Handles filesystem events for a single directory (non-recursive)."""

    def __init__(self, callback: Callable[[], None]):
        self._callback = callback

    # Any event in this (non-recursive) directory triggers refresh
    def on_any_event(self, event: FileSystemEvent):  # pragma: no cover - thin wrapper
        try:
            self._callback()
        except Exception:
            pass

# ---------------- Watch Data Structure ---------------- #
@dataclass
class _WatchEntry:
    path: Path
    timer: QTimer
    refresh_fn: Callable[[], None]
    watch_obj: Any  # ObservedWatch from watchdog
    handler: Any
    dirty: bool = False

# ---------------- Public Manager ---------------- #
class FileWatcherManager(QObject):
    """Singleton-like manager that tracks active directory watches.

    Usage (from UI code):
        watcher = FileWatcherManager.instance()
        watcher.start_watch(path, unique_id, refresh_callback)
        ... later ...
        watcher.stop_watch(unique_id)

    unique_id allows one watch per tab; navigating reuses same id with new path.
    """

    # Emitted after a debounced directory change (for optional global listeners)
    directory_changed = pyqtSignal(str)

    _instance: Optional['FileWatcherManager'] = None

    DEBOUNCE_MS = 250

    def __init__(self):  # pragma: no cover - Qt object creation
        super().__init__()
        # Store observer instance (runtime type only if available)
        self._observer: Optional[object] = None
        self._watches: Dict[str, _WatchEntry] = {}
        self._lock = threading.Lock()
        if _WATCHDOG_AVAILABLE:
            try:
                obs: Any = Observer()  # type: ignore
                obs.start()
                self._observer = obs
            except Exception:  # noqa: BLE001
                self._observer = None

    # -------- Singleton Access -------- #
    @classmethod
    def instance(cls) -> 'FileWatcherManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -------- Public API -------- #
    def start_watch(self, directory: str, watch_id: str, refresh_fn: Callable[[], None]) -> bool:
        """Start (or update) a watch for the given directory with an id.

        Returns True if watch active, False if watchdog unavailable or error.
        """
        if not _WATCHDOG_AVAILABLE:
            return False
        path_obj = Path(directory).resolve()
        if not path_obj.is_dir():
            return False

        with self._lock:
            # If existing watch for id and path changed, remove old schedule
            existing = self._watches.get(watch_id)
            if existing and existing.path != path_obj:
                # Path change: unschedule old and remove entry
                try:
                    if self._observer and existing.watch_obj:
                        obs: Any = self._observer
                        obs.unschedule(existing.watch_obj)
                except Exception:
                    pass
                existing.timer.stop()
                del self._watches[watch_id]

            if watch_id not in self._watches:
                # Create debounce timer
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.setInterval(self.DEBOUNCE_MS)
                handler = _DirectoryEventHandler(lambda wid=watch_id: self._mark_dirty_id(wid))
                watch_obj = None
                if self._observer is None:
                    return False
                try:
                    obs: Any = self._observer
                    watch_obj = obs.schedule(handler, str(path_obj), recursive=False)
                except Exception:  # noqa: BLE001
                    watch_obj = None
                if watch_obj is None:
                    return False
                entry = _WatchEntry(path=path_obj, timer=timer, refresh_fn=refresh_fn, watch_obj=watch_obj, handler=handler)
                self._watches[watch_id] = entry
                timer.timeout.connect(lambda wid=watch_id: self._emit_refresh_id(wid))
            else:
                # Path same; nothing to change
                pass

        return True

    def stop_watch(self, watch_id: str):
        with self._lock:
            entry = self._watches.pop(watch_id, None)
            if entry:
                try:
                    if self._observer and entry.watch_obj:
                        obs: Any = self._observer
                        obs.unschedule(entry.watch_obj)
                except Exception:
                    pass
                entry.timer.stop()

    def stop_all(self):  # pragma: no cover - used at shutdown
        with self._lock:
            for wid, entry in list(self._watches.items()):
                try:
                    if self._observer and entry.watch_obj:
                        obs: Any = self._observer
                        obs.unschedule(entry.watch_obj)
                except Exception:
                    pass
                entry.timer.stop()
            self._watches.clear()
            if self._observer:
                try:
                    obs: Any = self._observer
                    obs.stop()
                    obs.join(timeout=1)
                except Exception:
                    pass

    # -------- Internal Helpers -------- #
    def _mark_dirty(self, entry: _WatchEntry):  # Called from observer thread
        # Move to Qt thread by starting the timer via single-shot invocation
        def start_timer():
            entry.dirty = True
            if not entry.timer.isActive():
                entry.timer.start()
        # Use singleShot to ensure thread-safety (Qt main thread execution)
        QTimer.singleShot(0, start_timer)

    def _emit_refresh(self, entry: _WatchEntry):
        if entry.dirty:
            entry.dirty = False
            try:
                entry.refresh_fn()
            except Exception:
                pass
            self.directory_changed.emit(str(entry.path))

    # --- ID helpers (avoid capturing whole entry in lambdas repeatedly) ---
    def _mark_dirty_id(self, watch_id: str):  # Called from observer thread
        with self._lock:
            entry = self._watches.get(watch_id)
        if entry:
            self._mark_dirty(entry)

    def _emit_refresh_id(self, watch_id: str):
        with self._lock:
            entry = self._watches.get(watch_id)
        if entry:
            self._emit_refresh(entry)

# Convenience function if needed elsewhere
get_file_watcher = FileWatcherManager.instance
