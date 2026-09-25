"""The Horizon's HTTP surface (`/horizon/*`).

Needs the `api` extra to be COLLECTED AT ALL — it `importorskip`s `fastapi`, so without the extra it
is silently absent rather than failing. CI runs `uv sync --extra api` before the whole suite, so it
is covered there; a bare local `uv sync` will look greener than CI, which is the trap AGENTS.md's
Verify section describes.

Nothing here reaches the network or a model: `parse_web` is faked and the distillation pass is
injected, so what is exercised is the HANDLERS — the path ban, the size cap, the error mapping and
the cost rule.
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from penumbra import api, auth, horizon, ingest, intake
from penumbra.schema import Distillation, Source, SourceBlock


@pytest.fixture(autouse=True)
def _no_landing_orbit(monkeypatch):
    """These tests are about filing BY HAND, so automatic filing into the first orbit is off here;
    `test_landing_orbit.py` covers it."""
    monkeypatch.setenv("PN_LANDING_ORBIT", "off")


@pytest.fixture(autouse=True)
def _fake_web(monkeypatch):
    """Invariant 26 means this endpoint only ever takes http(s) URLs, so every capture test needs a
    fetcher that does not fetch."""
    def fake(url: str, source_id: str) -> Source:
        return Source(
            id=source_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text=f"body of {url}")]
        )

    monkeypatch.setattr(ingest, "parse_web", fake)


@pytest.fixture(autouse=True)
def _a_model_is_configured(monkeypatch):
    """The summary pass now CONFIGURES a model before it claims the first node, so these tests need
    `PN_*` set even though every one of them replaces `distil_source` with a stand-in.

    That is not fixture noise, it is the defect this file could not see. `config.setup()` was never
    called anywhere in the server process, so `POST /horizon/distil` could only ever produce
    `ValueError: No LM is loaded` — and the tests here were green throughout, because they patch
    `distil_source`, which is exactly the function whose real body could not work. `setup()` builds
    LM objects and opens no socket, so this costs nothing; `tests/test_distil_live.py` is the file
    that exercises the real path.
    """
    monkeypatch.setenv("PN_MAIN_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("PN_API_KEY", "sk-test")
    monkeypatch.setattr(api, "_MODEL_CONFIGURED", False)


@pytest.fixture(autouse=True)
def _fresh_queue():
    """`intake.shared()` is a process singleton and the API's lifespan STOPS it on shutdown. Reset it
    between tests so one test's stopped queue is not the next test's silent `queued` forever.

    `_DISTIL` is reset for the same reason and it is NEW: the auto pass reports through that shared
    state now (it used to report through nothing at all, which is the defect), so a test whose
    capture triggered an auto batch could leave `running: True` behind and the next test asserting
    an exact status dict would fail — passing alone and failing in the suite, which is the worst
    shape a test can have."""
    yield
    existing = intake._SHARED
    if existing is not None:
        existing.stop(timeout=5)
    intake._SHARED = None
    with api._DISTIL_GUARD:
        api._DISTIL.update(
            {"running": False, "done": 0, "total": 0, "failed": 0, "error": "", "cancel": False}
        )


@pytest.fixture
def client():
    with TestClient(
        api.app,
        base_url="http://127.0.0.1",
        headers={"Authorization": f"Bearer {auth.api_token()}"},
    ) as c:
        yield c


def _settle(client, node_id: str, *, want: str = "ready_undistilled", tries: int = 100) -> str:
    """The queue is a real thread; poll rather than sleep a fixed amount."""
    for _ in range(tries):
        state = client.get(f"/horizon/{node_id}").json()["node"]["state"]
        if state == want:
            return state
        time.sleep(0.02)
    return state


# --- invariant 26, which is the whole reason this endpoint is shaped the way it is -------------------


def test_listing_the_horizon_reports_a_clean_500_when_the_corpus_cap_env_var_is_malformed(
    client, monkeypatch
):
    """Invariant 24, on the screen the app opens to.

    `max_corpus_chars()` was the last statement of this handler and the only unguarded `_env_int`
    reader left on a request path. `SystemExit` inherits from `BaseException`, so Starlette's error
    middleware never sees it: an independent audit reproduced a raw `text/plain` 500 followed by the
    SERVER PROCESS EXITING — one authenticated GET, on a typo startup did not reject.
    """
    monkeypatch.setenv("PN_MAX_CORPUS_CHARS", "8M")
    resp = client.get("/horizon")
    assert resp.status_code == 500
    assert "server misconfigured" in resp.json()["detail"]
    # The process is still answering, which is the half a status code alone does not prove.
    monkeypatch.delenv("PN_MAX_CORPUS_CHARS")
    assert client.get("/horizon").status_code == 200


def test_a_malformed_corpus_cap_refuses_STARTUP_rather_than_waiting_for_the_first_request(
    monkeypatch,
):
    """Loud at boot beats a 500 on the default screen — the same choice `_lifespan` already makes
    for the trace-retention knobs and `auto_distil_max_per_batch`, and for the same reason: the
    operator who typed the value is present at startup and long gone by the first request.

    Drives `_lifespan` directly, for the reason the `PN_AUTO_DISTIL_MAX_PER_BATCH` test beside it
    gives: `TestClient` wraps whatever a lifespan raises in an anyio `ExceptionGroup` and reports
    the cancellation instead, so asserting through that wrapper tests the wrapper.
    """
    import asyncio

    monkeypatch.setenv("PN_MAX_CORPUS_CHARS", "nope")

    async def enter_and_leave() -> None:
        async with api._lifespan(api.app):
            pass

    with pytest.raises(SystemExit, match="PN_MAX_CORPUS_CHARS"):
        asyncio.run(enter_and_leave())




def test_a_local_path_is_refused_and_never_read(client, tmp_path):
    """**The attack invariant 26 records was reproduced end to end once** — `POST {"sources":
    ["/etc/passwd"]}` read the file and echoed it back through a citation that PASSED verification.
    `intake.submit` still accepts a path happily, because `ingest_one` does, which is correct for
    `cli.py` and an arbitrary-file-read vector the moment the same function sits behind HTTP.

    A SECOND capture endpoint is exactly where that comes back, so this is asserted here rather
    than inherited from the orbit one.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("SUPER-SECRET-CONTENTS", encoding="utf-8")

    for hostile in (str(secret), "/etc/passwd", "file:///etc/passwd", "../../etc/passwd", "~/.ssh/id_rsa"):
        resp = client.post("/horizon", json={"urls": [hostile]})
        assert resp.status_code == 422, hostile
        assert "invariant 26" in resp.json()["detail"]
        assert "SUPER-SECRET" not in resp.text

    assert client.get("/horizon").json()["total"] == 0, "a refused capture must create nothing"


# --- capture ------------------------------------------------------------------------------------------


def test_a_url_capture_returns_the_node_immediately_as_queued(client):
    """Invariant 79: the node exists the moment it is submitted, not when parsing finishes."""
    body = client.post("/horizon", json={"urls": ["https://example.com/a"]}).json()
    node = body["nodes"][0]
    assert node["state"] == "queued"
    assert node["kind"] == "web"
    assert _settle(client, node["id"]) == "ready_undistilled"
    stored = client.get(f"/horizon/{node['id']}/source").json()["source"]
    assert stored["blocks"][0]["text"].startswith("body of")


def test_pasted_text_skips_the_queue_and_is_ready_at_once(client):
    """`parse_text` plus the injection scan is microseconds; queueing it would only delay a node the
    reader is watching for."""
    node = client.post("/horizon", json={"texts": ["a pasted note"]}).json()["nodes"][0]
    assert node["state"] == "ready_undistilled"
    assert node["chars"] == len("a pasted note")
    # Content-derived origin, so the same paste twice is one node (invariant 78).
    again = client.post("/horizon", json={"texts": ["a pasted note"]}).json()["nodes"][0]
    assert again["id"] == node["id"]
    assert client.get("/horizon").json()["total"] == 1


def test_an_empty_capture_is_a_client_error(client):
    assert client.post("/horizon", json={}).status_code == 422
    assert client.post("/horizon", json={"texts": ["   "]}).json()["nodes"] == []


def test_an_unknown_field_is_refused_rather_than_ignored(client):
    assert client.post("/horizon", json={"sources": ["https://example.com/a"]}).status_code == 422


# --- listing, reading, removing --------------------------------------------------------------------


def test_the_listing_is_paged_and_reports_what_a_summary_pass_would_cost(client):
    for n in range(5):
        client.post("/horizon", json={"texts": [f"note {n}"]})
    page = client.get("/horizon?limit=2").json()
    assert len(page["nodes"]) == 2
    assert page["total"] == 5
    # Invariant 80: the count is knowable BEFORE anyone spends anything.
    assert page["undistilled"] == 5
    assert client.get("/horizon?limit=2&offset=4").json()["nodes"][0]["id"] not in {
        n["id"] for n in page["nodes"]
    }


def test_a_malformed_id_is_400_and_a_missing_one_is_404(client):
    """Invariant 27's rule at Tier 0: they are DIFFERENT answers, and neither is a raw 500.
    `horizon.node_blocks_path` raises `ValueError` for anything that is not a minted id — the same
    guard that stops `remove_node("../../orbits/mynb")` deleting a live orbit file."""
    for endpoint in ("/horizon/{}", "/horizon/{}/source"):
        assert client.get(endpoint.format("../../secret")).status_code in (400, 404)
        assert client.get(endpoint.format("nd-not-hex")).status_code == 400
        assert client.get(endpoint.format("nd-" + "0" * 16)).status_code == 404
    assert client.delete("/horizon/nd-not-hex").status_code == 400
    assert client.post(
        "/horizon/nd-not-hex/promote",
        json={"orbit_id": "x", "create": True},
    ).status_code == 400


def test_deleting_a_node_leaves_a_promoted_source_alone(client):
    node = client.post("/horizon", json={"texts": ["keep me"]}).json()["nodes"][0]
    client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "mynb", "create": True})

    assert client.delete(f"/horizon/{node['id']}").json()["removed"] is True
    assert client.get(f"/horizon/{node['id']}").status_code == 404
    # Invariant 12: promotion is a COPY, and tidying a horizon must not reach a cited source.
    assert len(client.get("/orbits/mynb").json()["sources"]) == 1


# --- promotion -------------------------------------------------------------------------------------


def test_promotion_assigns_the_orbits_own_source_id_and_keeps_the_node(client):
    node = client.post("/horizon", json={"texts": ["promote me"]}).json()["nodes"][0]
    membership = client.post(
        f"/horizon/{node['id']}/promote",
        json={"orbit_id": "work", "create": True},
    ).json()

    assert membership["membership"]["source_id"] != node["id"]
    assert client.get(f"/horizon/{node['id']}").json()["node"] is not None
    # The node is not consumed, so the same one can go into a second facet.
    client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "personal", "create": True})
    listed = client.get(f"/horizon/{node['id']}").json()["orbits"]
    assert {m["orbit_id"] for m in listed} == {"work", "personal"}


