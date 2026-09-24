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


def test_topology_and_graph_are_served(client):
    _capture("https://x.example/a", "x", entities=["REM"], tags=["sleep"], state="ready")
    star = client.get("/horizon/topology").json()
    assert star["total"] == {"count": 1, "distilled": 1}
    graph = client.get("/horizon/graph").json()
    assert graph["entities"] == [{"name": "REM", "count": 1}]
    assert client.get("/horizon/graph", params={"orbit": "nothing"}).json()["entities"] == []


def test_an_orbit_narrowed_ask_is_kept_with_its_orbit(client, monkeypatch):
    _mock_runner(monkeypatch, _answer())
    node = _capture("https://x.example/a", "sleep consolidates memory", entities=["REM"])
    horizon.promote_node(node, "sleep", create=True)
    scope = {"kind": "entity", "value": "REM", "orbit": "sleep"}
    body = client.post("/horizon/ask", json={"question": "q", "scope": scope}).json()
    assert body["scope"] == scope
    assert client.get("/horizon/asks").json()["asks"][0]["scope"] == scope


def test_the_summary_pass_can_be_limited_to_one_orbit(client, monkeypatch):
    seen: list = []

    def fake_pass(limit, language, node_ids=None):
        seen.append((limit, node_ids))
        with api._DISTIL_GUARD:
            api._DISTIL.update({"running": False})

    monkeypatch.setattr(api, "_run_distil_pass", fake_pass)
    inside = _capture("https://x.example/a", "one")
    _capture("https://x.example/b", "two")
    horizon.promote_node(inside, "sleep", create=True)
    resp = client.post("/horizon/distil", json={"limit": 20, "orbit_id": "sleep"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
    import time

    for _ in range(50):
        if seen:
            break
        time.sleep(0.01)
    assert seen == [(1, [inside])]


def test_stopping_one_orbits_summary_leaves_the_capture_queue_alone(client, monkeypatch):
    dropped: list = []
    monkeypatch.setattr(api._horizon_queue(), "cancel_pending", lambda: dropped.append(1) or [])
    resp = client.post("/horizon/distil/cancel")
    assert resp.status_code == 200
    assert dropped == []
    with api._DISTIL_GUARD:
        assert api._DISTIL["cancel"] is True
        api._DISTIL["cancel"] = False


def test_the_graph_and_a_narrowed_scope_accept_an_orbit_id_that_differs_from_its_slug(client, monkeypatch):
    from penumbra.orbit import slug

    _mock_runner(monkeypatch, _answer())
    node = _capture("https://x.example/a", "sleep", entities=["REM"])
    horizon.promote_node(node, "模型要睡覺", create=True)
    assert client.get("/horizon/graph", params={"orbit": "模型要睡覺"}).json()["entities"][0]["name"] == "REM"
    scope = {"kind": "entity", "value": "REM", "orbit": "模型要睡覺"}
    preview = client.post("/horizon/ask/preview", json={"question": "q", "scope": scope}).json()
    assert preview["count"] == 1
    body = client.post("/horizon/ask", json={"question": "q", "scope": scope}).json()
    assert body["scope"]["orbit"] == slug("模型要睡覺")


def test_a_blank_orbit_is_refused_rather_than_matching_nothing(client):
    assert client.get("/horizon/graph", params={"orbit": "   "}).status_code == 400
    scope = {"kind": "tag", "value": "x", "orbit": "  "}
    assert client.post("/horizon/ask/preview", json={"question": "q", "scope": scope}).status_code == 422


def test_stop_ends_a_long_document_worker_at_once(client):
    class _Run:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    run = _Run()
    api._DISTIL_RUN["run"] = run
    try:
        assert client.post("/horizon/distil/cancel").status_code == 200
        assert run.cancelled
    finally:
        api._DISTIL_RUN["run"] = None
        with api._DISTIL_GUARD:
            api._DISTIL["cancel"] = False


def test_the_estimate_counts_a_long_capture_as_a_range(client):
    from penumbra import distill

    short = _capture("https://x.example/a", "short")
    long = _capture("https://x.example/b", "x" * (distill.SHORT_LIMIT + 10))
    horizon.promote_node(short, "mix", create=True)
    horizon.promote_node(long, "mix", create=True)
    got = client.get("/horizon/distil/estimate", params={"orbit": "mix"}).json()
    # The top is a bound: the long document and the one alignment run, each at the full RLM budget.
    cfg = api.PenumbraConfig.from_env()
    per_run = cfg.max_retries * (cfg.max_iterations + cfg.max_llm_calls + 1)
    assert got == {"count": 2, "short": 1, "long": 1, "calls_min": 4, "calls_max": 1 + 2 * per_run}
    assert client.get("/horizon/distil/estimate").json()["count"] == 2


def test_a_pass_that_wrote_new_names_ends_with_one_alignment(client, monkeypatch):
    from penumbra import concepts

    _capture("https://x.example/a", "x", entities=["Matthew Walker"], state="ready")
    _capture("https://x.example/b", "y", entities=["馬修·沃克"], state="ready")
    calls = []

    def fake_task(dotted, kwargs, prefix):
        calls.append((dotted, prefix, kwargs["new_names"]))
        return {"merges": [{"alias": "馬修·沃克", "canonical": "Matthew Walker"},
                           {"alias": "Nobody", "canonical": "Matthew Walker"}]}

    monkeypatch.setattr(api, "_run_pass_task", fake_task)
    # A server teardown (every TestClient exit) sets the Stop flag; a pass clears it when it starts.
    with api._DISTIL_GUARD:
        api._DISTIL["cancel"] = False
    api._align_after_pass(horizon.DEFAULT_HORIZON_DIR)
    assert len(calls) == 1 and calls[0][0].endswith(":AlignConcepts")
    assert concepts.aliases() == {"馬修·沃克": "Matthew Walker"}, "an invented name was merged"
    assert concepts.unseen() == []
    api._align_after_pass(horizon.DEFAULT_HORIZON_DIR)
    assert len(calls) == 1, "names already aligned were paid for again"
    assert client.post("/horizon/aliases/remove", json={"alias": "馬修·沃克"}).json() == {"removed": True}
    assert client.post("/horizon/aliases/remove", json={"alias": "馬修·沃克"}).status_code == 404


def test_a_stopped_pass_does_not_go_on_to_align(monkeypatch):
    _capture("https://x.example/a", "x", entities=["A"], state="ready")
    _capture("https://x.example/b", "y", entities=["B"], state="ready")
    monkeypatch.setattr(api, "_run_pass_task", lambda *a: pytest.fail("aligned after Stop"))
    with api._DISTIL_GUARD:
        api._DISTIL["cancel"] = True
    try:
        api._align_after_pass(horizon.DEFAULT_HORIZON_DIR)
    finally:
        with api._DISTIL_GUARD:
            api._DISTIL["cancel"] = False


def test_a_failed_alignment_is_reported_and_tried_again_next_pass(client, monkeypatch):
    from penumbra import concepts

    _capture("https://x.example/a", "x", entities=["A"], state="ready")
    _capture("https://x.example/b", "y", entities=["B"], state="ready")

    def boom(*_):
        raise RuntimeError("worker died")

    monkeypatch.setattr(api, "_run_pass_task", boom)
    with api._DISTIL_GUARD:
        api._DISTIL["cancel"] = False
    api._align_after_pass(horizon.DEFAULT_HORIZON_DIR)
    assert "worker died" in client.get("/horizon/status").json()["align"]["error"]
    assert set(concepts.unseen()) == {"A", "B"}
    api._align_after_pass(horizon.DEFAULT_HORIZON_DIR)  # the same names failing a second time
    assert concepts.unseen() == [], "a persistent failure would be paid for at the end of every pass"
    with api._DISTIL_GUARD:
        api._ALIGN.update({"error": "", "failures": 0})


def test_suggestions_are_served_and_can_be_declined(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    filed = _capture("https://x.example/a", "x", entities=["REM", "hippocampus"], state="ready")
    horizon.promote_node(filed, "sleep", create=True)
    loose = _capture("https://x.example/b", "y", entities=["REM", "hippocampus"], state="ready")
    body = client.get("/horizon/suggestions").json()
    assert body["count"] == 1 and body["suggestions"][0]["node_id"] == loose
    declined = client.post("/horizon/suggestions/dismiss", json={"node_id": loose, "orbit": "sleep"})
    assert declined.status_code == 200
    assert client.get("/horizon/suggestions").json()["count"] == 0
    bad = client.post("/horizon/suggestions/dismiss", json={"node_id": "../x", "orbit": "sleep"})
    assert bad.status_code == 400



def test_shutting_down_ends_the_summary_passs_worker():
    """A long-document or alignment worker runs in its own session; the server's teardown must end
    it, or it outlives the server and keeps billing (invariants 22, 81)."""
    class _Run:
        cancelled = False

        def cancel(self):
            self.cancelled = True

    run = _Run()
    with TestClient(api.app, base_url="http://127.0.0.1",
                    headers={"Authorization": f"Bearer {auth.api_token()}"}):
        api._DISTIL_RUN["run"] = run
    try:
        assert run.cancelled
    finally:
        api._DISTIL_RUN["run"] = None
        with api._DISTIL_GUARD:
            api._DISTIL["cancel"] = False


def test_a_stopped_node_is_not_counted_as_a_failure(monkeypatch):
    from penumbra import distill

    node = _capture("https://x.example/long", "x" * (distill.SHORT_LIMIT + 5))
    monkeypatch.setattr(api, "_configure_in_process_model", lambda: None)

    def stopped_worker(source, language):
        with api._DISTIL_GUARD:
            api._DISTIL["cancel"] = True  # the reader pressed Stop while it ran
        raise RuntimeError("worker produced no output (exit -9)")

    monkeypatch.setattr(api, "_run_long_distil", stopped_worker)
    with api._DISTIL_GUARD:
        api._DISTIL.update(
            {"running": True, "done": 0, "total": 1, "failed": 0, "error": "", "cancel": False}
        )
    api._run_distil_pass(1, "", [node])
    status = api._distil_status()
    assert status["failed"] == 0 and status["error"] == "", status
    assert horizon.get_node(node).state == "ready_undistilled"


def test_removing_a_source_keeps_its_capture_from_being_suggested_back(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    a = _capture("https://x.example/a", "x", entities=["REM", "hippocampus"], state="ready")
    b = _capture("https://x.example/b", "y", entities=["REM", "hippocampus"], state="ready")
    horizon.promote_node(a, "sleep", create=True)
    membership = horizon.promote_node(b, "sleep", create=True)
    assert client.delete(f"/orbits/sleep/sources/{membership.source_id}").status_code == 200
    assert client.get("/horizon/suggestions").json()["count"] == 0


def test_the_graph_draws_similar_captures_including_an_unsummarised_one(client, monkeypatch):
    a = _capture("https://x.example/a", "x", entities=["REM"], state="ready")
    b = _capture("https://x.example/b", "y")  # not summarised
    monkeypatch.setattr(api, "_similar_or_none", lambda: (lambda ids: [{"a": a, "b": b, "score": 0.9}]))
    graph = client.get("/horizon/graph").json()
    assert graph["similar"] == [{"a": a, "b": b, "score": 0.9}]
    assert b in {c["node_id"] for c in graph["captures"]}, "the linked unsummarised capture was not drawn"
    assert b in {u["node_id"] for u in graph["undistilled"]}, "it still needs a summary and still says so"


def test_an_unsummarised_capture_can_be_suggested_by_similarity(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    filed = _capture("https://x.example/a", "x", entities=["REM"], state="ready", title="Sleep review")
    horizon.promote_node(filed, "sleep", create=True)
    loose = _capture("https://x.example/b", "y")
    monkeypatch.setattr(api, "_matches_or_none",
                        lambda: (lambda node_id, among: [(filed, 0.9)] if node_id == loose else []))
    body = client.get("/horizon/suggestions").json()
    row = next(s for s in body["suggestions"] if s["node_id"] == loose)
    assert row["orbit"] == "sleep" and row["like"] == "Sleep review"


def test_vector_status_and_a_second_download_is_refused(client, monkeypatch):
    monkeypatch.setattr(api, "_download_model", lambda: None)
    status = client.get("/horizon/vectors").json()
    assert status["installed"] is False and status["bytes"] > 100_000_000
    assert client.post("/horizon/vectors/download").status_code == 200
    assert client.post("/horizon/vectors/download").status_code == 409
    assert client.delete("/horizon/vectors").status_code == 409
    with api._VECTORS_LOCK:
        api._VECTOR_DL.update(running=False, cancel=False)



def test_a_poll_during_add_cannot_cache_the_answer_from_before_it(client, monkeypatch):
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")
    filed = _capture("https://x.example/a", "x", entities=["REM", "hippocampus"], state="ready")
    horizon.promote_node(filed, "sleep", create=True)
    loose = _capture("https://x.example/b", "y", entities=["REM", "hippocampus"], state="ready")
    real = horizon.promote_node

    def promote_with_a_poll(*args, **kwargs):
        client.get("/horizon/suggestions")  # a poll lands while the membership is being written
        return real(*args, **kwargs)

    monkeypatch.setattr(horizon, "promote_node", promote_with_a_poll)
    assert client.post(f"/horizon/{loose}/promote", json={"orbit_id": "sleep"}).status_code == 200
    assert client.get("/horizon/suggestions").json()["count"] == 0
