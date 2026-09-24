"""Asking the Horizon (`/horizon/ask*`, `/horizon/asks*`, `/horizon/concepts`).

Needs the `api` extra (it `importorskip`s `fastapi`). No model and no subprocess: nodes are written
straight into the Horizon and the runner is replaced, so what runs is the handlers, the selection
and the ask history.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, asks, auth, horizon
from penumbra.schema import Source, SourceBlock


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("PN_MAIN_MODEL", "test/model")
    monkeypatch.setenv("PN_OUTPUT_LANGUAGE", "English")
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    monkeypatch.delenv("PN_INTERPRETER", raising=False)


@pytest.fixture
def client():
    with TestClient(
        api.app, base_url="http://127.0.0.1", headers={"Authorization": f"Bearer {auth.api_token()}"}
    ) as c:
        yield c


def _capture(url: str, text: str, **fields) -> str:
    node_id = horizon.node_id_for(url)
    horizon.add_pending_node(url, "web")
    horizon.store_blocks(
        node_id, Source(id=node_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=text)])
    )
    if fields:
        horizon.update_node(node_id, **fields)
    return node_id


class _Process:
    pid = 0
    returncode = None


class _Run:
    def __init__(self, run_id):
        self.run_id = run_id
        self.process = _Process()

    def cancel(self):
        pass


def _mock_runner(monkeypatch, result: dict, seen: list | None = None):
    async def start_run(run_id, trace_dir, dotted_task, kwargs, *, fresh=False):
        if seen is not None:
            seen.append({"run_id": run_id, "task": dotted_task, "kwargs": kwargs})
        return _Run(run_id)

    async def wait_result(run, *, timeout=None):
        return result

    monkeypatch.setattr(api.runner, "start_run", start_run)
    monkeypatch.setattr(api.runner, "wait_result", wait_result)


def _answer(text="Sleep consolidates memory.", source_id="s1"):
    return {
        "text": text,
        "citations": [{"source_id": source_id, "locator": "whole", "quote": "memory",
                       "answer_span": "consolidates memory"}],
        "follow_ups": ["What about REM?"],
    }


def test_preview_says_what_would_be_read_and_costs_nothing(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    a = _capture("https://x.example/a", "sleep and memory", tags=["sleep"])
    _capture("https://x.example/b", "coffee", tags=["coffee"])
    scope = {"kind": "tag", "value": "sleep"}
    resp = client.post("/horizon/ask/preview", json={"question": "memory?", "scope": scope})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1 and body["in_scope"] == 1
    assert body["items"][0]["node_id"] == a
    assert body["strategy"] == "all"
    assert seen == []


def test_ask_reads_the_selection_runs_one_answer_and_keeps_it(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    a = _capture("https://x.example/a", "sleep consolidates memory", title="Sleep review")
    resp = client.post("/horizon/ask", json={"question": "What does sleep do?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(seen) == 1
    assert seen[0]["task"].endswith(":AnswerQuestion")
    assert seen[0]["run_id"].startswith(f"{api.HORIZON_ASK_KEY}-")
    # The corpus is the selection, renumbered: the model sees s1, never a node id.
    assert "[[SRC:s1|whole]]" in seen[0]["kwargs"]["sources"]
    assert a not in seen[0]["kwargs"]["sources"]
    citation = body["citations"][0]
    assert citation["verified"] is True
    assert citation["node_id"] == a and citation["title"] == "Sleep review"
    assert body["sources"] == [{"source_id": "s1", "node_id": a, "title": "Sleep review",
                                "origin": "https://x.example/a"}]
    listed = client.get("/horizon/asks").json()["asks"]
    assert [x["id"] for x in listed] == [body["id"]]


def test_ask_reads_exactly_the_captures_the_preview_showed(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    a = _capture("https://x.example/a", "one")
    b = _capture("https://x.example/b", "two")
    resp = client.post("/horizon/ask", json={"question": "q", "node_ids": [b]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["sources"][0]["node_id"] == b
    assert "one" not in seen[0]["kwargs"]["sources"]
    assert resp.json()["strategy"] == "chosen"
    assert a  # captured but not chosen


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"question": "   "}, 422),
        ({"question": "q", "scope": {"kind": "orbit", "value": "x"}}, 422),
        ({"question": "q", "scope": {"kind": "tag"}}, 422),
        ({"question": "q", "node_ids": []}, 422),
        ({"question": "q", "node_ids": ["../../etc"]}, 400),
        ({"question": "q", "node_ids": ["nd-0000000000000000"]}, 404),
    ],
)
def test_a_bad_ask_is_refused_before_anything_runs(client, monkeypatch, payload, status):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    _capture("https://x.example/a", "text")
    resp = client.post("/horizon/ask", json=payload)
    assert resp.status_code == status, resp.text
    assert seen == []


def test_an_empty_scope_is_refused_before_anything_runs(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    resp = client.post("/horizon/ask", json={"question": "q"})
    assert resp.status_code == 422
    assert seen == []


def test_a_capture_still_queued_cannot_be_chosen(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    queued = horizon.add_pending_node("https://x.example/q", "web")
    resp = client.post("/horizon/ask", json={"question": "q", "node_ids": [queued.id]})
    assert resp.status_code == 422
    assert seen == []


def test_the_budget_holds_for_a_chosen_list(client, monkeypatch):
    seen: list = []
    _mock_runner(monkeypatch, _answer(), seen)
    monkeypatch.setenv("PN_HORIZON_ASK_CHARS", "10")
    big = _capture("https://x.example/a", "x" * 50)
    resp = client.post("/horizon/ask", json={"question": "q", "node_ids": [big]})
    assert resp.status_code == 422
    assert seen == []


def test_a_malformed_bound_is_a_500_not_an_escaped_exit(client, monkeypatch):
    """Invariant 24: every `SystemExit` a handler can reach becomes a 500."""
    monkeypatch.setenv("PN_HORIZON_ASK_ITEMS", "many")
    _capture("https://x.example/a", "text")
    resp = client.post("/horizon/ask/preview", json={"question": "q"})
    assert resp.status_code == 500
    assert "PN_HORIZON_ASK_ITEMS" in resp.json()["detail"]


def test_an_old_ask_is_checked_again_against_the_captures_as_they_are_now(client, monkeypatch):
    _mock_runner(monkeypatch, _answer())
    a = _capture("https://x.example/a", "sleep consolidates memory")
    ask_id = client.post("/horizon/ask", json={"question": "q"}).json()["id"]
    assert client.get(f"/horizon/asks/{ask_id}").json()["citations"][0]["verified"] is True
    horizon.remove_node(a)
    again = client.get(f"/horizon/asks/{ask_id}").json()
    assert again["citations"][0]["verified"] is False
    assert again["citations"][0]["reason"]


def test_an_ask_can_be_removed(client, monkeypatch):
    _mock_runner(monkeypatch, _answer())
    _capture("https://x.example/a", "text")
    ask_id = client.post("/horizon/ask", json={"question": "q"}).json()["id"]
    assert client.delete(f"/horizon/asks/{ask_id}").json() == {"removed": True}
    assert client.get(f"/horizon/asks/{ask_id}").status_code == 404
    assert client.get("/horizon/asks/not-an-id").status_code == 400


def test_the_run_is_reachable_through_the_ordinary_run_routes(client, monkeypatch):
    """Stop and the ticker for a Horizon ask are the orbit routes under the reserved handle."""
    _mock_runner(monkeypatch, _answer())
    api._RUN_PROCESSES[f"{api.HORIZON_ASK_KEY}-abc"] = None
    try:
        runs = client.get(f"/orbits/{api.HORIZON_ASK_KEY}/runs").json()["runs"]
        assert runs == [f"{api.HORIZON_ASK_KEY}-abc"]
        stop = client.post(f"/orbits/{api.HORIZON_ASK_KEY}/runs/{api.HORIZON_ASK_KEY}-abc/cancel")
        assert stop.json()["detail"] == "stopped before it started"
    finally:
        api._RUN_PROCESSES.pop(f"{api.HORIZON_ASK_KEY}-abc", None)
        api._CANCELLED_BEFORE_SPAWN.discard(f"{api.HORIZON_ASK_KEY}-abc")


def test_no_orbit_can_take_the_reserved_handle(client):
    resp = client.post(f"/orbits/{api.HORIZON_ASK_KEY}/notes", json={"text": "hi"})
    assert resp.status_code in (400, 404)
    node = _capture("https://x.example/a", "text")
    promoted = client.post(f"/horizon/{node}/promote", json={"orbit_id": api.HORIZON_ASK_KEY, "create": True})
    assert promoted.status_code == 400


def test_concepts_list_what_a_scope_can_be(client):
    _capture("https://x.example/a", "x", tags=["sleep"], entities=["REM"])
    body = client.get("/horizon/concepts").json()
    assert body == {"tags": [{"name": "sleep", "count": 1}], "entities": [{"name": "REM", "count": 1}]}


def test_the_history_routes_are_not_swallowed_by_the_node_routes(client):
    """`/horizon/{node_id}` is a catch-all one segment deep; `/horizon/asks` must win."""
    assert client.get("/horizon/asks").status_code == 200
    assert client.get("/horizon/concepts").status_code == 200


def test_the_history_table_skips_an_unreadable_row():
    record = asks.add_ask(scope_kind="all", scope_value=None, question="q",
                          answer=api.Answer(text="a"), sources=[], strategy="all", run_id=None)
    import sqlite3

    conn = sqlite3.connect(horizon.index_path())
    conn.execute("UPDATE asks SET answer = '{broken' WHERE id = ?", (record.id,))
    conn.commit()
    conn.close()
    assert asks.list_asks() == []


def test_a_corrupt_history_row_is_a_409_not_a_bare_500(client):
    record = asks.add_ask(scope_kind="all", scope_value=None, question="q",
                          answer=api.Answer(text="a"), sources=[], strategy="all", run_id=None)
    import sqlite3

    conn = sqlite3.connect(horizon.index_path())
    conn.execute("UPDATE asks SET answer = '{broken' WHERE id = ?", (record.id,))
    conn.commit()
    conn.close()
    resp = client.get(f"/horizon/asks/{record.id}")
    assert resp.status_code == 409
    assert "cannot be read" in resp.json()["detail"]


def test_the_landing_orbit_never_takes_the_reserved_handle(monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", api.HORIZON_ASK_KEY)
    node = _capture("https://x.example/a", "text")
    api._file_into_landing_orbit(node)
    assert horizon.memberships_for(node) == []