def test_promoting_a_node_with_no_text_yet_is_a_clean_400(client):
    """A `queued` node has no blocks file, so `node_source` returns `None` and `promote_node` raises
    `ValueError` BEFORE `mutate_orbit` — no empty orbit is created as a side effect."""
    node = horizon.add_pending_node("https://example.com/waiting", "web")
    resp = client.post(f"/horizon/{node.id}/promote", json={"orbit_id": "nb", "create": True})
    assert resp.status_code == 400
    assert client.get("/orbits/nb").status_code == 404


# --- the queue's own surface -------------------------------------------------------------------------


def test_status_and_cancel_report_what_is_actually_happening(client):
    """THREE things can be happening, and they are reported side by side rather than merged:
    parsing, summarising and aligning concepts fail differently, cost differently and stop
    differently, so a single "busy" would let the page claim one while another was true
    (invariant 60)."""
    assert client.get("/horizon/status").json() == {
        "running": False,
        "current": None,
        "pending": 0,
        "distil": {"running": False, "done": 0, "total": 0, "failed": 0, "error": ""},
        "align": {"running": False, "error": ""},
    }
    body = client.post("/horizon/cancel").json()
    assert body["dropped"] == 0
    assert body["distil"]["running"] is False


# --- invariant 80: capture never pays ------------------------------------------------------------------


def test_capturing_makes_no_model_call(client, monkeypatch):
    """**The cost rule, asserted through the HTTP surface.** BYOK plus "just throw everything in"
    means a 200-bookmark import must cost nothing until somebody says otherwise."""
    from penumbra import distill

    calls: list[object] = []
    monkeypatch.setattr(distill, "distil_source", lambda *a, **k: calls.append(a) or Distillation())

    for n in range(3):
        client.post("/horizon", json={"urls": [f"https://example.com/{n}"]})
    for node in client.get("/horizon").json()["nodes"]:
        _settle(client, node["id"])
    assert calls == [], "capture spent the reader's money"
    assert client.get("/horizon").json()["undistilled"] == 3


def test_distil_is_a_separate_verb_that_names_its_own_number(client, monkeypatch):
    from penumbra import distill

    monkeypatch.setattr(
        distill, "distil_source", lambda *a, **k: Distillation(title="T", summary="S", tags=["x"])
    )
    for n in range(3):
        client.post("/horizon", json={"texts": [f"note {n}"]})

    assert client.post("/horizon/distil", json={"limit": 0}).status_code == 422

    # STARTED, not awaited. Fifty sequential model calls inside a request is a request that times
    # out, and a disabled button is not progress (invariant 47) - so the endpoint reports the total
    # it is about to spend and `GET /horizon/status` carries the rest.
    started = client.post("/horizon/distil", json={"limit": 2}).json()
    assert started == {
        "started": True,
        "running": True,
        "done": 0,
        "total": 2,
        # A pass reports what FAILED as well as what finished. Without these two the status
        # could only ever describe success, which is what it did over a feature that never ran.
        "failed": 0,
        "error": "",
    }

    for _ in range(200):
        if client.get("/horizon/status").json()["distil"]["running"] is False:
            break
        time.sleep(0.02)
    assert client.get("/horizon/status").json()["distil"]["running"] is False
    assert client.get("/horizon").json()["undistilled"] == 1
    assert client.get("/horizon?state=ready").json()["nodes"][0]["title"] == "T"


def test_auto_distillation_is_off_by_default_and_on_when_the_operator_says_so(client, monkeypatch):
    """The toggle the settings page exposes (a BEHAVIOUR preference — `POST /horizon/distil` is
    already a spend endpoint any token holder can call). Its BOUND,
    `PN_AUTO_DISTIL_MAX_PER_BATCH`, stays environment-only, which is invariant 41's placement rule.
    """
    from penumbra import distill

    seen: list[int] = []
    monkeypatch.setattr(
        distill, "distil_source", lambda *a, **k: seen.append(1) or Distillation(title="auto")
    )

    monkeypatch.delenv("PN_AUTO_DISTIL", raising=False)
    node = client.post("/horizon", json={"urls": ["https://example.com/off"]}).json()["nodes"][0]
    _settle(client, node["id"])
    assert seen == [], "the default must not spend"

    monkeypatch.setenv("PN_AUTO_DISTIL", "on")
    node = client.post("/horizon", json={"urls": ["https://example.com/on"]}).json()["nodes"][0]
    for _ in range(100):
        if client.get(f"/horizon/{node['id']}").json()["node"]["state"] == "ready":
            break
        time.sleep(0.02)
    assert seen, "the idle hook never fired"
    assert client.get(f"/horizon/{node['id']}").json()["node"]["title"] == "auto"


def test_the_auto_pass_never_reports_more_done_than_it_said_it_would(client, monkeypatch):
    """**`done` may not climb past `total`, on the one action that spends the reader's money.**

    `_auto_distil_after_intake` announces `total = min(limit, pending)` from a `count_nodes`
    snapshot and then ran `distil_pending(limit=limit)` — the raw CAP. `distil_pending` takes its
    own `list_nodes` when it actually starts, so anything that reached `ready_undistilled` between
    the two was summarised as well and ticked `done` past `total`: the strip rendered `2 / 1`, then
    `3 / 1`. Nothing was lost, which is what made it survivable and invisible; the counter on a
    spend action was simply wrong.

    The window is between `count_nodes` and `distil_pending`, on the queue's worker thread, and
    `_configure_in_process_model()` is the call that sits in it. Putting the node there is what
    makes the race deterministic instead of a sleep — and it goes in through `horizon.add_node`
    rather than a capture, because a capture would make the queue busy and `should_stop` would
    correctly yield before the bug could show.
    """
    from penumbra import api, distill, horizon
    from penumbra.schema import Source, SourceBlock

    monkeypatch.setenv("PN_AUTO_DISTIL", "on")
    monkeypatch.setenv("PN_AUTO_DISTIL_MAX_PER_BATCH", "5")

    calls: list[str] = []
    monkeypatch.setattr(
        distill,
        "distil_source",
        lambda *a, **k: calls.append("x") or Distillation(title="T", summary="S", tags=["x"]),
    )

    real_configure = api._configure_in_process_model

    def configure_and_let_one_more_arrive() -> None:
        real_configure()
        if len(calls) == 0:  # once, in the window the live version raced
            horizon.add_node(
                Source(
                    id="s0",
                    kind="text",
                    origin="arrived-in-the-window",
                    blocks=[SourceBlock(locator="whole", text="a node that landed after the snapshot")],
                )
            )

    monkeypatch.setattr(api, "_configure_in_process_model", configure_and_let_one_more_arrive)

    node = client.post("/horizon", json={"texts": ["the first note"]}).json()["nodes"][0]
    _settle(client, node["id"])
    for _ in range(200):
        if not client.get("/horizon/status").json()["distil"]["running"] and calls:
            break
        time.sleep(0.02)

    distil = client.get("/horizon/status").json()["distil"]
    assert calls, "the idle hook never fired, so this proves nothing"
    assert distil["done"] <= distil["total"], (
        f"the summary pass reported more finished than it said it would spend: {distil}"
    )


