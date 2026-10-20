"""**A capture's id changes once, and a clear restarts the numbering**, driven in a real WebKit.

A capture is `nd-<hash>` until its text is a memory item, then the item's `m<n>`, and a clear
starts a new store numbered from `m1` again. These check the page's half: what it holds is re-keyed
when a response names a capture by its new id, and a page holding ids from before a clear never
sends one (412, and the page reloads). Their own server, because one of them clears it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from tests.test_browser import REPO, TOKEN, _call, _free_port


@pytest.fixture(scope="module")
def browser():
    """WebKit, as `test_browser.py` launches it: a missing browser fails rather than skips."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.fail("playwright is a dev dependency: run `uv sync`")
    with sync_playwright() as play:
        try:
            engine = play.webkit.launch()
        except Exception as exc:  # noqa: BLE001 - the message says what to install
            pytest.fail(f"Playwright's WebKit is missing: run `uv run playwright install webkit` ({exc})")
        yield engine
        engine.close()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    pytest.importorskip("fastapi")  # the `api` extra, which CI installs
    home = tmp_path_factory.mktemp("browser-ids-server")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "penumbra.cli", "serve", "--port", str(port)],
        cwd=home, env={**os.environ, "PN_API_TOKEN": TOKEN, "PYTHONPATH": str(REPO)},
        stdout=(home / "serve.log").open("w"), stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(150):
            try:
                _call(base, "GET", "/orbits")
                break
            except OSError:
                time.sleep(0.2)
        else:
            tail = (home / "serve.log").read_text(errors="replace")[-2000:]
            raise RuntimeError(f"the server did not start; the end of its log:\n{tail}")
        _call(base, "POST", "/horizon", {"texts": ["A first note, kept before anything is cleared."]})
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _open(browser, server):
    view = browser.new_page(viewport={"width": 1440, "height": 900}, locale="en-US")
    view.goto(f"{server}/#token={TOKEN}")
    view.wait_for_function("horizonEpoch !== null", timeout=30000)
    return view


def _reloaded(view, timeout: float = 30.0) -> None:
    """Wait until the page has reloaded (the marker set before is gone) and read its epoch again.
    Polled, because an evaluate that lands mid-navigation raises rather than waits."""
    from playwright.sync_api import Error as PlaywrightError

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            state = view.evaluate("[window.__beforeReload === undefined, horizonEpoch !== null]")
            if state == [True, True]:
                return
            if state[0]:
                # Reloaded, but its first listing may have been held: poll as the page would.
                view.evaluate("() => { void api('/horizon/status'); }")
        except PlaywrightError:
            pass   # mid-navigation
        time.sleep(0.1)
    raise AssertionError("the page did not reload")


def _hold_requests(view, allowed: str) -> None:
    """Hold every request the page makes by itself, except the one under test (`allowed` in its
    URL): any of them would meet the new epoch first and reload the page. Documents, scripts and
    styles still load, so the reload itself can happen."""
    def decide(route):
        request = route.request
        if request.resource_type in ("fetch", "xhr") and allowed not in request.url:
            route.abort()
        else:
            route.continue_()

    view.route("**/*", decide)


def test_a_page_holding_a_temporary_id_holds_the_item_id_once_a_response_names_it(browser, server):
    """A card opened while its capture was read is held under the temporary id; the first response
    naming the capture by its item id re-keys every holder, so the card stays open and the map's
    focus stays on it."""
    node = _call(server, "GET", "/horizon?limit=5")["nodes"][0]
    assert node["id"].startswith("m") and node["former_id"].startswith("nd-")
    view = _open(browser, server)
    try:
        held = view.evaluate(f"""async () => {{
            const temp = {json.dumps(node["former_id"])};
            horizonState.open.add(temp);
            starMap.focus = {{kind: "capture", id: temp}};
            capturesHeld.byId.set(temp, {{node: {{}}}});
            graphState.capture = temp;
            const row = document.createElement("li");
            row.dataset.nodeId = temp;
            document.body.appendChild(row);
            const got = await api(`/horizon/${{encodeURIComponent(temp)}}`);
            return {{id: got.node.id, open: [...horizonState.open], focus: starMap.focus.id,
                     card: [...capturesHeld.byId.keys()], graph: graphState.capture,
                     row: row.dataset.nodeId}};
        }}""")
        now = node["id"]
        assert held == {"id": now, "open": [now], "focus": now, "card": [now], "graph": now, "row": now}
    finally:
        view.close()


