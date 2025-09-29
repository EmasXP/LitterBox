"""Panel showing active transfers."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy
from PyQt6.QtCore import QTimer
from core.file_transfer import FileTransferTask
import time


class TransferWidget(QFrame):
    def __init__(self, task: FileTransferTask, parent=None):
        super().__init__(parent)
        self.task = task
        self._init()

    def _init(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.label = QLabel("Preparing...")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(70)
        layout.addWidget(self.label, 2)
        layout.addWidget(self.progress, 5)
        layout.addWidget(self.btn_cancel, 0)
        self.btn_cancel.clicked.connect(self.task.cancel)
        self.task.progress_changed.connect(self._on_progress)
        self.task.finished.connect(self._on_finished)
        self._start_time = time.monotonic()
        self._last_time = self._start_time
        self._last_done = 0

    def _on_progress(self, done, total):
        pct = int(done * 100 / total) if total else 0
        self.progress.setValue(pct)
        now = time.monotonic()
        delta_bytes = done - self._last_done
        delta_time = max(1e-6, now - self._last_time)
        speed = delta_bytes / delta_time  # bytes per second (instant)
        self._last_time = now
        self._last_done = done
        avg_speed = done / max(1e-6, now - self._start_time)
        remaining = ''
        if speed > 0 and done < total:
            eta_sec = int((total - done) / max(speed, 1))
            if eta_sec > 3600:
                remaining = f"ETA {eta_sec // 3600}h {(eta_sec % 3600)//60}m"
            elif eta_sec > 60:
                remaining = f"ETA {eta_sec // 60}m {eta_sec % 60}s"
            else:
                remaining = f"ETA {eta_sec}s"

        def fmt(bps: float):
            units = ["B/s", "KB/s", "MB/s", "GB/s"]
            v = float(bps)
            for u in units:
                if v < 1024 or u == units[-1]:
                    return f"{v:.1f} {u}"
                v /= 1024
            return f"{v:.1f} B/s"

        speed_str = fmt(speed)
        avg_str = fmt(avg_speed)
        parts = [f"{pct}%", f"{len(self.task.sources)} item(s)", speed_str, remaining]
        if remaining:
            parts.append(f"avg {avg_str}")
        self.label.setText(" • ".join([p for p in parts if p]))

    def _on_finished(self, success, error):
        self.btn_cancel.setEnabled(False)
        self.label.setText("Completed" if success else (error or "Failed"))


class TransferPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    def add_task(self, task: FileTransferTask):
        tw = TransferWidget(task, self)
        self.layout().addWidget(tw)
        task.finished.connect(lambda *_: self._cleanup_later(tw))

    def _cleanup_later(self, tw: TransferWidget):
        QTimer.singleShot(3000, lambda: self._remove(tw))

    def _remove(self, tw: TransferWidget):
        tw.setParent(None)
        tw.deleteLater()