def test_two_uploaded_files_with_the_same_name_are_two_nodes(client):
    """**The other way a capture surface drops a file quietly, and this one answered 200.**

    `node_id_for` hashed the ORIGIN whenever it was non-empty, and an upload's origin is its
    filename. Two different files both called `notes.txt` therefore resolved to one node id;
    `add_node` is idempotent, so the second found the row already there and returned it untouched.
    The batch answered `{"nodes": [A, A], "refused": []}` — the same node twice, reported as two
    successful captures, with the second file's bytes gone. Invariant 79 says a capture always
    lands, and nothing here failed, so nothing could be retried.

    A filename is not an identity. A URL is, which is why it keeps hashing origin-only: a queued
    capture mints its node id before it has any content to hash (invariant 79).
    """
    resp = client.post(
        "/horizon/upload",
        files=[
            ("file", ("notes.txt", b"the first file's contents", "text/plain")),
            ("file", ("notes.txt", b"a completely different file", "text/plain")),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["refused"] == []
    ids = [n["id"] for n in body["nodes"]]
    assert len(ids) == 2, body
    assert len(set(ids)) == 2, f"both files collapsed into one node: {ids}"

    # Both texts are actually READABLE afterwards - the id being distinct is not the point on its
    # own, keeping the bytes is.
    texts = {
        "".join(b["text"] for b in client.get(f"/horizon/{node_id}/source").json()["source"]["blocks"])
        for node_id in ids
    }
    assert texts == {"the first file's contents", "a completely different file"}, texts

    # ...and re-uploading the SAME file is still one node, which is the dedupe that made hashing
    # the origin attractive in the first place.
    again = client.post(
        "/horizon/upload", files=[("file", ("notes.txt", b"the first file's contents", "text/plain"))]
    )
    assert again.json()["nodes"][0]["id"] == ids[0]
    assert client.get("/horizon").json()["total"] == 2


def test_the_same_url_captured_twice_is_still_one_node_even_if_its_text_changed(client, monkeypatch):
    """The half that must NOT fold text into the id. A URL identifies a place, not a version: a page
    re-captured after an edit is the same capture, and `add_pending_node` has to mint the node id
    before the fetch has happened at all (invariant 79), so for a URL there is no text to fold."""
    from penumbra import horizon

    first = horizon.node_id_for("https://example.com/a", "what the page said in March")
    second = horizon.node_id_for("https://example.com/a", "what it says now")
    pending = horizon.node_id_for("https://example.com/a")
    assert first == second == pending, "a URL's identity is the URL"


def test_the_orbit_upload_refuses_a_batch_instead_of_keeping_the_last_file(client):
    """**Dropping a file the caller chose is the one thing a capture surface may never do quietly.**

    `form.get("file")` returns the LAST part, so `-F file=@note.txt -F file=@broken.pdf` stored
    neither and answered `422 could not ingest 'broken.pdf'` — naming only the file that failed,
    with the one that would have worked neither stored nor mentioned. `/horizon/upload` is the batch
    surface (invariant 30) and takes all of them; this endpoint is single-file, which is a scope
    rather than a licence to silently keep one.
    """
    resp = client.post(
        "/orbits/reading/sources/upload",
        files=[
            ("file", ("a.txt", b"the first file", "text/plain")),
            ("file", ("b.txt", b"the second file", "text/plain")),
        ],
    )
    assert resp.status_code == 422
    assert "2 were sent" in resp.json()["detail"]
    assert "none were stored" in resp.json()["detail"]
    # And nothing landed: a refusal that half-applied would be worse than the silent drop.
    assert client.get("/orbits/reading").status_code == 404

    # One file still works, which is the scope.
    ok = client.post(
        "/orbits/reading/sources/upload",
        files={"file": ("a.txt", b"the first file", "text/plain")},
    )
    assert ok.status_code == 200
    assert [s["origin"] for s in ok.json()["sources"]] == ["a.txt"]


# --- invariant 30: the size cap is checked before the body is parsed -------------------------------


def test_the_upload_cap_is_enforced_from_content_length(client, monkeypatch):
    monkeypatch.setenv("PN_MAX_UPLOAD_BYTES", "10")
    resp = client.post(
        "/horizon/upload", files={"file": ("big.txt", b"x" * 100, "text/plain")}
    )
    assert resp.status_code == 413
    assert client.get("/horizon").json()["total"] == 0


def test_an_upload_lands_as_a_node(client):
    resp = client.post("/horizon/upload", files={"file": ("notes.md", b"# heading", "text/markdown")})
    assert resp.status_code == 200
    node = resp.json()["nodes"][0]
    assert node["state"] == "ready_undistilled"
    assert node["kind"] == "text"


def test_an_unsupported_upload_type_is_refused_by_name(client):
    resp = client.post("/horizon/upload", files={"file": ("sheet.xlsx", b"PK\x03\x04", "application/zip")})
    assert resp.status_code == 422
    assert ".xlsx" in resp.json()["detail"]


# --- invariant 77 covers these automatically, and that is worth proving --------------------------------


def test_every_horizon_route_needs_the_token():
    """Deny-by-default (invariant 77): the allowlist is the static directory, so a route added here
    is protected because nobody did anything. `test_api.py` asserts that over the whole route table;
    this checks the ones this slice added, by hand, once."""
    anon = TestClient(api.app, base_url="http://127.0.0.1")
    assert anon.get("/horizon").status_code == 401
    assert anon.post("/horizon", json={"texts": ["x"]}).status_code == 401
    assert anon.get("/horizon/status").status_code == 401
    assert anon.post("/horizon/distil", json={"limit": 1}).status_code == 401
    assert anon.delete("/horizon/nd-" + "0" * 16).status_code == 401


# --- regressions found by an independent review ---------------------------------------------------


def test_a_second_server_lifecycle_can_still_capture(_fake_web):
    """**The hollow green that mattered.** `stop()` is terminal and the ASGI shutdown calls it, but
    `intake.shared()` is a PROCESS singleton — so the second `with TestClient(app)` in one process
    got a queue whose worker refuses to start, and a URL captured after that sat at `queued` forever
    while the request returned 200. Invariant 79's named worst failure, wearing a 200.

    Two lifecycles in ONE test, deliberately: the `_fresh_queue` fixture resets the singleton BETWEEN
    tests, which is exactly what hid this.
    """
    headers = {"Authorization": f"Bearer {auth.api_token()}"}
    states = []
    for cycle in range(2):
        with TestClient(api.app, base_url="http://127.0.0.1", headers=headers) as c:
            node = c.post("/horizon", json={"urls": [f"https://example.com/cycle{cycle}"]}).json()["nodes"][0]
            states.append(_settle(c, node["id"]))
    assert states == ["ready_undistilled", "ready_undistilled"], states


def test_the_listing_cap_cannot_be_defeated_by_a_negative_limit(client):
    """SQLite reads a negative `LIMIT` as "no limit", and `min(limit, 200)` had no floor — measured
    at 303 rows from a handler whose own docstring says it must stay cheap at thousands."""
    for n in range(210):
        horizon.add_node(
            Source(id="s0", kind="text", origin=f"p{n}", blocks=[SourceBlock(locator="whole", text="t")])
        )
    assert len(client.get("/horizon?limit=200").json()["nodes"]) == 200
    # REFUSED rather than silently clamped: a caller that asked for 500 believes something about
    # what it got back, which is invariant 9's reasoning applied to a query parameter.
    assert client.get("/horizon?limit=500").status_code == 422
    assert client.get("/horizon?limit=-1").status_code == 422
    assert client.get("/horizon?limit=0").status_code == 422


def test_out_of_range_integers_are_a_422_not_a_500(client):
    """Unbounded ints reached `sqlite3` and came back as a plain-text `OverflowError` 500 — not even
    JSON — from one ordinary request."""
    assert client.get("/horizon?offset=100000000000000000000").status_code == 422
    assert client.post("/horizon/distil", json={"limit": 100000000000000000000}).status_code == 422
    assert client.post("/horizon/distil", json={"limit": 0}).status_code == 422


def test_promotion_losing_a_race_with_deletion_leaves_the_orbit_unchanged(client):
    """**The hard stop.** `memberships.node_id` has a foreign key, so a node removed mid-promotion
    made the INSERT fail — by which time `mutate_orbit` had already written the source. Measured:
    two of twelve concurrent pairs returned a raw 500 AND left the orbit holding a source no
    membership row recorded. The caller saw a failure; the orbit silently grew.

    Deterministic here rather than raced: the node is removed between the append and the membership
    insert, which is the exact interleaving the race produces.
    """
    from penumbra.orbit import load_orbit

    node = client.post("/horizon", json={"texts": ["racy"]}).json()["nodes"][0]
    real_append = horizon.append_sources

    def append_then_vanish(orbit, sources):
        appended = real_append(orbit, sources)
        horizon.remove_node(node["id"])          # the DELETE lands here
        return appended

    horizon.append_sources = append_then_vanish
    try:
        resp = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "racenb", "create": True})
    finally:
        horizon.append_sources = real_append

    assert resp.status_code == 400, resp.text
    assert "removed while it was being promoted" in resp.json()["detail"]
    book = load_orbit("racenb")
    assert book is None or book.sources == [], "a failed promotion left an unrecorded source behind"


def test_the_auto_distil_setting_is_writable_and_survives_another_save(client, monkeypatch):
    """`GET /settings` reported it while `PUT` refused it with a 422 — and because the body is a FULL
    replacement, the only other way to set it was wiped by the next legitimate save."""
    monkeypatch.delenv("PN_AUTO_DISTIL", raising=False)
    monkeypatch.delenv("PN_OUTPUT_LANGUAGE", raising=False)

    assert client.put("/settings", json={"auto_distil": "on"}).status_code == 200
    assert client.get("/settings").json()["auto_distil"]["value"] == "on"
    # A full replacement that names it keeps it; one that does not, clears it — stated semantics.
    client.put("/settings", json={"auto_distil": "on", "output_language": "Japanese"})
    assert client.get("/settings").json()["auto_distil"]["value"] == "on"
    assert client.put("/settings", json={"auto_distil": "nonsense"}).status_code in (400, 422)


