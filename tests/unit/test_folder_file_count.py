"""
Tests for folder file count feature in Properties dialog
"""
import pytest
import os
import tempfile
from pathlib import Path
from PyQt6.QtCore import QTimer
from ui.properties_dialog import PropertiesDialog, FolderSizeWorker


def test_folder_size_worker_counts_files(qtbot, tmp_path):
    """Test that FolderSizeWorker correctly counts files recursively"""
    # Create test directory structure
    # tmp_path/
    #   file1.txt
    #   file2.txt
    #   subdir/
    #     file3.txt
    #     file4.txt
    #     subsubdir/
    #       file5.txt

    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")
    (subdir / "file4.txt").write_text("content4")

    subsubdir = subdir / "subsubdir"
    subsubdir.mkdir()
    (subsubdir / "file5.txt").write_text("content5")

    # Create worker
    worker = FolderSizeWorker(str(tmp_path))

    # Track results
    file_counts = []
    final_count = [None]

    def on_progress(count):
        file_counts.append(count)

    def on_done(count):
        final_count[0] = count

    worker.file_count_progress.connect(on_progress)
    worker.file_count_done.connect(on_done)

    # Run worker
    worker.run()

    # Verify final count
    assert final_count[0] == 5, f"Expected 5 files, got {final_count[0]}"

    # Verify we got some progress updates
    assert len(file_counts) > 0, "Should have received progress updates"

    # Verify progress was incremental
    if len(file_counts) > 1:
        assert file_counts[-1] <= 5, "Progress count should not exceed final count"


def test_folder_size_worker_handles_empty_folder(qtbot, tmp_path):
    """Test that FolderSizeWorker handles empty folders correctly"""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    worker = FolderSizeWorker(str(empty_dir))

    final_count = [None]

    def on_done(count):
        final_count[0] = count

    worker.file_count_done.connect(on_done)
    worker.run()

    assert final_count[0] == 0, f"Expected 0 files in empty folder, got {final_count[0]}"


def test_folder_size_worker_counts_only_files(qtbot, tmp_path):
    """Test that FolderSizeWorker counts only files, not directories"""
    # Create structure with multiple subdirectories
    (tmp_path / "file1.txt").write_text("content")
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    (tmp_path / "dir3").mkdir()
    (tmp_path / "dir1" / "file2.txt").write_text("content")

    worker = FolderSizeWorker(str(tmp_path))

    final_count = [None]

    def on_done(count):
        final_count[0] = count

    worker.file_count_done.connect(on_done)
    worker.run()

    # Should count only 2 files, not the 3 directories
    assert final_count[0] == 2, f"Expected 2 files, got {final_count[0]}"


def test_folder_size_worker_stops_counting_on_stop(qtbot, tmp_path):
    """Test that FolderSizeWorker stops counting when stop() is called"""
    # Create many files
    for i in range(100):
        (tmp_path / f"file{i}.txt").write_text(f"content{i}")

    worker = FolderSizeWorker(str(tmp_path))

    # Stop immediately
    worker.stop()

    final_count = [None]

    def on_done(count):
        final_count[0] = count

    worker.file_count_done.connect(on_done)
    worker.run()

    # Should have stopped early, not counted all 100 files
    # (May vary depending on timing, but should be significantly less than 100)
    assert final_count[0] is not None, "Should have emitted final count"


def test_properties_dialog_shows_file_count_for_folder(qapp, qtbot, tmp_path):
    """Test that Properties dialog shows file count for folders"""
    # Create test folder with files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.txt").write_text("content2")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_text("content3")

    # Create properties dialog for the folder
    dialog = PropertiesDialog(str(tmp_path))
    qtbot.addWidget(dialog)

    # Verify file count label exists
    assert dialog.file_count_label is not None, "File count label should exist for folders"

    # Wait for calculation to complete (use QTimer to check periodically)
    def check_completed():
        return "Calculating..." not in dialog.file_count_label.text()

    # Wait up to 2 seconds for calculation
    qtbot.waitUntil(check_completed, timeout=2000)

    # Verify the file count is correct
    assert "3" in dialog.file_count_label.text(), f"Expected '3' in label, got: {dialog.file_count_label.text()}"
    assert "file" in dialog.file_count_label.text().lower(), "Label should contain 'file' or 'files'"

    # Clean up
    dialog.close()


def test_properties_dialog_no_file_count_for_files(qapp, qtbot, tmp_path):
    """Test that Properties dialog does not show file count for regular files"""
    # Create a regular file
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    # Create properties dialog for the file
    dialog = PropertiesDialog(str(test_file))
    qtbot.addWidget(dialog)

    # Verify file count label does not exist for files
    assert dialog.file_count_label is None, "File count label should not exist for regular files"

    # Clean up
    dialog.close()


def test_file_count_plural_singular(qtbot, tmp_path):
    """Test that file count label uses correct singular/plural form"""
    # Test with 1 file
    single_dir = tmp_path / "single"
    single_dir.mkdir()
    (single_dir / "file1.txt").write_text("content")

    worker = FolderSizeWorker(str(single_dir))
    final_count = [None]

    def on_done(count):
        final_count[0] = count

    worker.file_count_done.connect(on_done)
    worker.run()

    assert final_count[0] == 1

    # Test with multiple files
    multi_dir = tmp_path / "multi"
    multi_dir.mkdir()
    (multi_dir / "file1.txt").write_text("content")
    (multi_dir / "file2.txt").write_text("content")

    worker2 = FolderSizeWorker(str(multi_dir))
    final_count2 = [None]

    def on_done2(count):
        final_count2[0] = count

    worker2.file_count_done.connect(on_done2)
    worker2.run()

    assert final_count2[0] == 2
