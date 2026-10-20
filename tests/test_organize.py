"""Organising captures into orbits with a model in the automatic filing mode: the kit's
`organize_pending` with Penumbra's say in every placement (`api._organize_after_pass`,
`api._OrganizeHost`). The plan's own rules are the kit's, tested there.
"""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("fastapi")  # the `api` extra, which CI installs
from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, intake, memory_store, topics
from penumbra.orbit import list_orbit_summaries, load_orbit
from tests._labels import label


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("PN_LANDING_ORBIT", raising=False)
    monkeypatch.setenv("PN_FILING_MODE", "auto")
    with api._DISTIL_GUARD:
        api._DISTIL.update({"running": False, "cancel": False, "unreachable": 0})
        api._ORGANIZE.update({"running": False, "error": ""})
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


def _summarised(client, text: str, entities: list[str]) -> str:
    node_id = client.post("/horizon", json={"texts": [text]}).json()["nodes"][0]["id"]
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            break
        time.sleep(0.02)
    node_id = horizon.resolve_id(node_id)   # stored: it carries its kit item id now
    label(node_id, title=text, summary=f"about {text}", entities=entities)
    return node_id


def _kit_plan(plan: dict) -> dict:
    """A plan written with orbits, as the kit's step answers it: an orbit slug becomes its topic."""
    placements = []
    for p in plan["placements"]:
        entry = {"item": p["capture"], "fit": p.get("fit", "")}
        if p.get("orbit"):
            entry["topic"] = topics.topic_of(p["orbit"]) or p["orbit"]
        if p.get("new_orbit"):
            entry["new_topic"] = p["new_orbit"]
        placements.append(entry)
    return {"plan_json": json.dumps({"placements": placements})}


def _fake_model(monkeypatch, reply) -> list[dict]:
    """`seen` holds each call's fields, with `captures` and `orbits` as the old step named them."""
    seen: list[dict] = []

    def fake(dotted, kwargs, prefix, **kw):
        assert dotted == "rlm_harness.memory_tasks:OrganiseBatch"
        seen.append({**kwargs, "captures": kwargs["items"], "orbits": kwargs["topics"]})
        return _kit_plan(reply(kwargs) if callable(reply) else reply)

    monkeypatch.setattr(api, "_run_pass_task", fake)
    return seen


def test_captures_go_into_an_orbit_that_fits_or_a_new_one_it_names(client, monkeypatch):
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "space", "create": True})
    a = _summarised(client, "rockets", ["Rocket"])
    b = _summarised(client, "sourdough", ["Bread"])
    c = _summarised(client, "rye", ["Bread"])
    seen = _fake_model(monkeypatch, {"placements": [
        {"capture": a, "orbit": "space", "fit": "subject"},
        {"capture": b, "new_orbit": "Baking"},
        {"capture": c, "new_orbit": "baking"},
    ]})

    since = client.get("/horizon/suggestions").json()["auto_seq"]
    api._organize_after_pass()

    assert {x["id"] for x in json.loads(seen[0]["captures"])} == {a, b, c}, "the filed seed is not sent"
    assert [m.orbit_id for m in horizon.memberships_for(a)] == ["space"]
    baking = horizon.memberships_for(b)[0].orbit_id
    assert baking.startswith("orbit-") and [m.orbit_id for m in horizon.memberships_for(c)] == [baking]
    assert load_orbit(baking).title == "Baking"
    got = client.get("/horizon/suggestions", params={"since": since}).json()["auto_filed"]
    assert {e["node_id"]: e["new_orbit"] for e in got} == {a: False, b: True, c: True}


def test_manual_and_assigned_filing_never_call_the_model(client, monkeypatch):
    _summarised(client, "loose", ["X"])
    seen = _fake_model(monkeypatch, {"placements": []})
    for mode in ("manual", "assign"):
        monkeypatch.setenv("PN_FILING_MODE", mode)
        api._organize_after_pass()
    assert seen == []


def test_a_capture_left_alone_is_not_sent_again_until_the_orbits_change(client, monkeypatch):
    a = _summarised(client, "thin", [])
    seen = _fake_model(monkeypatch, {"placements": []})
    api._organize_after_pass()
    api._organize_after_pass()
    assert len(seen) == 1
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "new-one", "create": True})
    api._organize_after_pass()
    assert len(seen) == 2 and a in seen[1]["captures"]


