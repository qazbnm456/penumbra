"""Clearing everything (`POST /data/clear`): every orbit, capture and trace goes; the settings, the
paired extension and the embedding model stay; and nothing is cleared while work is running."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, intake
from penumbra.orbit import list_orbit_summaries


@pytest.fixture(autouse=True)
def _fresh_queue():
    yield
    if intake._SHARED is not None:
        intake._SHARED.stop(timeout=5)
    intake._SHARED = None


@pytest.fixture
def client():
    with TestClient(
        api.app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {auth.api_token()}"}
    ) as c:
        yield c


def _capture(client, text: str) -> str:
    node_id = client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]["id"]
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            return node_id
        time.sleep(0.02)
    raise AssertionError("the capture never became readable")


def test_clearing_removes_what_the_reader_made_and_keeps_the_setup(client):
    kept = _capture(client, "Lighthouses guide ships along the coast at night.")
    filed = _capture(client, "Origami is the art of folding paper into shapes.")
    promoted = client.post(f"/horizon/{filed}/promote", json={"orbit_id": "crafts", "create": True})
    assert promoted.status_code == 200
    client.delete(f"/horizon/{kept}")
    base = Path(api._horizon_queue_base())
    (base / ".capture-token").write_text("paired", encoding="utf-8")
    Path("orbits/.settings").write_text("{}", encoding="utf-8")
    api._TRACE_DIR.mkdir(parents=True, exist_ok=True)
    (api._TRACE_DIR / "run-1.jsonl").write_text("", encoding="utf-8")  # a run reservation, ours

    assert client.post("/data/clear", json={"confirm": "nope"}).status_code == 400
    reply = client.post("/data/clear", json={"confirm": "clear everything"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["orbits"] == 1 and reply.json()["captures"] == 1

    assert horizon.list_nodes() == [] and horizon.removal_events() == []
    assert list_orbit_summaries() == ([], [])
    assert not list((base / "nodes").glob("nd-*.json"))
    assert not list(api._TRACE_DIR.glob("*.jsonl"))
    assert (base / ".capture-token").read_text(encoding="utf-8") == "paired", "the pairing stays"
    assert Path("orbits/.settings").exists(), "the settings stay"
    # The Horizon still works afterwards.
    assert _capture(client, "A fresh start.")


def test_nothing_is_cleared_while_work_is_running(client, monkeypatch):
    node_id = _capture(client, "Something kept.")
    monkeypatch.setitem(api._DISTIL, "running", True)
    reply = client.post("/data/clear", json={"confirm": "clear everything"})
    assert reply.status_code == 409 and "summary pass" in reply.json()["detail"]
    assert horizon.get_node(node_id) is not None


def test_another_tools_traces_survive(client):
    api._TRACE_DIR.mkdir(parents=True, exist_ok=True)
    ours = api._TRACE_DIR / "run-ours.jsonl"
    ours.write_text("", encoding="utf-8")  # a reservation this project makes before a run
    foreign = api._TRACE_DIR / "other-tool.jsonl"
    foreign.write_text('{"tool": "someone else"}\n', encoding="utf-8")
    assert client.post("/data/clear", json={"confirm": "clear everything"}).status_code == 200
    assert not ours.exists()
    assert foreign.exists(), "a .jsonl this project did not write is not ours to delete"


def test_an_orbit_being_edited_holds_the_clear_off(client):
    with api._working_on("reading"):
        reply = client.post("/data/clear", json={"confirm": "clear everything"})
    assert reply.status_code == 409


def test_writes_are_refused_while_clearing(client):
    api._CLEARING.set()
    try:
        assert client.post("/horizon", json={"texts": ["too late"]}).status_code == 409
        assert client.get("/horizon").status_code == 200, "reads carry on"
    finally:
        api._CLEARING.clear()


def test_clearing_sweeps_the_lock_files_of_deleted_orbits(client):
    from penumbra.orbit import mutate_orbit, orbit_lock
    mutate_orbit("kept-lock", lambda orb: None, create=True)
    gone = Path("orbits/.gone.json.lock")
    gone.write_text("", encoding="utf-8")
    with orbit_lock("held"):  # held by someone: stays
        held = Path("orbits/.held.json.lock")
        assert client.post("/data/clear", json={"confirm": "clear everything"}).status_code == 200
        assert held.exists()
    assert not gone.exists() and not Path("orbits/.kept-lock.json.lock").exists()
