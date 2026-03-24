"""Tests for base service interface."""
from google_backup.services.base import SyncResult


def test_sync_result_has_errors_when_items_failed():
    result = SyncResult(
        service="test",
        items_synced=10,
        items_failed=2,
        items_deleted=0,
        failed_ids=["a", "b"],
        elapsed_seconds=1.5,
    )
    assert result.has_errors is True


def test_sync_result_no_errors_when_all_succeed():
    result = SyncResult(
        service="test",
        items_synced=10,
        items_failed=0,
        items_deleted=0,
        failed_ids=[],
        elapsed_seconds=1.0,
    )
    assert result.has_errors is False


def test_sync_result_summary_format():
    result = SyncResult(
        service="gmail",
        items_synced=100,
        items_failed=3,
        items_deleted=5,
        failed_ids=["x", "y", "z"],
        elapsed_seconds=12.34,
    )
    summary = result.summary()
    assert "gmail" in summary
    assert "100" in summary
    assert "3 failed" in summary
    assert "5 deleted" in summary