def test_a_page_from_before_a_clear_never_sends_an_old_id(browser, server):
    """Two windows; one clears; the other, idle, renames the capture it still shows as `m1`. A new
    capture is `m1` now, so the request is refused (412) before it runs, the page reloads, and the
    new capture keeps its title."""
    stale = _open(browser, server)
    try:
        old = _call(server, "GET", "/horizon?limit=5")["nodes"][0]["id"]
        epoch = stale.evaluate("horizonEpoch")
        _hold_requests(stale, f"/horizon/{old}/title")
        stale.wait_for_load_state("networkidle")   # a read sent before the hold would still land
        assert _call(server, "POST", "/data/clear", {"confirm": "clear everything"})["captures"] >= 1
        made = _call(server, "POST", "/horizon", {"texts": ["A new note, made after the clear."]})
        fresh = made["nodes"][0]
        assert fresh["id"] == old, "the numbering restarts after a clear, which is what this guards"
        assert _call(server, "GET", "/horizon/status")["epoch"] != epoch
        stale.evaluate("window.__beforeReload = true")
        stale.evaluate(f"""() => {{ void api(`/horizon/{old}/title`, {{method: "PUT",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{title: "Renamed by a stale page"}})}});
        }}""")
        stale.unroute("**/*")
        _reloaded(stale)
        assert stale.evaluate("horizonEpoch") != epoch
        after = _call(server, "GET", f"/horizon/{fresh['id']}")["node"]
        assert after["title"] != "Renamed by a stale page"
        assert "title" not in after["edited"]
    finally:
        stale.close()


def test_a_poll_that_sees_a_new_epoch_reloads_the_page(browser, server):
    """The passive half: a page that polls after a clear reloads without waiting for a write."""
    from playwright.sync_api import Error as PlaywrightError

    view = _open(browser, server)
    try:
        view.evaluate("window.__beforeReload = true")
        _call(server, "POST", "/data/clear", {"confirm": "clear everything"})
        try:
            view.evaluate("() => { void api('/horizon/status'); }")
        except PlaywrightError:
            pass   # the page's own poll already saw the new epoch and is reloading: the same path
        _reloaded(view)
        assert view.evaluate("horizonEpoch") == _call(server, "GET", "/horizon/status")["epoch"]
    finally:
        view.close()


def test_a_stale_move_reloads_the_page_and_asks_nothing(browser, server):
    """A refused move must not reach the move's own 409 branch, which would ask to confirm leaving
    citations unverified for what may now be a different capture."""
    view = _open(browser, server)
    try:
        node = _call(server, "POST", "/horizon", {"texts": ["a note to move"]})["nodes"][0]
        _call(server, "POST", f"/horizon/{node['id']}/promote", {"orbit_id": "a", "create": True})
        _hold_requests(view, f"/horizon/{node['id']}/move")
        view.wait_for_load_state("networkidle")   # a read sent before the hold would still land
        _call(server, "POST", "/data/clear", {"confirm": "clear everything"})
        view.evaluate(f"""() => {{ window.__beforeReload = true;
            window.confirmAction = async () => {{ sessionStorage.setItem("asked", "1"); return false; }};
            const real = window.notify;
            window.notify = (message, ...rest) => {{
              if (/412|cleared since/.test(String(message))) sessionStorage.setItem("told", String(message));
              return real(message, ...rest);
            }};
            void moveCapture({{id: {json.dumps(node["id"])}, orbit: "a"}},
                             {{id: "b", slug: "b", title: "B"}});
        }}""")
        view.unroute("**/*")
        _reloaded(view)
        said = view.evaluate("[sessionStorage.getItem('asked'), sessionStorage.getItem('told')]")
        assert said == [None, None], "the refused move asked to confirm, or showed the refusal"
    finally:
        view.close()


def test_a_page_that_missed_a_clear_still_sends_a_new_capture(browser, server):
    """Only a request naming a capture carries the epoch, so text typed into a page that has not
    noticed a clear is sent and kept, not lost to a reload."""
    view = _open(browser, server)
    try:
        epoch = view.evaluate("horizonEpoch")
        # The page's own reads (any could carry the new epoch and reload it first) are held; the
        # capture itself goes through untouched.
        view.route("**/*", lambda route: route.abort() if (
            route.request.resource_type in ("fetch", "xhr") and route.request.method == "GET")
            else route.fallback())
        view.wait_for_load_state("networkidle")   # a read sent before the hold would still land
        _call(server, "POST", "/data/clear", {"confirm": "clear everything"})
        got = view.evaluate("""async () => (await api("/horizon", {method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({texts: ["typed into a page that missed the clear"]})})).nodes[0].origin""")
        assert view.evaluate("horizonEpoch") == epoch, "nothing told it yet, and nothing needed to"
        view.unroute("**/*")
        assert "typed into a page" in got
        origins = [n["origin"] for n in _call(server, "GET", "/horizon?limit=10")["nodes"]]
        assert any("typed into a page" in o for o in origins)
    finally:
        view.close()


def test_a_question_typed_before_the_reload_is_still_there_after_it(browser, server):
    """A Horizon question's preview carries the epoch, so a page that missed a clear reloads at the
    preview, and the question typed into the dock is put back."""
    view = _open(browser, server)
    try:
        _call(server, "POST", "/horizon", {"texts": ["something to ask about"]})
        view.evaluate("""() => { horizonEpoch = "from-before-a-clear"; window.__beforeReload = true;
            document.getElementById("ask-h-input").value = "what did I keep about sleep?";
            void api("/horizon/ask/preview", {method: "POST", headers: {"Content-Type": "application/json"},
              body: JSON.stringify({question: "what did I keep about sleep?", scope: {kind: "all"}})});
        }""")
        _reloaded(view)
        assert view.evaluate("document.getElementById('ask-h-input').value") == "what did I keep about sleep?"
        assert view.evaluate("sessionStorage.getItem('penumbra.typedBeforeReload')") is None, "kept once"
    finally:
        view.close()
