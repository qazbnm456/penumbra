"""How a capture in no orbit is filed (`config.filing_mode`, `api._file_into_landing_orbit`).

`manual`, the default, leaves it in the Horizon for the reader; `assign` files everything into one
chosen orbit; `auto` accepts the filing suggestion once there is one. It stays in the Horizon
either way (invariant 78: filing copies, it never moves). The rules that make that safe are the
tests below.
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
    monkeypatch.delenv("PN_FILING_MODE", raising=False)


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


def _ready(node_id: str) -> None:
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            return
        time.sleep(0.02)


def _assign(client, monkeypatch, orbit_id: str = "reading") -> None:
    """`assign` into an orbit that exists, made the way a reader makes one: by filing into it."""
    seed = client.post("/horizon", json={"texts": [f"seed for {orbit_id}"]}).json()["nodes"][0]["id"]
    _ready(seed)
    resp = client.post(f"/horizon/{seed}/promote", json={"orbit_id": orbit_id, "create": True})
    assert resp.status_code == 200, resp.text
    monkeypatch.setenv("PN_FILING_MODE", "assign")
    monkeypatch.setenv("PN_LANDING_ORBIT", orbit_id)


def test_by_default_a_capture_stays_in_the_horizon_and_no_orbit_is_made(client):
    node_id = client.post("/horizon", json={"urls": ["https://example.com/a"]}).json()["nodes"][0]["id"]
    _ready(node_id)
    time.sleep(0.1)
    assert horizon.memberships_for(node_id) == []
    assert load_orbit("first-orbit") is None
    assert config.filing_mode() == ("manual", None)


def test_assign_files_every_capture_into_the_chosen_orbit(client, monkeypatch):
    _assign(client, monkeypatch)
    node_id = client.post("/horizon", json={"urls": ["https://example.com/a"]}).json()["nodes"][0]["id"]
    assert _filed(node_id) == ["reading"]
    assert horizon.get_node(node_id) is not None, "filing copies; the node stays in the Horizon"


def test_pasted_text_skips_the_queue_and_still_lands(client, monkeypatch):
    _assign(client, monkeypatch)
    node_id = client.post("/horizon", json={"texts": ["a thought worth keeping"]}).json()["nodes"][0]["id"]
    assert _filed(node_id) == ["reading"]


def test_a_chosen_orbit_that_was_deleted_is_not_recreated(client, monkeypatch):
    monkeypatch.setenv("PN_FILING_MODE", "assign")
    monkeypatch.setenv("PN_LANDING_ORBIT", "gone")
    node_id = client.post("/horizon", json={"texts": ["where does this go"]}).json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == []
    assert load_orbit("gone") is None


def test_a_capture_already_filed_by_hand_is_not_filed_again(client, monkeypatch):
    _assign(client, monkeypatch, "landing")
    monkeypatch.setenv("PN_FILING_MODE", "manual")
    node_id = client.post("/horizon", json={"texts": ["filed by hand"]}).json()["nodes"][0]["id"]
    _ready(node_id)
    promoted = client.post(f"/horizon/{node_id}/promote", json={"orbit_id": "reading", "create": True})
    assert promoted.status_code == 200, promoted.text
    monkeypatch.setenv("PN_FILING_MODE", "assign")

    api._file_into_landing_orbit(node_id)

    assert [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]


def test_filing_stops_at_the_corpus_cap(client, monkeypatch):
    """Invariant 8 fails a whole question past the cap; quietly growing the chosen orbit toward it
    with every capture would make it an orbit nobody can ask."""
    _assign(client, monkeypatch)
    monkeypatch.setattr(api, "max_corpus_chars", lambda: 10)
    resp = client.post("/horizon", json={"texts": ["far more than ten characters"]})
    node_id = resp.json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == []


def test_a_landing_orbit_chosen_before_the_mode_existed_still_receives_captures(tmp_path):
    config.write_settings({"landing_orbit": "reading"}, base_dir=tmp_path)
    assert config.filing_mode(base_dir=tmp_path) == ("assign", "reading")
    config.write_settings({"landing_orbit": "off"}, base_dir=tmp_path)
    assert config.filing_mode(base_dir=tmp_path) == ("manual", None)


def test_the_mode_accepts_three_values_and_assign_needs_an_orbit(tmp_path):
    config.write_settings({"filing_mode": "assign"}, base_dir=tmp_path)
    assert config.filing_mode(base_dir=tmp_path) == ("manual", None)
    config.write_settings({"filing_mode": "auto", "landing_orbit": "reading"}, base_dir=tmp_path)
    assert config.filing_mode(base_dir=tmp_path) == ("auto", None)
    with pytest.raises(ValueError):
        config.write_settings({"filing_mode": "sometimes"}, base_dir=tmp_path)
    with pytest.raises(ValueError):
        config.write_settings({"landing_orbit": "../escape"}, base_dir=tmp_path)


def test_auto_files_a_capture_into_its_suggested_orbit(client, monkeypatch):
    _assign(client, monkeypatch)
    monkeypatch.setenv("PN_FILING_MODE", "manual")
    node_id = client.post("/horizon", json={"texts": ["waiting"]}).json()["nodes"][0]["id"]
    _ready(node_id)
    monkeypatch.setattr(api.filing, "suggestions", lambda landing, **kw: [
        {"node_id": node_id, "orbit": "reading", "title": "waiting", "shared": [], "tags": [], "score": 3},
    ])
    assert api._auto_file_suggested() == 0, "manual files nothing"
    monkeypatch.setenv("PN_FILING_MODE", "auto")
    assert api._auto_file_suggested() == 1
    assert [m.orbit_id for m in horizon.memberships_for(node_id)] == ["reading"]


def test_a_filing_failure_never_fails_the_capture(client, monkeypatch):
    """Invariant 79: a capture always lands. Filing is a convenience on top of it."""
    _assign(client, monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("filing broke")

    monkeypatch.setattr(horizon, "promote_node", boom)
    resp = client.post("/horizon", json={"texts": ["kept even though filing failed"]})
    assert resp.status_code == 200
    node_id = resp.json()["nodes"][0]["id"]
    assert horizon.get_node(node_id) is not None


def test_a_crashing_after_parse_hook_does_not_stall_intake(client, monkeypatch):
    """The hook runs on the intake worker; if it raised out, every later capture would sit at
    `queued`, which looks exactly like still working (invariant 79)."""
    def boom(node_id):
        raise RuntimeError("the hook broke")

    monkeypatch.setattr(api, "_file_into_landing_orbit", boom)
    ids = [
        client.post("/horizon", json={"urls": [f"https://example.com/{n}"]}).json()["nodes"][0]["id"]
        for n in ("one", "two")
    ]
    for _ in range(150):
        if all(horizon.get_node(i).state == "ready_undistilled" for i in ids):
            break
        time.sleep(0.02)
    assert [horizon.get_node(i).state for i in ids] == ["ready_undistilled"] * 2


def test_the_cap_is_measured_on_the_real_blob_not_the_text(client, monkeypatch):
    """Markers and separators are part of what invariant 8 caps: a 50-character paste becomes 68
    characters of blob (`[[SRC:s10|whole]]` and a newline). A cap between the two must refuse it."""
    text = "x" * 50
    _assign(client, monkeypatch, "r")
    monkeypatch.setattr(api, "max_corpus_chars", lambda: 60)
    node_id = client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]["id"]
    time.sleep(0.2)
    assert horizon.memberships_for(node_id) == [], "text alone (50) fits; the real blob does not"


def test_captures_the_old_first_orbit_holds_still_count_as_unfiled(client, monkeypatch):
    """Before the mode existed every capture was filed into `first-orbit` by the app, not the
    reader, so those captures keep their suggestions and `auto` can still file them."""
    _assign(client, monkeypatch, "first-orbit")
    node_id = client.post("/horizon", json={"texts": ["filed by the app"]}).json()["nodes"][0]["id"]
    assert _filed(node_id) == ["first-orbit"]
    _assign(client, monkeypatch, "reading")
    monkeypatch.setenv("PN_FILING_MODE", "auto")
    monkeypatch.setattr(api.filing, "suggestions", lambda landing, **kw: [
        {"node_id": node_id, "orbit": "reading", "title": "t", "shared": [], "tags": [], "score": 3},
    ] if landing == "first-orbit" else [])
    assert api._auto_file_suggested() == 1
    assert sorted(m.orbit_id for m in horizon.memberships_for(node_id)) == ["first-orbit", "reading"]
