"""`hermes sessions export` single-file formats accept a directory as OUTPUT."""

import json
import sys
from pathlib import Path

import hermes_state
import hermes_cli.main as main_mod


class _FakeDB:
    def resolve_session_id(self, session_id):
        return "sess-123"

    def export_session(self, session_id, **_projection):
        return {"id": "sess-123", "source": "cli", "messages": [{"role": "user", "content": "hi"}]}

    def assert_exports_safe(self, session_ids, max_messages=None):
        return None

    def close(self):
        pass


def _export(monkeypatch, *argv):
    # Read-only observation commands short-circuit when state.db is absent; the fake DB
    # stands in for the file that would otherwise be opened read-only.
    from hermes_constants import get_hermes_home
    (get_hermes_home() / "state.db").touch()
    monkeypatch.setattr(hermes_state, "SessionDB", lambda **_kw: _FakeDB())
    monkeypatch.setattr(sys, "argv", ["hermes", "sessions", "export", "--session-id", "sess", *argv])
    main_mod.main()


def test_jsonl_export_into_directory_writes_default_named_file(monkeypatch, tmp_path):
    out_dir = tmp_path / "saved"
    out_dir.mkdir()

    _export(monkeypatch, f"{out_dir}/")

    written = out_dir / "hermes_session_sess-123.jsonl"
    assert json.loads(written.read_text(encoding="utf-8"))["id"] == "sess-123"


def test_jsonl_export_to_file_path_is_unchanged(monkeypatch, tmp_path):
    target = tmp_path / "one.jsonl"

    _export(monkeypatch, str(target))

    assert json.loads(target.read_text(encoding="utf-8"))["id"] == "sess-123"
    assert target.is_file() and not (tmp_path / "hermes_session_sess-123.jsonl").exists()


def test_jsonl_export_expands_user_directory(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(work)

    _export(monkeypatch, "~/My Exports/")

    written = home / "My Exports" / "hermes_session_sess-123.jsonl"
    output = capsys.readouterr().out
    reported = output.strip().removeprefix("Exported 1 session to ")
    assert json.loads(written.read_text(encoding="utf-8"))["id"] == "sess-123"
    assert Path(reported) == written
    assert not (work / "~").exists()


def test_jsonl_export_expands_user_file(monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    work = tmp_path / "work"
    output_dir = home / "My Exports"
    output_dir.mkdir(parents=True)
    work.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(work)

    _export(monkeypatch, "~/My Exports/chosen.jsonl")

    written = output_dir / "chosen.jsonl"
    output = capsys.readouterr().out
    reported = output.strip().removeprefix("Exported 1 session to ")
    assert json.loads(written.read_text(encoding="utf-8"))["id"] == "sess-123"
    assert Path(reported) == written
    assert not (output_dir / "hermes_session_sess-123.jsonl").exists()
    assert not (work / "~").exists()
