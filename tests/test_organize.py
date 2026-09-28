"""Putting captures into orbits with a model when filing is automatic (`organize.py`,
`api._organize_after_pass`).

The model's reply is only a proposal: `plan_from` keeps what it may do (captures it was shown, orbits
that exist, a bounded number of new ones), and every filing goes through the same checks as any
automatic filing. The model run itself is faked here; nothing below costs a call.
"""

from __future__ import annotations

import json
import time

import pytest

from penumbra import organize


def test_the_plan_keeps_only_what_it_was_shown():
    raw = {"placements": [
        {"capture": "a", "orbit": "o1"},
        {"capture": "a", "orbit": "o2"},  # a second place for the same capture
        {"capture": "ghost", "orbit": "o1"},  # never shown
        {"capture": "b", "orbit": "invented"},  # an orbit that does not exist, and no name
        {"capture": "c", "new_orbit": "  Solar   sails "},
        {"capture": "d", "new_orbit": "solar sails"},
        {"capture": "e", "new_orbit": "Reading"},  # the title of an orbit that exists
        "not a placement",
    ]}
    plan = organize.plan_from(raw, captures={"a", "b", "c", "d", "e"}, orbits={"o1": "Reading", "o2": ""})
    assert plan == [
        ("a", "orbit", "o1"),
        ("c", "new", "Solar sails"),
        ("d", "new", "Solar sails"),
        ("e", "orbit", "o1"),
    ]


def test_the_plan_opens_a_bounded_number_of_new_orbits():
    raw = {"placements": [{"capture": str(n), "new_orbit": f"subject {n // 2}"} for n in range(16)]}
    plan = organize.plan_from(raw, captures={str(n) for n in range(16)}, orbits={}, max_new=3)
    assert [name for _c, _k, name in plan] == ["subject 0"] * 2 + ["subject 1"] * 2 + ["subject 2"] * 2


def test_a_new_orbit_needs_two_captures():
    raw = {"placements": [
        {"capture": "a", "new_orbit": "Spaced repetition"},
        {"capture": "b", "new_orbit": "Baking"},
        {"capture": "c", "new_orbit": "baking"},
    ]}
    plan = organize.plan_from(raw, captures={"a", "b", "c"}, orbits={})
    assert plan == [("b", "new", "Baking"), ("c", "new", "Baking")], "a subject of one waits for a second"


def test_a_reply_that_does_not_parse_places_nothing():
    assert organize.parse_plan("```json\n{\"placements\": []}\n```") == {"placements": []}
    assert organize.parse_plan("sorry, I cannot") == {"placements": []}
    assert organize.plan_from(organize.parse_plan("[1, 2]"), captures={"a"}, orbits={}) == []


fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, intake
from penumbra.orbit import list_orbit_summaries, load_orbit


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("PN_LANDING_ORBIT", raising=False)
    monkeypatch.setenv("PN_FILING_MODE", "auto")
    with api._DISTIL_GUARD:
        api._DISTIL.update({"running": False, "cancel": False, "unreachable": 0})
        api._ORGANIZE.update({"running": False, "error": "", "left": set(), "orbits": frozenset()})
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
    horizon.update_node(node_id, state="ready", title=text, summary=f"about {text}", entities=entities)
    return node_id


def _fake_model(monkeypatch, reply) -> list[dict]:
    seen: list[dict] = []

    def fake(dotted, kwargs, prefix, **kw):
        assert dotted == "penumbra.organize:OrganizeCaptures"
        seen.append(kwargs)
        return reply(kwargs) if callable(reply) else reply

    monkeypatch.setattr(api, "_run_pass_task", fake)
    return seen


def test_captures_go_into_an_orbit_that_fits_or_a_new_one_it_names(client, monkeypatch):
    seed = _summarised(client, "seed", [])
    client.post(f"/horizon/{seed}/promote", json={"orbit_id": "space", "create": True})
    a = _summarised(client, "rockets", ["Rocket"])
    b = _summarised(client, "sourdough", ["Bread"])
    c = _summarised(client, "rye", ["Bread"])
    seen = _fake_model(monkeypatch, {"placements": [
        {"capture": a, "orbit": "space"},
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
    _fake_model(monkeypatch, {"placements": [{"capture": a, "orbit": "space"}]})
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
        {"placements": [{"capture": b, "orbit": "PLACEHOLDER"}]},
    ])

    def reply(kwargs):
        plan = next(replies)
        orbits = json.loads(kwargs["orbits"])
        for item in plan["placements"]:
            if item.get("orbit") == "PLACEHOLDER":
                item["orbit"] = orbits[0]["id"]
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
