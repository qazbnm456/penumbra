"""An unset output language follows the interface language the reader last used, where no request
is there to ask (`config.reader_language`): the automatic summary pass and organising."""

from __future__ import annotations

import pytest

from penumbra import config


def test_it_is_recorded_only_when_it_changes_and_read_back_clean(tmp_path):
    assert config.reader_language(tmp_path) is None
    config.remember_reader_language("Traditional Chinese", tmp_path)
    path = tmp_path / ".reader-language"
    stamp = path.stat().st_mtime_ns
    config.remember_reader_language("Traditional Chinese", tmp_path)
    assert path.stat().st_mtime_ns == stamp
    config.remember_reader_language("  ", tmp_path)
    assert config.reader_language(tmp_path) == "Traditional Chinese"
    path.write_text("Eng\nlish\x00")
    assert "\n" not in (config.reader_language(tmp_path) or "")


def test_it_is_not_a_setting_so_the_settings_page_never_sees_it(tmp_path):
    config.remember_reader_language("Traditional Chinese", tmp_path)
    assert config.read_settings(tmp_path) == ({}, None)


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth


def test_a_request_records_it_and_background_runs_use_it(monkeypatch):
    monkeypatch.delenv("PN_OUTPUT_LANGUAGE", raising=False)
    api._READER_LANGUAGE["last"] = ""
    with TestClient(api.app, base_url="http://127.0.0.1",
                    headers={"Authorization": f"Bearer {auth.api_token()}"}) as client:
        client.get("/orbits", headers={"X-Penumbra-Interface-Language": "Traditional Chinese"})
    assert config.reader_language() == "Traditional Chinese"

    seen = {}
    monkeypatch.setattr(api.distill, "distil_pending", lambda **kw: seen.update(kw))
    monkeypatch.setattr(api, "_configure_in_process_model", lambda: None)
    monkeypatch.setattr(api, "_organize_after_pass", lambda *a: None)

    class Queue:
        base_dir = "horizon"
        cancel_generation = 0

        def has_pending_work(self):
            return False

    class Node:
        chars = 10

    monkeypatch.setattr(api.intake, "shared", lambda: Queue())
    monkeypatch.setattr(api.horizon, "list_nodes", lambda **kw: [Node()])
    monkeypatch.setattr(api, "_vector_worker", lambda: type("W", (), {"nudge": lambda self: None})())
    monkeypatch.setattr(api, "_auto_file_suggested", lambda: 0)
    monkeypatch.setattr(api, "auto_distil_enabled", lambda: True)
    with api._DISTIL_GUARD:
        api._DISTIL.update({"running": False, "cancel": False})
    api._auto_distil_after_intake()
    assert seen.get("language") == "Traditional Chinese"