def test_every_uploaded_file_is_ingested_not_just_the_last(client):
    """`form.get` returns the LAST value for a repeated key, so two of three files were dropped with
    no message — under a response shape that reads as "several are fine"."""
    resp = client.post(
        "/horizon/upload",
        files=[
            ("file", ("a.md", b"aaa", "text/markdown")),
            ("file", ("b.md", b"bbbb", "text/markdown")),
            ("file", ("c.md", b"ccccc", "text/markdown")),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()["nodes"]) == 3
    assert client.get("/horizon").json()["total"] == 3


def test_a_malformed_multipart_body_is_a_400_not_a_raw_500(client):
    """Neither `MultiPartException` nor `MultipartParseError` is an `HTTPException`, so both escaped
    as plain-text `Internal Server Error`. Pre-existing on the orbit uploader, which the Horizon's
    copied — so both are fixed, and both are asserted."""
    for endpoint in ("/horizon/upload", "/orbits/mynb/sources/upload"):
        resp = client.post(
            endpoint,
            content=b"--boundary\r\nnot a valid part at all",
            headers={"Content-Type": "multipart/form-data; boundary=boundary"},
        )
        assert resp.status_code == 400, f"{endpoint} -> {resp.status_code}"


def test_the_idle_hook_yields_to_a_capture_that_arrives_mid_batch(client, monkeypatch):
    """Invariant 47 applied to a batch nobody pressed a button for. The hook runs on the queue's own
    worker thread, so while it summarises nothing parses — a capture arriving mid-batch waited for
    the WHOLE batch. `should_stop` had no caller anywhere until this.

    Deterministic, not timed: the first summary BLOCKS until this test releases it, so the hook is
    provably mid-batch when the capture arrives. `should_stop` is checked between nodes, so the
    held call finishes and then the batch must stop — the assertion is the CALL COUNT, not a clock.
    """
    import threading

    from penumbra import distill

    monkeypatch.setenv("PN_AUTO_DISTIL", "on")
    calls: list[int] = []
    held = threading.Event()
    reached = threading.Event()

    def slow(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            reached.set()
            held.wait(5)
        return Distillation(title="auto")

    # The count is recorded from INSIDE the parse, not polled afterwards. Polling reads the state and
    # the counter as two separate actions, and the NEXT idle hook runs between them — which is how
    # an earlier version of this test reported 6 and 8 on different runs for the same behaviour.
    observed: dict[str, int] = {}

    def parse(url: str, source_id: str) -> Source:
        if "urgent" in url:
            observed["calls_at_parse"] = len(calls)
        return Source(
            id=source_id, kind="web", origin=url, blocks=[SourceBlock(locator="whole", text="x")]
        )

    monkeypatch.setattr(ingest, "parse_web", parse)
    monkeypatch.setattr(distill, "distil_source", slow)
    for n in range(6):
        client.post("/horizon", json={"texts": [f"note {n}"]})
    client.post("/horizon", json={"urls": ["https://example.com/trigger"]})

    assert reached.wait(5), "the idle hook never started summarising"
    client.post("/horizon", json={"urls": ["https://example.com/urgent"]})
    held.set()

    for _ in range(300):
        if "calls_at_parse" in observed:
            break
        time.sleep(0.01)

    assert "calls_at_parse" in observed, "the arriving capture was never parsed"
    # Seven nodes were waiting to be summarised when it arrived. Without the yield it waits for all
    # of them; with it, the batch ends at the first node boundary after the capture lands.
    assert observed["calls_at_parse"] <= 2, f"the capture waited for {observed['calls_at_parse']}"


class _NoReentry:
    """A `_DISTIL_GUARD` stand-in that RAISES on re-entry instead of blocking forever.

    **Every test that drives a `_DISTIL_GUARD` region uses this, and that is not optional.** The
    deadlock these tests exist for is on the ASGI event loop, so reproducing it for real leaves the
    lock held and takes the rest of the run with it: measured, the whole suite hung past 600s, and
    neither `pyproject.toml` nor the CI job sets a timeout — so GitHub's 6-hour default applies and
    the result reads as "cancelled" rather than "this test failed". The CHANGELOG claimed a
    regression "fails instead of hanging CI"; an independent review reproduced the hang. It is true
    now because the acquisition below is non-blocking.

    With no competing thread, a failed non-blocking acquire can only mean this thread already holds
    it, which is exactly the fault under test.
    """

    def __init__(self, inner):
        self._inner = inner

    def __enter__(self):
        if not self._inner.acquire(blocking=False):
            raise AssertionError(
                "a handler re-entered _DISTIL_GUARD while already holding it - this is the "
                "deadlock that wedged the event loop; call _distil_snapshot() instead"
            )
        return self

    def __exit__(self, *exc):
        self._inner.release()
        return False

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_asking_for_a_summary_pass_with_nothing_pending_answers_instead_of_wedging(
    client, monkeypatch
):
    """**This branch wedged the entire server, and nothing in the suite executed it.**

    `distil_horizon` holds `_DISTIL_GUARD` — a plain, non-reentrant `threading.Lock` — and its
    `total == 0` early return called `_distil_status()`, which takes the same lock. The handler is
    `async`, so the deadlock was on the ASGI EVENT LOOP: no further request was answered, static
    page included, and the process survived SIGINT and SIGTERM. Only SIGKILL ended it.

    Every existing `/horizon/distil` test posts with pending nodes, so `total > 0` in all of them. The
    shipped UI reaches this branch by design — `app.js` handles `started: false` with a comment
    recording that it had already fired in the wild — via a stale count, a second tab, an
    auto-distil pass finishing first, or a node deleted between the poll and the press.
    """
    # `_NoReentry` so a REGRESSION fails in milliseconds instead of hanging the run — see its
    # docstring. It changes nothing about the passing path: a handler that does not re-enter never
    # touches the non-blocking branch.
    monkeypatch.setattr(api, "_DISTIL_GUARD", _NoReentry(api._DISTIL_GUARD))
    assert client.get("/horizon/status").json()["distil"]["running"] is False
    resp = client.post("/horizon/distil", json={"limit": 4})
    assert resp.status_code == 200, resp.text
    assert resp.json()["started"] is False, "there was nothing to summarise"
    # The half a status code alone does not prove: the process is still answering.
    assert client.get("/horizon/status").status_code == 200
    assert client.get("/horizon").status_code == 200


def test_no_handler_re_enters_the_summary_lock(client, monkeypatch):
    """The same defect as the test above, asserted as the PROPERTY rather than the symptom — and
    deliberately in a way that cannot hang.

    Driving the deadlock directly would leave `_DISTIL_GUARD` held forever and take the rest of the
    run down with it, which is a worse CI failure than the bug. So the lock is wrapped in a proxy
    that acquires non-blockingly: with no competing thread, a failed acquisition can only mean this
    thread already holds it, and the proxy raises instead of waiting.

    `_DISTIL_GUARD` must also STAY non-reentrant. Swapping it for an `RLock` would silence this
    without removing anything — the next nested acquisition would simply become invisible again.
    """
    import threading

    assert not isinstance(api._DISTIL_GUARD, type(threading.RLock())), (
        "an RLock hides re-entry rather than preventing it; keep the read split from the locking"
    )

    monkeypatch.setattr(api, "_DISTIL_GUARD", _NoReentry(api._DISTIL_GUARD))
    # Both `_DISTIL_GUARD` regions a request can reach: the empty pass and cancel.
    assert client.post("/horizon/distil", json={"limit": 4}).status_code == 200
    assert client.post("/horizon/cancel").status_code == 200
    assert client.get("/horizon/status").status_code == 200


def test_a_failed_summary_pass_can_be_dismissed_instead_of_greeting_everyone_forever(client):
    """**The error was process state that only the START of the next pass ever cleared.**

    So one failed batch installed a banner above the stream for the life of the server, for every
    visitor rather than the one who pressed the button: reproduced by pressing Summarise, quitting
    the browser, and loading the front page in a brand-new profile, where `.distil-error` was
    already rendered with no dismiss and no timestamp. On the commonest first-run condition — BYOK,
    no model configured yet — that is a permanent error on the default screen.

    Cleared on the SERVER, because a dismiss the page kept to itself would come back on the reload.
    """
    api._DISTIL.update({"running": False, "failed": 2, "error": "RuntimeError: PN_MAIN_MODEL is not set"})
    assert client.get("/horizon/status").json()["distil"]["error"], "the fixture did not take"

    resp = client.post("/horizon/distil/dismiss")
    assert resp.status_code == 200, resp.text
    assert resp.json()["dismissed"] is True
    assert resp.json()["error"] == ""
    assert resp.json()["failed"] == 0

    # And it stays gone for the NEXT reader, which is the half that makes it a server-side clear.
    after = client.get("/horizon/status").json()["distil"]
    assert after["error"] == "" and after["failed"] == 0, after


def test_a_running_summary_pass_owns_its_error_fields(client):
    """A pass in flight is still accumulating failures, so clearing under it would hide a live one.
    There is nothing stale to dismiss while it is running, and 409 says which case this is."""
    api._DISTIL.update({"running": True, "failed": 1, "error": "one node failed"})
    try:
        assert client.post("/horizon/distil/dismiss").status_code == 409
        assert client.get("/horizon/status").json()["distil"]["error"] == "one node failed"
    finally:
        api._DISTIL.update({"running": False, "failed": 0, "error": ""})


def test_a_malformed_auto_distil_bound_refuses_startup(monkeypatch):
    """It used to come up fine and then KILL THE WORKER THREAD: `_env_int` raises `SystemExit`, a
    `BaseException`, which escaped the hook's `except Exception`, unwound `_run`, and ended the
    thread — and `threading` swallows `SystemExit` without a traceback, so captures simply stopped
    being parsed with no signal at all. Loud at boot beats silent at run time.

    Drives `_lifespan` directly rather than through `TestClient`, which wraps whatever a lifespan
    raises in an anyio `ExceptionGroup` and then reports the cancellation instead — asserting
    through that wrapper tests the wrapper.
    """
    import asyncio

    monkeypatch.setenv("PN_AUTO_DISTIL_MAX_PER_BATCH", "not-an-int")

    async def enter_and_leave() -> None:
        async with api._lifespan(api.app):
            pass

    with pytest.raises(SystemExit, match="PN_AUTO_DISTIL_MAX_PER_BATCH"):
        asyncio.run(enter_and_leave())


def test_the_idle_hook_can_never_end_the_worker(client, monkeypatch):
    """The other half of the same fix: whatever a policy hook raises, intake survives it. The
    docstring promises "anything it raises is logged and swallowed" — that has to hold for
    `BaseException` or it is worth less than no promise."""
    from penumbra import distill

    monkeypatch.setenv("PN_AUTO_DISTIL", "on")

    def explode(*args, **kwargs):
        raise SystemExit("a malformed PN_* value, as config raises it")

    monkeypatch.setattr(distill, "distil_pending", explode)
    first = client.post("/horizon", json={"urls": ["https://example.com/a"]}).json()["nodes"][0]
    _settle(client, first["id"])

    second = client.post("/horizon", json={"urls": ["https://example.com/b"]}).json()["nodes"][0]
    assert _settle(client, second["id"]) == "ready_undistilled", "the worker died on the hook"

def test_a_batch_upload_keeps_every_file_it_can_and_names_the_rest(client):
    """**Dropping a file the reader chose is the one thing a capture surface must never do
    quietly** — the handler's own comment, which the handler was not honouring.

    Dropping `good-a.md`, `bad.docx` and `good-b.md` together stored the first, raised on the
    second, and lost the THIRD with no record anywhere, under a 422 that named neither the file
    that survived nor the one that vanished. An independent review reproduced it: the horizon total
    went up by one and `good-b.md` was simply gone.

    Invariant 79 one layer up. A capture always lands; a batch lands every item it can and says
    which ones it could not.
    """
    reply = client.post(
        "/horizon/upload",
        files=[
            ("file", ("good-a.md", b"the first note", "text/markdown")),
            ("file", ("bad.docx", b"PK\x03\x04 not really", "application/octet-stream")),
            ("file", ("good-b.md", b"the third note, after the bad one", "text/markdown")),
        ],
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()
    stored = sorted(node["origin"] for node in body["nodes"])
    assert len(stored) == 2, f"a file after the unsupported one was dropped: {stored}"
    assert any("good-a" in origin for origin in stored)
    assert any("good-b" in origin for origin in stored), "the file AFTER the failure is the one lost"

    refused = body["refused"]
    assert [item["filename"] for item in refused] == ["bad.docx"]
    assert "docx" in refused[0]["error"]

    # And the whole batch failing is still a 422 - a request where nothing landed has no success to
    # report, and the reader would otherwise get an empty stream and a 200.
    only_bad = client.post(
        "/horizon/upload", files=[("file", ("x.docx", b"nope", "application/octet-stream"))]
    )
    assert only_bad.status_code == 422
    assert "docx" in only_bad.json()["detail"]

def test_the_listing_reports_the_ceiling_a_node_has_to_fit_under(client, monkeypatch):
    """**The two caps are six times apart and nothing said so.** 50MB of bytes may be uploaded
    (invariant 30); 8,000,000 characters may be assembled into a corpus (invariant 8). So a 30MB
    text file captures fine, promotes fine, and then makes the orbit it was promoted into
    unusable at the first question - invariant 8 failing loudly, a long way from the decision that
    caused it. Reporting the ceiling with the listing is what lets a row say so BEFORE the filing.

    Read through `config.max_corpus_chars()`, which is independent of `PenumbraConfig` for the same
    reason `max_upload_bytes()` is: this endpoint must answer on a server with no model configured.
    """
    body = client.get("/horizon").json()
    assert body["corpus_char_cap"] == 8_000_000

    monkeypatch.setenv("PN_MAX_CORPUS_CHARS", "1234")
    assert client.get("/horizon").json()["corpus_char_cap"] == 1234, "the env has to win, as everywhere"

    # And it does not need a model to say it.
    monkeypatch.delenv("PN_MAIN_MODEL", raising=False)
    assert client.get("/horizon").status_code == 200

# --- the three seams a one-line mutation broke while 894 tests stayed green ------------------------


def test_the_listing_actually_filters_by_the_query(client):
    """**The product's stated promise, and it had no HTTP-level test at all.**

    `horizon._search_clause` has six good unit tests and `?state=` / `?offset=` are driven over HTTP,
    which is exactly what made `?q=` look covered. It was not: a reviewer changed
    `query=q` to `query=None` in the handler and the whole suite still reported 894 passed, with
    every search in the UI silently returning the unfiltered listing. `grep -rn 'params={"q"' tests/`
    returned nothing.

    Driven through the ENDPOINT, because the endpoint is where the parameter was being dropped.
    """
    for text in ("a note about gardens", "a note about rivers", "a note about both gardens and rivers"):
        client.post("/horizon", json={"texts": [text]})

    def origins(**params):
        reply = client.get("/horizon", params=params)
        assert reply.status_code == 200, reply.text
        return sorted(node["origin"] for node in reply.json()["nodes"])

    everything = origins()
    assert len(everything) == 3

    gardens = origins(q="gardens")
    assert len(gardens) == 2, f"the query was not applied: {gardens}"
    assert all("garden" in o for o in gardens)

    # Two terms AND, and they may land in different columns - the case `_search_clause` exists for.
    both = origins(q="gardens rivers")
    assert len(both) == 1, both
    assert "both" in both[0]

    # `total` is the count of MATCHES, not of everything: the foot's "Older" button reads it, so a
    # search that filtered the page but not the count would page into rows that do not match.
    assert client.get("/horizon", params={"q": "gardens"}).json()["total"] == 2
    assert client.get("/horizon", params={"q": "zzzznothing"}).json()["nodes"] == []


def test_cancel_actually_reaches_a_running_summary_pass(client, monkeypatch):
    """**The one test that looked like it covered this asserted nothing.**

    `test_status_and_cancel_report_what_is_actually_happening` posts to `/horizon/cancel` and then
    checks `distil.running is False` — with nothing running. Vacuously true, and it would pass if
    the endpoint were a no-op. A reviewer changed `_DISTIL["cancel"] = True` to `False` and the
    suite stayed green while every remaining model call in a batch ran on after the reader pressed
    Stop. This is the action that spends their money.

    So: a REAL pass, in flight, stopped, and the stop observed in what the pass did rather than in
    what the status says afterwards.
    """
    from penumbra import distill

    seen: list[int] = []

    def slow(*args, **kwargs):
        seen.append(1)
        time.sleep(0.05)
        return Distillation(title="T", summary="S", tags=["x"])

    monkeypatch.setattr(distill, "distil_source", slow)
    for n in range(12):
        client.post("/horizon", json={"texts": [f"note {n}"]})

    started = client.post("/horizon/distil", json={"limit": 12}).json()
    assert started["started"] is True

    # Let it get going, then stop it.
    for _ in range(100):
        if seen:
            break
        time.sleep(0.02)
    assert seen, "the pass never started, so stopping it proves nothing"
    client.post("/horizon/cancel")

    for _ in range(200):
        if not client.get("/horizon/status").json()["distil"]["running"]:
            break
        time.sleep(0.02)
    stopped_after = len(seen)
    assert stopped_after < 12, (
        f"Stop did not reach the pass: {stopped_after} of 12 nodes were summarised anyway"
    )
    # And it stopped at a NODE BOUNDARY rather than mid-call: nothing is left claiming to be in
    # flight, and the untouched nodes are still pending rather than lost.
    assert client.get("/horizon/status").json()["distil"]["running"] is False
    assert client.get("/horizon").json()["undistilled"] == 12 - stopped_after


def test_a_second_summary_pass_is_refused_while_one_is_running(client, monkeypatch):
    """"One summary pass at a time" was asserted only in a comment. Removing the 409 left the suite
    green — and two concurrent passes both claim nodes, so the guard is what stops a reader paying
    twice for the same batch by pressing the button again."""
    from penumbra import distill

    monkeypatch.setattr(
        distill,
        "distil_source",
        lambda *a, **k: time.sleep(0.05) or Distillation(title="T", summary="S", tags=["x"]),
    )
    for n in range(8):
        client.post("/horizon", json={"texts": [f"slow note {n}"]})

    assert client.post("/horizon/distil", json={"limit": 8}).json()["started"] is True
    second = client.post("/horizon/distil", json={"limit": 8})
    assert second.status_code == 409, f"a second pass was allowed: {second.text}"

    client.post("/horizon/cancel")
    for _ in range(200):
        if not client.get("/horizon/status").json()["distil"]["running"]:
            break
        time.sleep(0.02)


def test_a_failed_node_is_counted_and_its_reason_reported(client, monkeypatch):
    """The `failed`/`error` channel added to stop the strip counting to 2/2 over a pass where
    nothing worked. No test had ever observed either field NON-ZERO, so the whole mechanism was
    pinned only by its own absence."""
    from penumbra import distill

    # **Patched BELOW `distil_source`, on purpose.** Replacing `distil_source` itself is what every
    # other distillation test does, and it bypasses the exact mechanism this test exists to observe:
    # the real `distil_source` is what catches the failure, calls `on_error` and returns `None`. A
    # stub that raises instead just propagates, and a stub that returns `None` never reports a
    # reason. `DistillNode.arun` is the seam the real code actually fails at.
    class Unreachable:
        async def arun(self, **kwargs):
            raise RuntimeError("the summariser is unreachable")

    monkeypatch.setattr(distill, "DistillNode", Unreachable)
    for n in range(2):
        client.post("/horizon", json={"texts": [f"doomed {n}"]})

    client.post("/horizon/distil", json={"limit": 2})
    for _ in range(200):
        distil = client.get("/horizon/status").json()["distil"]
        if not distil["running"]:
            break
        time.sleep(0.02)

    assert distil["failed"] == 2, f"failures were not counted: {distil}"
    assert "unreachable" in distil["error"], distil["error"]
    # `done` counts ATTEMPTS, so it moves too - and the nodes go back to pending rather than being
    # marked summarised.
    assert distil["done"] == 2
    assert client.get("/horizon").json()["undistilled"] == 2

def test_a_malformed_file_is_refused_not_a_500_and_takes_nothing_with_it(client):
    """**`PdfiumError` subclasses `RuntimeError`, not `ValueError`.**

    Both upload endpoints caught `(ValueError, OSError)`, so a malformed `.pdf` went straight past
    them: the request became a raw `500: Internal Server Error`, and every file already stored in
    that batch was never reported, because the response that would have named them never happened.
    A reviewer reproduced it with curl - `note.txt` + `broken.pdf` together, 500, and the reader
    told nothing about the file that worked. That is the exact failure the batch loop was written to
    fix, arriving through a different exception type, and it contradicts invariant 79.

    `intake.py`'s worker already catches `Exception` with the reason written down ("a parser may
    raise anything; the node records it"). The queue path had it; the two upload paths did not.
    """
    reply = client.post(
        "/horizon/upload",
        files=[
            ("file", ("note.txt", b"a real note that must survive", "text/plain")),
            ("file", ("broken.pdf", b"%PDF-1.7 not actually a pdf at all", "application/pdf")),
        ],
    )
    assert reply.status_code == 200, f"a malformed file 500'd the whole batch: {reply.text}"
    body = reply.json()
    assert [n["origin"] for n in body["nodes"]] == ["note.txt"], "the good file was lost"
    assert [r["filename"] for r in body["refused"]] == ["broken.pdf"]
    assert "PdfiumError" in body["refused"][0]["error"] or "pdf" in body["refused"][0]["error"].lower()

    # Alone, it is a 422 naming the file - never a 500.
    only_bad = client.post(
        "/horizon/upload", files=[("file", ("broken.pdf", b"%PDF-1.7 rubbish", "application/pdf"))]
    )
    assert only_bad.status_code == 422, only_bad.text


def test_the_orbit_upload_refuses_a_malformed_file_too(client):
    """The Tier 1 path had the identical catch and the identical 500 (`Could not add source:
    500: Internal Server Error`). One parser, two endpoints, one rule."""
    reply = client.post(
        "/orbits/mynb/sources/upload",
        files={"file": ("broken.pdf", b"%PDF-1.7 rubbish", "application/pdf")},
    )
    assert reply.status_code == 422, f"expected a named refusal, got {reply.status_code}"
    assert "broken.pdf" in reply.json()["detail"]


def test_a_membership_does_not_outlive_the_source_it_points_at(client):
    """**The one question a capture index has to answer is "where did this end up".**

    Promotion writes `(node_id, orbit_id, source_id)`. Removing that source from the orbit
    left the row behind — invariant 50 guarantees the survivors are never renumbered, so the id is
    simply gone — and `GET /horizon/{node_id}` went on reporting the node as filed there while the
    Horizon row went on saying "already in <orbit>". Re-promoting worked, so nothing was lost;
    the index was just wrong about the only thing it is for.
    """
    node = client.post("/horizon", json={"texts": ["something worth filing"]}).json()["nodes"][0]
    _settle(client, node["id"])

    promoted = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "reading", "create": True})
    assert promoted.status_code == 200
    filed = client.get(f"/horizon/{node['id']}").json()["orbits"]
    assert [(m["orbit_id"], m["source_id"]) for m in filed] == [("reading", "s1")]

    assert client.delete("/orbits/reading/sources/s1").status_code == 200
    assert client.get(f"/horizon/{node['id']}").json()["orbits"] == [], (
        "the node still claims to be filed in an orbit whose copy of it has been removed"
    )

    # And it can be filed again, which is what makes the stale row a lie rather than a record.
    again = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "reading", "create": True})
    assert again.status_code == 200
    assert [m["orbit_id"] for m in client.get(f"/horizon/{node['id']}").json()["orbits"]] == [
        "reading"
    ]


