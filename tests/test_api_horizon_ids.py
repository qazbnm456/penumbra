"""The HTTP side of a capture's two ids: every route takes either, resolves it once, and hands the
current id on; the extension's card works with the id it was given; a stale epoch is refused.

Needs the `api` extra (`importorskip`), like the other API suites.
"""

from __future__ import annotations

import time

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, ingest, intake, memory_store, topics
from penumbra.orbit import mutate_orbit
from penumbra.schema import Source, SourceBlock


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def fake(url: str, source_id: str) -> Source:
        return Source(id=source_id, kind="web", origin=url,
                      blocks=[SourceBlock(locator="whole", text=f"body of {url}")])

    monkeypatch.setattr(ingest, "parse_web", fake)
    monkeypatch.setenv("PN_FILING_MODE", "manual")
    yield
    if intake._SHARED is not None:
        intake._SHARED.stop(timeout=5)
    intake._SHARED = None


@pytest.fixture
def client():
    with TestClient(api.app, base_url="http://127.0.0.1",
                    headers={"Authorization": f"Bearer {auth.api_token()}"}) as c:
        yield c


def _paste(client, text: str) -> dict:
    return client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]


def _ready(client, node_id: str) -> dict:
    for _ in range(200):
        node = client.get(f"/horizon/{node_id}").json()["node"]
        if node["state"] == "ready_undistilled":
            return node
        time.sleep(0.02)
    raise AssertionError("never became ready")


def test_every_node_route_answers_to_the_temporary_id(client):
    node = _paste(client, "a note with two ids")
    temp, now = node["former_id"], node["id"]
    assert temp.startswith("nd-") and now.startswith("m")
    assert client.get(f"/horizon/{temp}").json()["node"]["id"] == now
    assert client.put(f"/horizon/{temp}/title", json={"title": "Named"}).json()["node"]["id"] == now
    assert client.put(f"/horizon/{temp}/tags", json={"tags": ["x"]}).json()["node"]["id"] == now
    assert client.get(f"/horizon/{temp}/source").status_code == 200
    promoted = client.post(f"/horizon/{temp}/promote", json={"orbit_id": "one", "create": True})
    assert promoted.status_code == 200 and promoted.json()["membership"]["node_id"] == now
    client.post("/orbits/two/notes", json={"text": "an orbit to move into"})
    moved = client.post(f"/horizon/{temp}/move", json={"from_orbit": "one", "to_orbit": "two"})
    assert moved.status_code == 200, moved.text
    assert client.post(f"/horizon/{temp}/unfile", json={"orbit": "two"}).status_code == 200
    assert client.delete(f"/horizon/{temp}").json()["removed"] is True
    assert client.get(f"/horizon/{now}").status_code == 404


@pytest.mark.parametrize("route", ["/horizon/{}", "/horizon/{}/source"])
def test_a_malformed_id_is_400_and_a_missing_one_404_in_either_shape(client, route):
    assert client.get(route.format("m0")).status_code == 400
    assert client.get(route.format("nd-nothex")).status_code == 400
    assert client.get(route.format("m999")).status_code == 404
    assert client.get(route.format("nd-" + "0" * 16)).status_code == 404


def test_an_unreadable_row_is_removed_by_its_temporary_id(client):
    node = _paste(client, "a row that will not parse")
    with horizon._connect() as conn:
        # A JSON column still kept on the row (labels live in the kit's store now).
        conn.execute("UPDATE nodes SET flags = 'not json' WHERE id = ?", (node["id"],))
    assert client.get(f"/horizon/{node['former_id']}").status_code == 409
    assert client.delete(f"/horizon/{node['former_id']}").json()["removed"] is True


def test_a_capture_named_by_both_its_ids_is_named_twice(client, monkeypatch):
    monkeypatch.setenv("PN_MAIN_MODEL", "openai/gpt-4o-mini")   # read before the selection is checked
    monkeypatch.setenv("PN_API_KEY", "sk-test")
    node = _paste(client, "one capture, two names")
    both = [node["id"], node["former_id"]]
    reply = client.post("/horizon/ask", json={"question": "what", "node_ids": both})
    assert reply.status_code == 422 and "named twice" in reply.json()["detail"]


def test_a_suggestion_dismissed_by_the_temporary_id_is_recorded_under_the_item_id(client):
    node = _paste(client, "a capture to keep out of an orbit")
    mutate_orbit("o", lambda orb: None, create=True)
    assert client.post("/horizon/suggestions/dismiss",
                       json={"node_id": node["former_id"], "orbit": "o"}).status_code == 200
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    assert store.dismissed() == {(node["id"], topics.topic_of("o"))}


def _pair(client) -> dict:
    url = client.post("/extension/pairing").json()["pair_url"]
    return {"Authorization": f"Bearer {url.split('#code=', 1)[1]}"}


def test_the_extension_files_and_takes_back_a_link_by_the_id_it_was_given(client):
    """A link is captured queued, under its temporary id; once read it is an item. The card's file
    and undo still name the temporary id, and both work."""
    key = _pair(client)
    seed = _paste(client, "seed")
    client.post(f"/horizon/{seed['id']}/promote", json={"orbit_id": "reading", "create": True})
    got = client.post("/extension/capture", headers=key,
                      json={"kind": "link", "url": "https://example.com/l", "title": "L"}).json()
    temp = got["node"]["id"]
    assert temp.startswith("nd-")
    now = _ready(client, temp)["id"]
    assert now.startswith("m")
    filed = client.post("/extension/file", headers=key, json={"node_id": temp, "orbit": "reading"})
    assert filed.status_code == 200 and filed.json()["filed"] is True
    assert [m.orbit_id for m in horizon.memberships_for(now)] == ["reading"]
    assert client.post("/extension/undo", headers=key, json={"node_id": temp}).json()["removed"] is True
    assert horizon.get_node(now) is None
    # One removed elsewhere while the card still holds it: the card is told it was not removed.
    link = {"kind": "link", "url": "https://example.com/m", "title": "M"}
    other = client.post("/extension/capture", headers=key, json=link).json()["node"]["id"]
    assert client.delete(f"/horizon/{_ready(client, other)['id']}").status_code == 200
    assert client.post("/extension/undo", headers=key, json={"node_id": other}).json() == {"removed": False}