def test_a_declined_orbit_is_never_the_answer(client, monkeypatch):
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "space", "create": True})
    a = _summarised(client, "rockets", ["Rocket"])
    assert client.post(f"/horizon/{a}/promote", json={"orbit_id": "space"}).status_code == 200
    source_id = horizon.memberships_for(a)[0].source_id
    assert client.delete(f"/orbits/space/sources/{source_id}").status_code == 200
    _fake_model(monkeypatch, {"placements": [{"capture": a, "orbit": "space", "fit": "subject"}]})
    api._organize_after_pass()
    assert horizon.memberships_for(a) == []


def test_a_new_orbit_nothing_could_go_into_is_not_left_behind(client, monkeypatch):
    a = _summarised(client, "big", ["X"])
    b = _summarised(client, "bigger", ["X"])
    monkeypatch.setattr(api, "max_corpus_chars", lambda: 5)
    _fake_model(monkeypatch, {"placements": [{"capture": a, "new_orbit": "Too big"},
                                             {"capture": b, "new_orbit": "Too big"}]})
    api._organize_after_pass()
    assert horizon.memberships_for(a) == [] and horizon.memberships_for(b) == []
    assert list_orbit_summaries()[0] == []


def test_a_failed_run_is_reported_and_files_nothing(client, monkeypatch):
    a = _summarised(client, "loose", ["X"])

    def boom(kwargs):
        raise RuntimeError("model down")

    _fake_model(monkeypatch, boom)
    api._organize_after_pass()
    assert horizon.memberships_for(a) == []
    status = client.get("/horizon/status").json()["organize"]
    assert status == {"running": False, "error": "RuntimeError: model down"}


def test_a_stopped_pass_does_not_organise(client, monkeypatch):
    _summarised(client, "loose", ["X"])
    seen = _fake_model(monkeypatch, {"placements": []})
    with api._DISTIL_GUARD:
        api._DISTIL["cancel"] = True
    api._organize_after_pass()
    assert seen == []


def test_a_round_that_opened_orbits_is_followed_by_one_over_what_it_left(client, monkeypatch):
    a = _summarised(client, "rockets", ["Rocket"])
    c = _summarised(client, "probes", ["Probe"])
    b = _summarised(client, "moons", ["Moon"])
    replies = iter([
        {"placements": [{"capture": a, "new_orbit": "Space"}, {"capture": c, "new_orbit": "Space"}]},
        {"placements": [{"capture": b, "orbit": "PLACEHOLDER", "fit": "subject"}]},
    ])

    def reply(kwargs):
        plan = next(replies)
        offered = json.loads(kwargs["topics"])
        for item in plan["placements"]:
            if item.get("orbit") == "PLACEHOLDER":
                item["orbit"] = topics.orbits_by_topic()[offered[0]["id"]]
        return plan

    seen = _fake_model(monkeypatch, reply)
    api._organize_after_pass()
    assert len(seen) == 2, "the second round sees the capture the first one left"
    assert b in seen[1]["captures"] and a not in seen[1]["captures"]
    space = horizon.memberships_for(a)[0].orbit_id
    assert [m.orbit_id for m in horizon.memberships_for(b)] == [space]


def test_what_was_left_goes_again_when_something_new_arrives(client, monkeypatch):
    a = _summarised(client, "spaced repetition", ["Memory"])
    seen = _fake_model(monkeypatch, {"placements": [{"capture": a, "new_orbit": "Learning"}]})
    api._organize_after_pass()
    assert horizon.memberships_for(a) == [], "a subject of one is left"
    api._organize_after_pass()
    assert len(seen) == 1, "nothing new: the left capture is not sent again"
    b = _summarised(client, "zettelkasten", ["Notes"])
    api._organize_after_pass()
    assert len(seen) == 2 and a in seen[1]["captures"] and b in seen[1]["captures"]


