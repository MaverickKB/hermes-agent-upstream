import time

import pytest

from agent.insights import InsightsEngine
from hermes_state import SessionDB


@pytest.fixture()
def db(tmp_path):
    session_db = SessionDB(db_path=tmp_path / "state.db")
    yield session_db
    session_db.close()


@pytest.mark.parametrize("duration_seconds", [-60, 0])
def test_nonpositive_duration_is_not_ranked_as_longest(db, duration_seconds):
    started_at = time.time() - 600
    db.create_session(session_id="clock-drift", source="cli", model="test-model")
    db.append_message("clock-drift", role="user", content="hello")
    db.update_token_counts("clock-drift", input_tokens=3, output_tokens=2)
    db.end_session("clock-drift", end_reason="user_exit")
    db._conn.execute(
        "UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = ?",
        (started_at, started_at + duration_seconds, "clock-drift"),
    )
    db._conn.commit()

    engine = InsightsEngine(db)
    report = engine.generate(days=30)
    terminal = engine.format_terminal(report)

    assert report["overview"]["total_sessions"] == 1
    assert report["overview"]["total_messages"] == 1
    assert report["overview"]["total_tokens"] == 5
    assert report["overview"]["total_hours"] == 0
    assert report["overview"]["avg_session_duration"] == 0
    assert not any(item["label"] == "Longest session" for item in report["top_sessions"])
    assert any(
        item["label"] == "Most messages" and item["session_id"] == "clock-drift"
        for item in report["top_sessions"]
    )
    assert "Longest session" not in terminal


def test_positive_duration_remains_eligible_for_longest_session(db):
    started_at = time.time() - 600
    db.create_session(session_id="positive", source="cli", model="test-model")
    db.append_message("positive", role="user", content="hello")
    db.end_session("positive", end_reason="user_exit")
    db._conn.execute(
        "UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = ?",
        (started_at, started_at + 120, "positive"),
    )
    db._conn.commit()

    engine = InsightsEngine(db)
    report = engine.generate(days=30)
    terminal = engine.format_terminal(report)

    longest = next(item for item in report["top_sessions"] if item["label"] == "Longest session")
    assert longest["session_id"] == "positive"
    assert longest["value"] == "2m"
    assert report["overview"]["total_hours"] == pytest.approx(120 / 3600)
    assert report["overview"]["avg_session_duration"] == 120
    assert "Longest session" in terminal
    assert "2m" in terminal
