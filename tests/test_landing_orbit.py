"""Where an uncategorised capture lands (`api._file_into_landing_orbit`, `config.landing_orbit`).

By default everything captured is also filed into an automatically created first orbit, so it can
be asked about at once, and it stays in the Horizon either way (invariant 78: filing copies, it
never moves). The rules that make that safe are the tests below.
"""

from __future__ import annotations

import time

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, config, horizon, ingest, intake
from penumbra.orbit import load_orbit
from penumbra.schema import Source, SourceBlock


@pytest.fixture(autouse=True)
def _fake_web(monkeypatch):
    def fake(url: str, source_id: str) -> Source:
        return Source(
            id=source_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=f"body of {url}")]
        )

    monkeypatch.setattr(ingest, "parse_web", fake)
    monkeypatch.delenv("PN_LANDING_ORBIT", raising=False)


@pytest.fixture(autouse=True)
def _fresh_queue():
    yield
    if intake._SHARED is not None:
        intake._SHARED.stop(timeout=5)
    intake._SHARED = None


@pytest.fixture
def client():
    with TestClient(
        api.app,
        base_url="http://127.0.0.1",
        headers={"Authorization": f"Bearer {auth.api_token()}"},
    ) as c:
        yield c


def _filed(node_id: str, tries: int = 150) -> list[str]:
    for _ in range(tries):
        orbits = [m.orbit_id for m in horizon.memberships_for(node_id)]
        if orbits:
            return orbits
        time.sleep(0.02)
    return []


def test_a_capture_lands_in_the_first_orbit_titled_in_the_readers_language(client):
    resp = client.post(
        "/horizon",
        json={"urls": ["https://example.com/a"]},
        headers={"X-Penumbra-Interface-Language": "Traditional Chinese"},
    )
    node_id = resp.json()["nodes"][0]["id"]

    assert _filed(node_id) == [api.FIRST_ORBIT_ID]
    orbit = load_orbit(api.FIRST_ORBIT_ID)
    assert orbit is not None and orbit.title == "第一個軌道"
    assert [s.origin for s in orbit.sources] == ["https://example.com/a"]
    assert horizon.get_node(node_id) is not None, "filing copies; the node stays in the Horizon"


def test_pasted_text_skips_the_queue_and_still_lands(client):
    node_id = client.post("/horizon", json={"texts": ["a thought worth keeping"]}).json()["nodes"][0]["id"]
    assert _filed(node_id) == [api.FIRST_ORBIT_ID]
    assert load_orbit(api.FIRST_ORBIT_ID).title == "First orbit"


def test_off_keeps_captures_in_the_horizon_only(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    node_id = client.post("/horizon", json={"texts": ["stay here"]}).json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == []
    assert load_orbit(api.FIRST_ORBIT_ID) is None


def test_a_chosen_orbit_that_was_deleted_is_not_recreated(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "gone")
    node_id = client.post("/horizon", json={"texts": ["where does this go"]}).json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == []
    assert load_orbit("gone") is None


def test_a_capture_already_filed_by_hand_is_not_filed_again(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    node_id = client.post("/horizon", json={"texts": ["filed by hand"]}).json()["nodes"][0]["id"]
    promoted = client.post(f"/horizon/{node_id}/promote", json={"orbit_id": "reading", "create": True})
    assert promoted.status_code == 200, promoted.text
    monkeypatch.delenv("PN_LANDING_ORBIT")

    api._file_into_landing_orbit(node_id)

    assert [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]


def test_filing_stops_at_the_corpus_cap(client, monkeypatch):
    """Invariant 8 fails a whole question past the cap; quietly growing the landing orbit toward it
    with every capture would make it an orbit nobody can ask."""
    monkeypatch.setattr(api, "max_corpus_chars", lambda: 10)
    resp = client.post("/horizon", json={"texts": ["far more than ten characters"]})
    node_id = resp.json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == []


def test_the_setting_accepts_default_off_or_an_orbit_id_and_nothing_else(tmp_path):
    config.write_settings({"landing_orbit": "off"}, base_dir=tmp_path)
    assert config.landing_orbit(base_dir=tmp_path) == "off"
    config.write_settings({"landing_orbit": "reading-list"}, base_dir=tmp_path)
    assert config.landing_orbit(base_dir=tmp_path) == "reading-list"
    with pytest.raises(ValueError):
        config.write_settings({"landing_orbit": "../escape"}, base_dir=tmp_path)


def test_an_upload_that_creates_the_first_orbit_titles_it_in_the_readers_language(client):
    """The first orbit is often created by a dropped file. The upload path did not pass the
    interface language along, so a reader with a Chinese interface got an orbit named "First orbit"."""
    resp = client.post(
        "/horizon/upload",
        files=[("file", ("notes.md", b"# notes\n\nsomething worth keeping", "text/markdown"))],
        headers={"X-Penumbra-Interface-Language": "Traditional Chinese"},
    )
    assert resp.status_code == 200, resp.text
    node_id = resp.json()["nodes"][0]["id"]
    assert _filed(node_id) == [api.FIRST_ORBIT_ID]
    assert load_orbit(api.FIRST_ORBIT_ID).title == "第一個軌道"
