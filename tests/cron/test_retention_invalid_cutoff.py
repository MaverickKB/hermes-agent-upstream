import logging
from datetime import UTC, datetime, timedelta

import pytest

from cron import jobs


def _seed_jobs(monkeypatch):
    now = datetime(2026, 1, 31, 12, tzinfo=UTC)
    completed_at = now - timedelta(days=30)
    monkeypatch.setattr(jobs, "_hermes_now", lambda: completed_at)
    completed = jobs.create_job(prompt="Once", schedule="in 1m")
    assert jobs.mark_job_run(completed["id"], success=True)
    completed = jobs.get_job(completed["id"])
    assert completed["state"] == "completed"
    monkeypatch.setattr(jobs, "_hermes_now", lambda: now)
    recurring = jobs.create_job(prompt="Recurring", schedule="every 1h")
    assert jobs.trigger_job(recurring["id"]) is not None
    return completed, recurring["id"]


@pytest.mark.parametrize("retention", [".nan", ".inf", "1.0e300", "4000000"])
def test_invalid_retention_keeps_completed_jobs_and_recurring_dispatch(tmp_path, monkeypatch, caplog, retention):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        f"cron:\n  completed_retention_days: {retention}\n", encoding="utf-8"
    )
    with jobs.use_cron_store(tmp_path):
        completed, recurring_id = _seed_jobs(monkeypatch)

        due = jobs.get_due_jobs()

        assert [job["id"] for job in due] == [recurring_id]
        assert jobs.get_job(completed["id"]) == completed
    assert any(
        record.levelno >= logging.WARNING and "completed_retention_days" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize("retention,pruned", [(7, True), (0, False), (-1, False)])
def test_valid_retention_preserves_pruning_and_disabled_sweeps(tmp_path, monkeypatch, retention, pruned):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        f"cron:\n  completed_retention_days: {retention}\n", encoding="utf-8"
    )
    with jobs.use_cron_store(tmp_path):
        completed, recurring_id = _seed_jobs(monkeypatch)

        due = jobs.get_due_jobs()

        assert [job["id"] for job in due] == [recurring_id]
        if pruned:
            assert jobs.get_job(completed["id"]) is None
        else:
            assert jobs.get_job(completed["id"]) == completed