def test_an_unreadable_blocks_file_is_a_409_naming_the_right_file(client, tmp_path):
    """**Two endpoints read a node's text, and a corrupt file broke each in its own way.**

    `GET /horizon/{id}/source` let the exception escape as a bodyless `500 Internal Server Error`, so
    the page's error path had nothing to render — invariant 27's shape one tier down, missing its
    second arm, because `_node_or_404` covers the DB ROW and the text is a separate file
    (invariant 78).

    `POST /horizon/{id}/promote` was worse: it caught `ValidationError` broadly and blamed the
    ORBIT, telling the operator to "fix or remove by hand" an `orbits/<id>.json` that parses
    perfectly well. `promote_node` reads the node first and the orbit second, and both raise the
    same class — so the narrowing belongs at the call that knows which file it was reading.
    """
    from penumbra import horizon

    node = client.post("/horizon", json={"texts": ["something worth keeping"]}).json()["nodes"][0]
    _settle(client, node["id"])
    assert client.get(f"/horizon/{node['id']}/source").status_code == 200

    horizon.node_blocks_path(node["id"]).write_text('{"not": "a list of blocks"}', encoding="utf-8")

    read = client.get(f"/horizon/{node['id']}/source")
    assert read.status_code == 409, f"expected a 409, got {read.status_code}"
    assert node["id"] in read.json()["detail"] and "by hand" in read.json()["detail"]

    promoted = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "reading", "create": True})
    assert promoted.status_code == 409
    detail = promoted.json()["detail"]
    assert node["id"] in detail, f"the 409 does not name the node whose file is broken: {detail}"
    assert "orbits/" not in detail, (
        f"a broken NODE file was blamed on an orbit that parses fine, with advice to remove it: "
        f"{detail}"
    )


