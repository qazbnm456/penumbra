"""Removing a capture from the map: from the Horizon only, or from every orbit it was filed into
as well (`DELETE /horizon/{id}?everywhere=true`)."""

from __future__ import annotations

import time

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, intake
from penumbra.orbit import load_orbit


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


def _filed(client, text: str, orbit: str) -> str:
    node_id = client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]["id"]
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            break
        time.sleep(0.02)
    reply = client.post(f"/horizon/{node_id}/promote", json={"orbit_id": orbit, "create": True})
    assert reply.status_code == 200
    return node_id


def test_removing_from_the_horizon_only_keeps_the_orbits_copy(client):
    node_id = _filed(client, "circle of fifths", "music")
    reply = client.delete(f"/horizon/{node_id}")
    assert reply.status_code == 200 and reply.json()["orbits"] == []
    assert horizon.get_node(node_id) is None
    assert len(load_orbit("music").sources) == 1, "the orbit keeps the copy it was given"


def test_removing_everywhere_takes_it_out_of_every_orbit_too(client):
    node_id = _filed(client, "chords", "music")
    again = client.post(f"/horizon/{node_id}/promote", json={"orbit_id": "theory", "create": True})
    assert again.status_code == 200
    reply = client.delete(f"/horizon/{node_id}", params={"everywhere": "true"})
    assert reply.status_code == 200
    assert sorted(reply.json()["orbits"]) == ["music", "theory"]
    assert horizon.get_node(node_id) is None
    assert load_orbit("music").sources == [] and load_orbit("theory").sources == []


def test_removing_everywhere_reaches_an_orbit_named_in_chinese(client):
    """An orbit named in Chinese has a hashed id (invariant 10); its memberships hold that slug, and
    the everywhere delete must open the same file."""
    from penumbra.orbit import slug

    node_id = _filed(client, "tea ceremony", "茶道")
    reply = client.delete(f"/horizon/{node_id}", params={"everywhere": "true"})
    assert reply.status_code == 200 and reply.json()["orbits"] == [slug("茶道")]
    assert load_orbit("茶道").sources == []