def test_what_was_left_is_remembered_across_a_restart(client, monkeypatch):
    """The left set lives in the kit's memory store, so the waiting card can still say why a
    capture waits after the server restarts (it was process state, and a restart erased it)."""
    a = _summarised(client, "origami", ["Paper"])
    _fake_model(monkeypatch, {"placements": [{"capture": a, "new_orbit": "Paper folding"}]})
    api._organize_after_pass()
    got = client.get("/horizon/suggestions").json()
    assert got["organize_left"] == [a]
    monkeypatch.setenv("PN_FILING_MODE", "manual")
    assert client.get("/horizon/suggestions").json()["organize_left"] == [], "only automatic filing says so"


def test_a_failed_summary_is_reported_after_a_restart_and_cleared_by_dismiss(client, monkeypatch):
    node_id = client.post("/horizon", json={"texts": ["lighthouse"]}).json()["nodes"][0]["id"]
    for _ in range(150):
        if horizon.get_node(node_id).state == "ready_undistilled":
            break
        time.sleep(0.02)
    with api._DISTIL_GUARD:
        api._record_failure(node_id, "RuntimeError: run timed out after 300s")
        # A restart: the process forgets everything it held.
        api._DISTIL.update({"failed": 0, "error": "", "failures": [], "running": False})
    distil = client.get("/horizon/status").json()["distil"]
    assert distil["failed"] == 1 and distil["failures"][0]["id"] == node_id
    assert "timed out" in distil["failures"][0]["error"]
    assert client.post("/horizon/distil/dismiss").status_code == 200
    assert client.get("/horizon/status").json()["distil"]["failures"] == []
    assert horizon.get_node(node_id).state == "ready_undistilled", "dismissing forgets only the reason"


def test_a_capture_the_plan_named_but_filing_refused_is_not_sent_again(client, monkeypatch):
    """Left means not filed, not merely not named: a capture sent to an orbit the reader declined
    would otherwise cost a model call at the end of every later pass."""
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "space", "create": True})
    a = _summarised(client, "rockets", ["Rocket"])
    assert client.post(f"/horizon/{a}/promote", json={"orbit_id": "space"}).status_code == 200
    source_id = horizon.memberships_for(a)[0].source_id
    assert client.delete(f"/orbits/space/sources/{source_id}").status_code == 200
    seen = _fake_model(monkeypatch, {"placements": [{"capture": a, "orbit": "space", "fit": "subject"}]})
    api._organize_after_pass()
    api._organize_after_pass()
    assert len(seen) == 1, "the second pass sent the refused capture to the model again"


def test_organising_yields_to_a_waiting_capture(client, monkeypatch):
    """On the automatic pass it runs on the intake worker's thread, so it stops when told to."""
    _summarised(client, "loose", ["X"])
    seen = _fake_model(monkeypatch, {"placements": []})
    api._organize_after_pass(should_stop=lambda: True)
    assert seen == []


def test_a_new_orbit_keeps_only_when_two_captures_went_in(client, monkeypatch):
    """The kit opens a topic for two or more captures; when filing refuses one of two (the corpus
    cap), the other is taken back and the orbit made for them goes."""
    a = _summarised(client, "short", ["X"])
    b = _summarised(client, "a much longer capture " * 40, ["X"])
    monkeypatch.setattr(api, "max_corpus_chars", lambda: 200)
    since = client.get("/horizon/suggestions").json()["auto_seq"]
    _fake_model(monkeypatch, {"placements": [{"capture": a, "new_orbit": "Pair"},
                                             {"capture": b, "new_orbit": "Pair"}]})
    undone = []
    real = api._OrganizeHost.unplace
    def unplace(self, item_id, topic_id):
        undone.append(item_id)
        real(self, item_id, topic_id)

    monkeypatch.setattr(api._OrganizeHost, "unplace", unplace)
    api._organize_after_pass()
    assert undone == [a], "a was filed, then taken back when b could not join it"
    assert horizon.memberships_for(a) == [] and horizon.memberships_for(b) == []
    assert list_orbit_summaries()[0] == []
    assert client.get("/horizon/suggestions", params={"since": since}).json()["auto_filed"] == [], \
        "a filing the pass took back is never announced"


def test_the_kit_mirror_follows_a_filing(client, monkeypatch):
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "space", "create": True})
    a = _summarised(client, "rockets", ["Rocket"])
    _fake_model(monkeypatch, {"placements": [{"capture": a, "orbit": "space", "fit": "subject"}]})
    api._organize_after_pass()
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    assert [t.id for t in store.item_topics(a)] == [topics.topic_of("space")]