def test_a_membership_is_keyed_on_the_same_thing_the_orbit_file_is(client):
    """**One orbit on disk, two rows in the index, and the second promotion reused a source id.**

    `orbit.slug()` decides the FILENAME, so `"Foo Bar"` and `"Foo-Bar"` are one orbit — but
    memberships stored the raw id. Promote through the spaced form, remove the source through the
    file's form, and the row survived: the node went on claiming to be filed somewhere its copy had
    been removed from, and the next promotion then handed `s1` to a DIFFERENT node. Two rows, one
    source id, two different documents.

    Not reachable through the UI, which mints `nb-<uuid8>` (invariant 37), and fully reachable over
    HTTP by any token holder.
    """
    first = client.post("/horizon", json={"texts": ["the first thing"]}).json()["nodes"][0]
    second = client.post("/horizon", json={"texts": ["the second thing"]}).json()["nodes"][0]
    _settle(client, first["id"])
    _settle(client, second["id"])

    assert client.post(
        f"/horizon/{first['id']}/promote",
        json={"orbit_id": "Foo Bar", "create": True},
    ).status_code == 200
    filed = client.get(f"/horizon/{first['id']}").json()["orbits"]
    assert [m["orbit_id"] for m in filed] == ["Foo-Bar"], (
        f"the membership does not name the orbit the file is: {filed}"
    )

    # The SAME orbit, named the way its file is. Removing through it must clear the row.
    assert client.delete("/orbits/Foo-Bar/sources/s1").status_code == 200
    assert client.get(f"/horizon/{first['id']}").json()["orbits"] == [], (
        "a stale row survived because it was keyed on a spelling the file does not use"
    )

    # And the id it freed goes to the next promotion without two nodes claiming it.
    assert client.post(
        f"/horizon/{second['id']}/promote",
        json={"orbit_id": "Foo-Bar", "create": True},
    ).status_code == 200
    assert [m["orbit_id"] for m in client.get(f"/horizon/{second['id']}").json()["orbits"]] == ["Foo-Bar"]
    assert client.get(f"/horizon/{first['id']}").json()["orbits"] == [], (
        "the first node still claims a source id that now belongs to a different document"
    )


def test_one_unreadable_row_does_not_take_down_the_whole_listing(client):
    """**`GET /horizon` is the application's front page**, and a single unparseable row turned it into
    a bodyless 500 — so nothing rendered at all, not even the rows that were fine.

    `_FIELD_ADAPTERS`' own comment gives this exact reasoning ("one bad write making the whole
    listing unreadable"), and the validator it describes only guards `update_node`, which is the
    write side. Skipped and LOGGED, never silently dropped: the same "flag, never hide" shape
    `list_orbit_summaries` already uses for an unparseable orbit file.
    """
    import sqlite3

    from penumbra import horizon

    good = client.post("/horizon", json={"texts": ["a node that is fine"]}).json()["nodes"][0]
    bad = client.post("/horizon", json={"texts": ["a node about to be corrupted"]}).json()["nodes"][0]
    _settle(client, good["id"])
    _settle(client, bad["id"])
    assert client.get("/horizon").json()["total"] == 2

    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("UPDATE nodes SET tags = ? WHERE id = ?", ("{not json", bad["id"]))
        conn.commit()

    listing = client.get("/horizon")
    assert listing.status_code == 200, (
        f"one bad row took down the front page: {listing.status_code} {listing.text[:120]}"
    )
    ids = [n["id"] for n in listing.json()["nodes"]]
    assert good["id"] in ids, "the readable rows were lost with the unreadable one"
    assert bad["id"] not in ids, "an unparseable row was rendered anyway"


def test_an_unreadable_index_row_can_be_removed_and_stops_inflating_the_counts(client):
    """**Round eight made an unparseable row invisible; it stayed COUNTED and became immortal.**

    `list_nodes` skipped it so `GET /horizon` would stop 500ing — and `count_nodes` was a separate
    `COUNT(*)` over the same WHERE, so `total` went on including it. Measured live: `total 3, rows
    2`, `Load more` offered on a page that already held everything, and a real summary pass
    reporting `done 3 / total 4` — a number on the one action that spends the reader's money that
    it can never reach, which is invariant 60's rule.

    And every per-node endpoint answered `400 "invalid node id"` about an id that is perfectly
    valid — the same mis-blame fixed one endpoint over — INCLUDING `DELETE`, the only verb that
    could have cleared it. So the row could not be seen, could not be counted against, and could not
    be removed.
    """
    import sqlite3

    from penumbra import horizon

    good = client.post("/horizon", json={"texts": ["a node that is fine"]}).json()["nodes"][0]
    bad = client.post("/horizon", json={"texts": ["a node about to be corrupted"]}).json()["nodes"][0]
    _settle(client, good["id"])
    _settle(client, bad["id"])
    assert client.get("/horizon").json()["total"] == 2

    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("UPDATE nodes SET tags = ? WHERE id = ?", ("{not json", bad["id"]))
        conn.commit()

    listing = client.get("/horizon").json()
    assert len(listing["nodes"]) == 1, "the readable row was lost with the unreadable one"
    assert listing["total"] == 1, (
        f"the count still includes a row the listing cannot show: total={listing['total']}"
    )
    assert listing["undistilled"] == 1, (
        "the summary pass is priced from a count that includes a node it can never reach"
    )

    # Named, not blamed on the id - and pointing at the one verb that fixes it.
    read = client.get(f"/horizon/{bad['id']}")
    assert read.status_code == 409, f"expected 409, got {read.status_code}: {read.text[:120]}"
    assert "DELETE" in read.json()["detail"]

    # **And that verb works.** This is the recovery; routing it through the same gate made the row
    # immortal.
    gone = client.delete(f"/horizon/{bad['id']}")
    assert gone.status_code == 200 and gone.json()["removed"] is True
    assert client.get(f"/horizon/{bad['id']}").status_code == 404
    assert client.get("/horizon").json()["total"] == 1

    # A malformed id is still a 400, and an absent one still a 404 - invariant 27's distinction.
    assert client.delete("/horizon/not-a-minted-node-id").status_code == 400
    assert client.delete("/horizon/nd-0000000000000000").status_code == 404


def test_concurrent_promotions_of_one_node_do_not_blame_each_other(client):
    """**Eight of ten concurrent promotions answered 400, blaming a source their own sibling had
    just created.**

    `promote_node` read this node's prior membership BEFORE `mutate_orbit` took the lock. Under
    concurrency that snapshot is stale: a sibling appends the source, this call's `append_sources`
    dedupes by origin and appends nothing, the idempotent branch is skipped because `prior` is still
    `None`, and it falls through to "the orbit already holds a DIFFERENT source with this
    origin". Invariant 34 names the fault exactly — a stale snapshot and interleaved critical
    sections are two distinct problems, and the lock alone does not fix the first.

    Reachable by two tabs or any API client; the UI disables the picker per row.
    """
    from concurrent.futures import ThreadPoolExecutor

    node = client.post("/horizon", json={"texts": ["one node, many eager promoters"]}).json()["nodes"][0]
    _settle(client, node["id"])

    def promote(_: int):
        return client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "racey", "create": True})

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(promote, range(10)))

    codes = sorted(r.status_code for r in results)
    assert set(codes) == {200}, (
        f"concurrent promotions of ONE node into ONE orbit must all be idempotent, got {codes}: "
        f"{[r.json().get('detail') for r in results if r.status_code != 200][:2]}"
    )
    # One source, one membership, every caller told the same id.
    ids = {r.json()["membership"]["source_id"] for r in results}
    assert len(ids) == 1, f"the same node landed under {len(ids)} different source ids: {ids}"
    assert len(client.get("/orbits/racey").json()["sources"]) == 1
    assert len(client.get(f"/horizon/{node['id']}").json()["orbits"]) == 1


def test_a_source_another_route_added_under_the_same_origin_is_not_shadowed(tmp_path):
    """**The data-loss bug the content comparison has to keep closed.**

    `append_sources` dedupes by ORIGIN, so "appended nothing" does not mean "this node is already
    here". Matching on origin alone once recorded a membership pointing at somebody else's source,
    so the node's own text never reached the orbit and `promote_node` returned success.

    Two NODES cannot collide this way — a URL is one node id, and every other origin has its text
    folded into the id — which is why this is driven through the library rather than over HTTP. (It
    was reachable while a filename hashed to one node whatever the file contained; see
    `test_two_uploaded_files_with_the_same_name_are_two_nodes`.) The reachable collision
    is between a node and a source the orbit got by another route: `cli.py --source`, or
    `POST /orbits/{id}/sources`, on a URL whose content has changed since.

    It was refused loudly for a while, which was right about shadowing and wrong about the outcome:
    nothing in the product renames a node or a source, so the node became permanently unfileable.
    Both land now under distinct display origins, which is neither silent nor shadowing — the
    property under test is that each source keeps its OWN text and its own membership.
    """
    from penumbra import horizon
    from penumbra.orbit import load_orbit, mutate_orbit
    from penumbra.schema import Source, SourceBlock

    base = tmp_path / "horizon"
    books = tmp_path / "orbits"
    node = horizon.add_node(
        Source(
            id="s0",
            kind="web",
            origin="https://example.com/a",
            blocks=[SourceBlock(locator="whole", text="what the node captured")],
        ),
        base_dir=base,
    )
    # The orbit already holds that origin, with DIFFERENT text, from another route.
    mutate_orbit(
        "collide",
        lambda nb: nb.sources.append(
            Source(
                id="s1",
                kind="web",
                origin="https://example.com/a",
                blocks=[SourceBlock(locator="whole", text="what somebody else captured")],
            )
        ),
        base_dir=books,
        create=True,
    )

    membership = horizon.promote_node(node.id, "collide", base_dir=base, orbits_dir=books)
    assert membership.source_id != "s1", (
        "the membership points at a source that is not this node's text — the data-loss bug"
    )
    sources = {s.id: s for s in load_orbit("collide", base_dir=books).sources}
    assert len(sources) == 2, "the other route's source must survive untouched"
    assert sources["s1"].blocks[0].text == "what somebody else captured"
    assert sources[membership.source_id].blocks[0].text == "what the node captured"
    # Tellable apart on screen, which is what makes this not shadowing.
    assert sources["s1"].origin != sources[membership.source_id].origin
    assert sources[membership.source_id].origin.startswith("https://example.com/a")


