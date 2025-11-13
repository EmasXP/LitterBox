import os
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from ui.main_window import FileTab
from core.file_operations import FileOperations


def _make_files(tmp_path):
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.log").write_text("b")


def test_trash_shortcut_confirmation_accept(qapp, tmp_path, monkeypatch):
    _make_files(tmp_path)
    tab = FileTab(str(tmp_path))
    # Prevent background timers
    if hasattr(tab, '_poll_timer'): tab._poll_timer.stop()
    if hasattr(tab, '_watch_refresh_timer'): tab._watch_refresh_timer.stop()
    qapp.processEvents()

    # Select both files
    fl = tab.file_list
    assert fl.select_item_by_name("alpha.txt")
    # Add beta.log to selection without clearing first selection
    for row in range(fl.source_model.rowCount()):
        item = fl.source_model.item(row, 0)
        if not item:
            continue
        p = item.data(Qt.ItemDataRole.UserRole)
        if os.path.basename(p) == "beta.log":
            src_index = fl.source_model.index(row, 0)
            proxy_index = fl.proxy_model.mapFromSource(src_index)
            sel_model = fl.selectionModel()
            if sel_model and proxy_index.isValid():
                sel_model.select(proxy_index, sel_model.SelectionFlag.Select | sel_model.SelectionFlag.Rows)  # type: ignore[attr-defined]
            break

    trashed = []
    def fake_move_to_trash(path):
        trashed.append(os.path.basename(path))
        return True, ""
    monkeypatch.setattr(FileOperations, "move_to_trash", fake_move_to_trash)

    # Simulate user clicking Yes in confirmation dialog
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)

    QTest.keyClick(fl, Qt.Key.Key_Delete)  # type: ignore[arg-type]
    # Both files should be trashed after confirmation
    assert set(trashed) == {"alpha.txt", "beta.log"}


def test_trash_shortcut_confirmation_cancel(qapp, tmp_path, monkeypatch):
    _make_files(tmp_path)
    tab = FileTab(str(tmp_path))
    if hasattr(tab, '_poll_timer'): tab._poll_timer.stop()
    if hasattr(tab, '_watch_refresh_timer'): tab._watch_refresh_timer.stop()
    qapp.processEvents()

    fl = tab.file_list
    assert fl.select_item_by_name("alpha.txt")

    trashed = []
    def fake_move_to_trash(path):
        trashed.append(os.path.basename(path))
        return True, ""
    monkeypatch.setattr(FileOperations, "move_to_trash", fake_move_to_trash)

    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.No)

    QTest.keyClick(fl, Qt.Key.Key_Delete)  # type: ignore[arg-type]
    # User canceled; nothing trashed
    assert trashed == []
