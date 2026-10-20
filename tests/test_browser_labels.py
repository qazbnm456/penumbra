"""**A capture's labels on its card**, driven in a real WebKit: they come from the kit's memory store,
a capture still being read offers no rename or tags, and one the summary pass gave up on says so
and can be summarised again. Its own server, whose memory store the test writes failure rows into.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time

import pytest

from tests.test_browser import REPO, TOKEN, _call, _free_port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    pytest.importorskip("fastapi")  # the `api` extra, which CI installs
    home = tmp_path_factory.mktemp("browser-labels-server")
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
        yield base, home
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
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


def _open(browser, base):
    view = browser.new_page(viewport={"width": 1440, "height": 900}, locale="en-US")
    view.goto(f"{base}/#token={TOKEN}")
    view.wait_for_function("horizonEpoch !== null", timeout=30000)
    return view


def _card(view, node_id: str) -> dict:
    """The capture's card body as the list fills it (`fillNodeBody`), read back as text."""
    return view.evaluate(f"""async () => {{
        const got = await api(`/horizon/${{encodeURIComponent({json.dumps(node_id)})}}`);
        const row = document.createElement("li"), inner = document.createElement("div");
        await fillNodeBody(got.node, row, inner);
        const title = captureTitleRow(got.node, got.node.title || "untitled");
        const tags = captureTagEditor(got.node);
        return {{text: inner.textContent, summarise: !!inner.querySelector(".node-summarise"),
                 rename: !!title.querySelector(".card-rename"), tagAdd: !!tags.querySelector(".tag-add"),
                 named: title.querySelector(".card-title").title}};
    }}""")


def test_a_named_capture_shows_the_readers_name_and_its_editors(browser, server):
    base, _home = server
    node = _call(base, "POST", "/horizon", {"texts": ["A note about tides and the moon."]})["nodes"][0]
    _call(base, "PUT", f"/horizon/{node['id']}/title", {"title": "Tides"})
    view = _open(browser, base)
    try:
        card = _card(view, node["id"])
        assert card["rename"] and card["tagAdd"]
        assert card["named"] == "You named this."
    finally:
        view.close()


def test_a_capture_still_being_read_offers_no_rename_or_tags(browser, server):
    base, _home = server
    view = _open(browser, base)
    try:
        shown = view.evaluate("""() => {
            const node = {id: "nd-0123456789abcdef", state: "parsing", tags: [], edited: []};
            return [!!captureTitleRow(node, "x").querySelector(".card-rename"),
                    !!captureTagEditor(node).querySelector(".tag-add")];
        }""")
        assert shown == [False, False]
    finally:
        view.close()


def test_a_capture_the_pass_gave_up_on_says_so_and_can_be_summarised_again(browser, server):
    base, home = server
    node = _call(base, "POST", "/horizon", {"texts": ["A note the model could not label."]})["nodes"][0]
    with sqlite3.connect(home / "horizon" / "memory.db") as conn:
        for _ in range(3):
            conn.execute("INSERT INTO distill_failures (item_id, error, created_at) VALUES (?, ?, ?)",
                         (int(node["id"][1:]), "ValueError: unusable reply", time.time()))
    view = _open(browser, base)
    try:
        sent: list[str] = []
        view.on("request",
                lambda r: sent.append(r.post_data or "") if r.url.endswith("/horizon/distil") else None)
        card = _card(view, node["id"])
        assert "Gave up summarising this after 3 tries" in card["text"]
        assert "unusable reply" in card["text"] and card["summarise"]
        view.evaluate(f"""async () => {{
            const got = await api(`/horizon/{node['id']}`);
            const row = document.createElement("li"), inner = document.createElement("div");
            await fillNodeBody(got.node, row, inner);
            inner.querySelector(".node-summarise").click();
        }}""")
        view.wait_for_timeout(500)
        assert sent and json.loads(sent[0]) == {"limit": 1, "node_ids": [node["id"]]}
    finally:
        view.close()