def test_re_promoting_a_node_whose_text_changed_is_still_idempotent(client):
    """**A URL node keeps its id when it is re-fetched.** `add_pending_node` derives the id from the
    origin ALONE, so re-capturing a page whose content has changed updates the blocks under the same
    node. The content comparison cannot recognise it after that — which is why the membership row is
    still consulted, and why deleting it would be wrong even though the comparison covers the common
    case.
    """
    from penumbra import horizon
    from penumbra.schema import Source, SourceBlock

    node = client.post("/horizon", json={"texts": ["the original text"]}).json()["nodes"][0]
    _settle(client, node["id"])
    promoted = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "changed", "create": True})
    assert promoted.status_code == 200
    source_id = promoted.json()["membership"]["source_id"]

    # The node's stored text changes under the same id, as a re-fetch does.
    horizon.store_blocks(
        node["id"],
        Source(
            id=node["id"],
            kind="text",
            origin=node["origin"],
            blocks=[SourceBlock(locator="whole", text="the page says something else now")],
        ),
    )

    again = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "changed", "create": True})
    assert again.status_code == 200, (
        f"re-promoting a node whose text changed was refused: {again.json().get('detail')}"
    )
    assert again.json()["membership"]["source_id"] == source_id, "it was filed twice"
    assert len(client.get("/orbits/changed").json()["sources"]) == 1


def test_a_promotion_racing_its_own_sibling_adopts_the_source_instead_of_refusing(tmp_path):
    """**The window the content comparison exists for, made deterministic.**

    `promote_node` writes the orbit under a `flock` and the membership row into SQLite
    afterwards — they cannot be one transaction, which is what the compensating write below them is
    about. So there is a window where the source EXISTS and no row records it, and a sibling
    entering the lock in that window sees an origin collision with no membership to explain it.
    Live, ten concurrent promotions of one node produced eight 400s blaming a source their own
    siblings had just created.

    Reading the membership inside the lock closes most of the window; the content comparison closes
    the rest, and only this reproduces it deterministically — the row is deleted to stand in for
    "not written yet", which is exactly what the racing sibling sees.
    """
    from penumbra import horizon
    from penumbra.schema import Source, SourceBlock

    base = tmp_path / "horizon"
    books = tmp_path / "orbits"
    node = horizon.add_node(
        Source(
            id="s0",
            kind="web",
            origin="https://example.com/racing",
            blocks=[SourceBlock(locator="whole", text="one node, two eager promoters")],
        ),
        base_dir=base,
    )
    first = horizon.promote_node(node.id, "racing", base_dir=base, orbits_dir=books)

    # The source is in the orbit; the row that says whose it is has not landed yet.
    horizon.forget_membership("racing", first.source_id, base_dir=base)

    second = horizon.promote_node(node.id, "racing", base_dir=base, orbits_dir=books)
    assert second.source_id == first.source_id, (
        "a promotion racing its own sibling was refused, or filed the node twice"
    )
    assert len(horizon.nodes_in_orbit("racing", base_dir=base)) == 1


def test_two_files_with_the_same_name_can_both_be_filed(client):
    """**Round eleven landed both captures and left one of them unfileable.**

    Fixing `node_id_for` made two different `notes.txt` two nodes, which is right — and promoting
    the second into an orbit that already held the first was then a hard refusal with no way out,
    because nothing in the product can rename a node or a source. Invariant 79 gets the capture to
    land; invariant 78's promotion was a dead end one step later. Two `notes.txt` from two folders
    is an ordinary thing to drop on a horizon.
    """
    resp = client.post(
        "/horizon/upload",
        files=[
            ("file", ("notes.txt", b"the first file", "text/plain")),
            ("file", ("notes.txt", b"a different file", "text/plain")),
        ],
    )
    first, second = [n["id"] for n in resp.json()["nodes"]]

    a = client.post(f"/horizon/{first}/promote", json={"orbit_id": "both", "create": True})
    b = client.post(f"/horizon/{second}/promote", json={"orbit_id": "both", "create": True})
    assert a.status_code == 200 and b.status_code == 200, (a.text, b.text)

    sources = client.get("/orbits/both").json()["sources"]
    assert len(sources) == 2, sources
    assert {s["id"] for s in sources} == {"s1", "s2"}
    # Distinct NAMES, so the reader can tell them apart — the whole reason refusing felt necessary.
    origins = sorted(s["origin"] for s in sources)
    assert origins == ["notes (2).txt", "notes.txt"], origins
    # ...and each carries its OWN bytes, which is the property the refusal was protecting.
    texts = {
        s["id"]: "".join(
            b["text"]
            for b in client.get(f"/orbits/both/sources/{s['id']}").json()["blocks"]
        )
        for s in sources
    }
    assert sorted(texts.values()) == ["a different file", "the first file"]


def test_the_orbit_listing_carries_the_key_a_membership_is_written_with(client):
    """**The UI reported a live orbit as deleted.**

    `promote_node` keys `NodeMembership.orbit_id` on `slug(orbit_id)` — deliberately, because
    the slug is what identifies the orbit FILE. The client built its label map from
    `GET /orbits`, which carried the id stored INSIDE the file and no slug, so for any orbit
    whose id differs from its slug the two ends could never meet: the node rendered "In a deleted
    orbit" while that orbit sat live in the same row's own picker. Reproduced in a browser
    with `台灣研究筆記` (slug `nb-<hash>`, invariant 10) and with `Foo Bar` (slug `Foo-Bar`).

    Not reachable from the web UI alone — invariant 37 mints `nb-<uuid8>`, whose slug is itself —
    and reachable from the first `penumbra ask --orbit "reading list"` or any HTTP caller.
    """
    from penumbra import horizon
    from penumbra.orbit import slug

    node = client.post("/horizon", json={"texts": ["something worth filing"]}).json()["nodes"][0]
    _settle(client, node["id"])

    for orbit_id in ("Foo Bar", "台灣研究筆記", "plain"):
        filed = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": orbit_id, "create": True})
        assert filed.status_code == 200, filed.text

    listing = {n["id"]: n for n in client.get("/orbits").json()["orbits"]}
    by_slug = {n["slug"]: n["id"] for n in listing.values()}
    for membership in horizon.memberships_for(node["id"]):
        assert membership.orbit_id in by_slug, (
            f"a membership names {membership.orbit_id!r}, which nothing in GET /orbits "
            f"matches — the client can only render this as 'a deleted orbit'. "
            f"Listing slugs: {sorted(by_slug)}"
        )

    # ...and the field says what it claims: the slug of the id beside it.
    for orbit in listing.values():
        assert orbit["slug"] == slug(orbit["id"])
    # The case that makes this necessary: an id that is NOT its own slug.
    assert any(n["slug"] != n["id"] for n in listing.values()), "the fixture stopped covering it"


def test_a_orbit_can_be_deleted_and_its_nodes_survive(client, tmp_path):
    """**An orbit could not be deleted from anywhere**: no endpoint, no CLI verb, no control, so
    once one existed it was permanent and an accidental empty one sat in the facet rail as
    "Untitled orbit · 0" forever. The product ships Forget for a node and ✕ for a source, and
    `app.js` even carried the string "a deleted orbit" for a state nothing could produce.

    The nodes survive, which is the half that makes deleting safe to offer: promotion COPIES into a
    orbit (invariant 78), so a capture outlives any orbit it was filed into.
    """
    from penumbra import horizon
    from penumbra.orbit import orbit_path

    node = client.post("/horizon", json={"texts": ["worth keeping past the orbit"]}).json()["nodes"][0]
    _settle(client, node["id"])
    assert client.post(
        f"/horizon/{node['id']}/promote",
        json={"orbit_id": "doomed", "create": True},
    ).status_code == 200
    assert orbit_path("doomed").exists()
    assert len(horizon.memberships_for(node["id"])) == 1

    resp = client.delete("/orbits/doomed")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] is True
    assert resp.json()["memberships_dropped"] == 1

    assert not orbit_path("doomed").exists()
    assert "doomed" not in [n["id"] for n in client.get("/orbits").json()["orbits"]]
    # The index no longer claims the node is filed somewhere that is gone — the one question a
    # capture index has to answer is "where did this end up".
    assert horizon.memberships_for(node["id"]) == []
    # ...and the node itself is untouched, text and all.
    assert client.get(f"/horizon/{node['id']}").status_code == 200
    blocks = client.get(f"/horizon/{node['id']}/source").json()["source"]["blocks"]
    assert "".join(b["text"] for b in blocks) == "worth keeping past the orbit"

    # Deleting it again is a 404, not a second success.
    assert client.delete("/orbits/doomed").status_code == 404


def test_deleting_a_orbit_takes_its_audio_with_it(client):
    """One file per orbit is what made retention a non-question (invariant 42). Leaving it behind
    would make it one, and `find_audio` would then serve an episode for an orbit that is gone."""
    from penumbra.orbit import audio_path

    client.post("/orbits/withaudio/sources", json={"sources": ["https://example.com/a"]})
    episode = audio_path("withaudio", suffix=".mp3")
    episode.parent.mkdir(parents=True, exist_ok=True)
    episode.write_bytes(b"not really an mp3")

    assert client.delete("/orbits/withaudio").status_code == 200
    assert not episode.exists(), "the episode outlived the orbit it belongs to"


def test_a_orbit_with_a_run_in_flight_refuses_to_be_deleted(client):
    """Deleting the file under a running worker leaves it writing an answer into an orbit that no
    longer exists — and `mutate_orbit` would helpfully re-create it, an orbit resurrected by
    its own deletion. The Stop the reader already has is the one that ends the run."""
    import types

    client.post("/orbits/busy/sources", json={"sources": ["https://example.com/a"]})
    api._ACTIVE_RUNS["busy"] = types.SimpleNamespace(process=None)
    try:
        resp = client.delete("/orbits/busy")
        assert resp.status_code == 409, resp.text
        assert "stop it first" in resp.json()["detail"]
    finally:
        api._ACTIVE_RUNS.pop("busy", None)
    # Still there, which is the point of refusing.
    assert client.get("/orbits/busy").status_code == 200
    assert client.delete("/orbits/busy").status_code == 200


class _NoContentLength:
    """A request with no `Content-Length`, i.e. chunked transfer encoding."""

    headers: ClassVar = {}

    async def form(self):
        raise AssertionError(
            "form() must not be called when Content-Length is missing — invariant 30's whole point "
            "is that there is no safe way to bound an unknown-length body before reading it"
        )