def test_a_link_captured_into_an_orbit_is_filed_there_once_read(client):
    key = _pair(client)
    seed = _paste(client, "seed two")
    client.post(f"/horizon/{seed['id']}/promote", json={"orbit_id": "target", "create": True})
    got = client.post("/extension/capture", headers=key,
                      json={"kind": "link", "url": "https://example.com/t", "title": "T", "orbit": "target"})
    temp = got.json()["node"]["id"]
    now = _ready(client, temp)["id"]
    for _ in range(100):
        if horizon.memberships_for(now):
            break
        time.sleep(0.02)
    assert [m.orbit_id for m in horizon.memberships_for(now)] == ["target"]


def test_a_request_with_a_stale_epoch_is_refused_before_it_runs(client):
    node = _paste(client, "named before the clear")
    epoch = client.get("/horizon/status").json()["epoch"]
    assert client.get("/horizon").json()["epoch"] == epoch
    assert client.get("/horizon/status", headers={"X-Horizon-Epoch": epoch}).status_code == 200
    assert client.post("/data/clear", json={"confirm": "clear everything"}).status_code == 200
    again = _paste(client, "named after the clear")
    assert again["id"] == node["id"], "the numbering restarts"
    refused = client.put(f"/horizon/{again['id']}/title", json={"title": "stale"},
                         headers={"X-Horizon-Epoch": epoch})
    assert refused.status_code == 412 and refused.json()["epoch"] != epoch
    assert client.get(f"/horizon/{again['id']}").json()["node"]["title"] != "stale"
    unauthenticated = TestClient(api.app, base_url="http://127.0.0.1")
    assert unauthenticated.get("/horizon/status", headers={"X-Horizon-Epoch": epoch}).status_code == 401, \
        "the token is checked first, so the epoch is never told to a stranger"


def test_the_extension_never_reaches_a_capture_made_after_a_clear(client):
    """The card keeps a capture's temporary id (a hash of what was captured); item ids start again
    from `m1` after a clear, so an item id kept from before would name a different capture."""
    key = _pair(client)
    page = {"kind": "selection", "url": "https://example.com/a", "title": "A", "text": "the first passage"}
    first = client.post("/extension/capture", headers=key, json=page).json()["node"]
    kept = first["former_id"] or first["id"]
    assert kept.startswith("nd-"), "the card is given the temporary id to keep"
    assert client.post("/data/clear", json={"confirm": "clear everything"}).status_code == 200
    other = {"kind": "selection", "url": "https://example.com/b", "title": "B", "text": "a different passage"}
    second = client.post("/extension/capture", headers=key, json=other).json()["node"]
    assert second["id"] == first["id"], "the item ids start again"
    assert client.post("/extension/undo", headers=key, json={"node_id": kept}).status_code == 404
    assert client.post("/extension/undo", headers=key, json={"node_id": first["id"]}).status_code == 200, \
        "the item id names the new capture, which this browser did make"


def test_a_stale_move_and_unfile_are_refused_like_any_write(client):
    node = _paste(client, "filed before the clear")
    client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "a", "create": True})
    epoch = client.get("/horizon/status").json()["epoch"]
    client.post("/data/clear", json={"confirm": "clear everything"})
    stale = {"X-Horizon-Epoch": epoch}
    move = {"from_orbit": "a", "to_orbit": "b"}
    moved = client.post(f"/horizon/{node['id']}/move", headers=stale, json=move)
    unfiled = client.post(f"/horizon/{node['id']}/unfile", headers=stale, json={"orbit": "a"})
    assert moved.status_code == unfiled.status_code == 412


def test_a_passage_that_waits_for_the_store_is_filed_to_its_orbit_and_undone_by_its_first_id(
    client, monkeypatch
):
    import sqlite3

    from penumbra import memory_store

    monkeypatch.setattr(intake, "_RETRY_FIRST_S", 0.05)
    store = memory_store.store(api._horizon_queue_base())
    real, calls = store.add, [0]

    def add(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 2:   # the passage's own add; the seed's was the first
            exc = sqlite3.OperationalError("database is locked")
            exc.sqlite_errorcode = 5
            raise exc
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "add", add)
    key = _pair(client)
    seed = _paste(client, "seed for dest")
    client.post(f"/horizon/{seed['id']}/promote", json={"orbit_id": "dest", "create": True})
    passage = {"kind": "selection", "url": "https://example.com/w", "title": "W", "text": "a waiting passage",
               "orbit": "dest"}
    got = client.post("/extension/capture", headers=key, json=passage).json()
    temp = got["node"]["id"]
    assert temp.startswith("nd-") and got["node"]["state"] == "stored_unindexed" and got["filed"] is None
    now = _ready(client, temp)["id"]
    for _ in range(100):
        if horizon.memberships_for(now):
            break
        time.sleep(0.02)
    assert [m.orbit_id for m in horizon.memberships_for(now)] == ["dest"]
    assert client.post("/extension/undo", headers=key, json={"node_id": temp}).json()["removed"] is True
