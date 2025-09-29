"""Clipboard integration for copy/cut of files (interoperable with other file managers)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import os
from urllib.parse import urlparse, unquote

from PyQt6.QtGui import QGuiApplication, QClipboard
from PyQt6.QtCore import QUrl, QMimeData


GNOME_MIME = 'x-special/gnome-copied-files'
KDE_CUT_MIME = 'application/x-kde-cutselection'  # contains '1' for cut, '0' for copy


@dataclass
class ClipboardContent:
    operation: str  # 'copy' or 'cut'
    paths: List[str]


class ClipboardManager:
    @staticmethod
    def set_files(paths: List[str], operation: str = 'copy') -> None:
        if operation not in ('copy', 'cut'):
            operation = 'copy'
        mime = QMimeData()
        lines = [operation]
        for p in paths:
            lines.append('file://' + os.path.abspath(p))
        payload = '\n'.join(lines)
        mime.setData(GNOME_MIME, payload.encode('utf-8'))
        # KDE expects an extra MIME with 1 (cut) or 0 (copy)
        mime.setData(KDE_CUT_MIME, b'1' if operation == 'cut' else b'0')
        mime.setText('\n'.join([os.path.abspath(p) for p in paths]))
        urls = [QUrl.fromLocalFile(os.path.abspath(p)) for p in paths]
        mime.setUrls(urls)
        QGuiApplication.clipboard().setMimeData(mime, QClipboard.Mode.Clipboard)

    @staticmethod
    def get_files() -> Optional[ClipboardContent]:
        cb = QGuiApplication.clipboard()
        mime = cb.mimeData(QClipboard.Mode.Clipboard)
        if not mime:
            return None
        # GNOME format
        if mime.hasFormat(GNOME_MIME):
            try:
                data = bytes(mime.data(GNOME_MIME)).decode('utf-8', 'ignore')
                lines = [l for l in data.splitlines() if l.strip()]
                if not lines:
                    return None
                op = 'copy'
                if lines[0] in ('copy', 'cut'):
                    op = lines[0]
                    file_lines = lines[1:]
                else:
                    file_lines = lines
                paths = []
                for line in file_lines:
                    if line.startswith('file://'):
                        parsed = urlparse(line)
                        path = unquote(parsed.path)
                        if path and os.path.exists(path):
                            paths.append(path)
                if paths:
                    return ClipboardContent(op, paths)
            except Exception:
                return None
        # KDE cut/copy additional hint combined with URLs
        if mime.hasFormat(KDE_CUT_MIME) and mime.hasUrls():
            try:
                op = 'cut' if bytes(mime.data(KDE_CUT_MIME)).startswith(b'1') else 'copy'
                paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and os.path.exists(u.toLocalFile())]
                if paths:
                    return ClipboardContent(op, paths)
            except Exception:
                pass
        # URLs fallback
        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and os.path.exists(u.toLocalFile())]
            if paths:
                return ClipboardContent('copy', paths)
        # Plain text fallback
        if mime.hasText():
            candidates = [l.strip() for l in mime.text().splitlines() if l.strip()]
            paths = [c for c in candidates if os.path.exists(c)]
            if paths:
                return ClipboardContent('copy', paths)
        return None