def test_the_horizon_upload_refuses_a_chunked_body_with_411():
    """Invariant 30, on the product's DEFAULT drop target — and nothing pinned it.

    `test_api.py` pins the same guard for `/orbits/{id}/sources/upload`; deleting it from
    `/horizon/upload` left all 999 tests green, found by an independent review sending a real chunked
    multipart POST over a raw socket. `TestClient` cannot see this: httpx always sends a
    `Content-Length`, and the in-loop 413 would answer anyway — AFTER the whole body had been
    spooled, which is the thing this guard exists to prevent.
    """
    with pytest.raises(api.HTTPException) as exc_info:
        asyncio.run(api.upload_into_horizon(_NoContentLength()))
    assert exc_info.value.status_code == 411
    assert "Content-Length" in exc_info.value.detail


class _DeclaredOversized:
    """A request whose declared size already exceeds the cap — refused before the body is parsed."""

    headers: ClassVar = {"content-length": str(10**12)}

    async def form(self):
        raise AssertionError("form() must not be called once Content-Length has cleared the cap")


def test_the_horizon_upload_refuses_an_oversized_declaration_before_parsing():
    with pytest.raises(api.HTTPException) as exc_info:
        asyncio.run(api.upload_into_horizon(_DeclaredOversized()))
    assert exc_info.value.status_code == 413


def test_stop_reaches_the_summary_batch_that_has_not_started_yet(client, monkeypatch):
    """**"Stop means stop, not stop-one-of-the-two"** — `cancel_horizon_intake`'s own comment, and it
    reached only the batch that was already running.

    `cancel_pending` bumps `_cancel_generation` for exactly this reason. But
    `_auto_distil_after_intake` read `queue.cancel_generation` at ENTRY, i.e. after the bump, so its
    own comparison could never be true for a batch that began afterwards — and then it wrote
    `cancel: False`, wiping the flag the reader had just set. A paid batch started milliseconds
    later at the next idle with `should_stop()` already false (invariants 47 and 80).
    """
    from penumbra import distill

    started: list[dict] = []

    def fake_pass(*, limit, base_dir=None, language="", should_stop=None, on_node=None, on_error=None):
        started.append({"limit": limit, "stopped_at_entry": bool(should_stop and should_stop())})

    monkeypatch.setattr(distill, "distil_pending", fake_pass)
    monkeypatch.setattr(api, "_configure_in_process_model", lambda: None)
    monkeypatch.setenv("PN_AUTO_DISTIL", "on")
    api._DISTIL.update({"running": False, "cancel": False, "done": 0, "total": 0, "failed": 0})

    client.post("/horizon", json={"texts": ["something worth summarising"]})
    node = client.get("/horizon").json()["nodes"][0]
    _settle(client, node["id"])
    started.clear()

    assert client.post("/horizon/cancel").status_code == 200
    assert api._DISTIL["cancel"] is True, "Stop did not set the flag"

    # The batch that the next idle would start must not run at all.
    api._auto_distil_after_intake()
    assert started == [], f"a paid batch started after Stop: {started}"
    assert api._DISTIL["cancel"] is True, "the batch wiped the flag the reader set"

    # ...and a NEW capture is the reader asking for it again.
    client.post("/horizon", json={"texts": ["a second thing, deliberately"]})
    assert api._DISTIL["cancel"] is False, "throwing something new in must resume the pass"


def test_promoting_into_a_deleted_orbit_does_not_bring_it_back(client):
    """**A STALE PICKER OPTION was enough — no race required.**

    The Horizon's "File into…" `<select>` is built from the orbit list fetched when the page
    rendered, so an option can name an orbit that has since been deleted. Promoting through one
    re-created it: same handle, same slug, holding one source and none of its title, sources, notes,
    turns or overview, back in the facet rail. `DELETE /orbits/{id}` refuses while a run is in
    flight for exactly this reason, and round fourteen closed the same class at three write sites
    and left this one — "fixing the INSTANCE rather than the CLASS", which `_require_sources`' own
    docstring names.

    `create` is what the CALLER meant: the UI mints a fresh `nb-<uuid8>` when the reader picks "a
    new orbit" (invariant 37) and sends an existing id otherwise.
    """
    node = client.post("/horizon", json={"texts": ["worth filing"]}).json()["nodes"][0]
    _settle(client, node["id"])

    first = client.post(
        f"/horizon/{node['id']}/promote",
        json={"orbit_id": "nb-abc12345", "create": True},
    )
    assert first.status_code == 200, first.text
    assert client.delete("/orbits/nb-abc12345").status_code == 200

    stale = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "nb-abc12345"})
    assert stale.status_code == 404, (
        f"a deleted orbit came back through a stale picker option: {stale.status_code}"
    )
    assert "nb-abc12345" not in [n["id"] for n in client.get("/orbits").json()["orbits"]]


def test_a_note_cannot_resurrect_a_orbit_deleted_while_it_was_in_flight(client, monkeypatch):
    """The last write site still passing a constant. Lazy creation stays — an orbit really can
    start life as a note, which this endpoint's docstring promises — but an orbit deleted while
    the write was in flight must not be re-created by it."""
    import threading

    from penumbra.orbit import orbit_path

    client.post("/orbits/noted/sources", json={"texts": ["a source"]})
    writing, release = threading.Event(), threading.Event()
    real = api.add_note

    def slow(nb, text):
        writing.set()
        release.wait(10)
        return real(nb, text)

    monkeypatch.setattr(api, "add_note", slow)
    result = {}
    worker = threading.Thread(
        target=lambda: result.update(
            resp=client.post("/orbits/noted/notes", json={"text": "a thought"})
        ),
        daemon=True,
    )
    worker.start()
    assert writing.wait(10)
    assert client.delete("/orbits/noted").status_code == 200
    release.set()
    worker.join(10)

    #: The orbit stays gone. The racing write's own status is deliberately NOT asserted: whoever
    #: takes the per-orbit lock first legitimately wins, so a 200 here means the note landed
    #: before the delete and a 404 means after. What must never happen is the file coming BACK.
    assert not orbit_path("noted").exists(), "a note resurrected a deleted orbit"
    assert result["resp"].status_code in (200, 404, 409), result["resp"].status_code

    # ...and a note can still START an orbit, which is the behaviour this endpoint promises.
    assert client.post("/orbits/fresh-by-note/notes", json={"text": "hello"}).status_code == 200
    assert orbit_path("fresh-by-note").exists()


def test_a_promotion_says_whether_it_added_a_source_so_undo_never_removes_an_old_one(client):
    """Promotion is idempotent: filing a node where it already is returns the source it already has.
    The map's Undo deletes the returned source, so it must know whether this call created it."""
    node = client.post("/horizon", json={"texts": ["file me twice"]}).json()["nodes"][0]
    first = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "twice", "create": True}).json()
    again = client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "twice", "create": False}).json()
    assert first["appended"] is True
    assert again["appended"] is False
    assert again["membership"]["source_id"] == first["membership"]["source_id"]


def test_a_source_added_inside_an_orbit_lands_in_the_horizon_filed_there(client):
    """Everything crosses the Horizon, including a paste made from inside an orbit: it becomes a
    node filed into that orbit, pointing at the source the orbit already holds, so a summary can
    read it and the map draws it like any capture."""
    orbit = client.post("/orbits/inside/sources", json={"texts": ["typed straight into the orbit"]}).json()
    (source,) = orbit["sources"]
    nodes = client.get("/horizon").json()["nodes"]
    (node,) = [n for n in nodes if "typed straight" in (n.get("origin") or "")]
    assert node["state"] == "ready_undistilled", "recording it must not start a summary (invariant 80)"
    (membership,) = client.get(f"/horizon/{node['id']}").json()["orbits"]
    assert membership["orbit_id"] == "inside" and membership["source_id"] == source["id"]
    # The orbit is untouched: still one source, same id.
    assert [s["id"] for s in client.get("/orbits/inside").json()["sources"]] == [source["id"]]


def test_recording_orbit_sources_is_idempotent_and_is_the_backfill(client):
    from penumbra import horizon
    from penumbra import orbit as ob

    client.post("/orbits/older/sources", json={"texts": ["written before the Horizon knew"]})
    before = len(client.get("/horizon").json()["nodes"])
    loaded = ob.load_orbit("older")
    assert horizon.record_orbit_sources(loaded.id, loaded.sources) == 0, "already recorded"
    assert len(client.get("/horizon").json()["nodes"]) == before
    assert api._backfill_horizon() == 0


def test_moving_a_capture_takes_it_out_of_the_orbit_it_left(client):
    """Dragging a moon to another planet is a move: one orbit gains it, the other loses it."""
    node = client.post("/horizon", json={"texts": ["move me across"]}).json()["nodes"][0]
    client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "from-here", "create": True})
    client.post("/orbits/to-there/sources", json={"texts": ["something already there"]})
    moved = client.post(
        f"/horizon/{node['id']}/move", json={"from_orbit": "from-here", "to_orbit": "to-there"}
    ).json()
    assert moved["appended"] is True and moved["removed"]
    assert client.get("/orbits/from-here").json()["sources"] == []
    assert len(client.get("/orbits/to-there").json()["sources"]) == 2
    orbits = [m["orbit_id"] for m in client.get(f"/horizon/{node['id']}").json()["orbits"]]
    assert orbits == ["to-there"]


def test_a_move_that_would_orphan_citations_asks_first(client):
    from penumbra import orbit as ob
    from penumbra.schema import Answer, ChatTurn, Citation

    node = client.post("/horizon", json={"texts": ["cited text"]}).json()["nodes"][0]
    sid = client.post(
        f"/horizon/{node['id']}/promote", json={"orbit_id": "cited", "create": True}
    ).json()["membership"]["source_id"]
    client.post("/orbits/elsewhere/sources", json={"texts": ["x"]})
    ob.mutate_orbit("cited", lambda o: o.turns.append(ChatTurn(question="q", answer=Answer(
        text="a", citations=[Citation(source_id=sid, locator="whole", quote="cited text")]))), create=False)
    body = {"from_orbit": "cited", "to_orbit": "elsewhere"}
    refused = client.post(f"/horizon/{node['id']}/move", json=body)
    assert refused.status_code == 409 and refused.json()["cited"] == 1
    assert len(client.get("/orbits/cited").json()["sources"]) == 1, "nothing moved before the answer"
    done = client.post(f"/horizon/{node['id']}/move", json={**body, "confirm": True})
    assert done.status_code == 200 and done.json()["removed"] == sid


def test_the_listing_says_which_orbits_each_capture_is_in(client):
    node = client.post("/horizon", json={"texts": ["listed with its orbit"]}).json()["nodes"][0]
    client.post(f"/horizon/{node['id']}/promote", json={"orbit_id": "shown", "create": True})
    (listed,) = [n for n in client.get("/horizon").json()["nodes"] if n["id"] == node["id"]]
    assert [m["orbit_id"] for m in listed["orbits"]] == ["shown"]
    assert listed["orbits"][0]["promoted_at"] > 0
