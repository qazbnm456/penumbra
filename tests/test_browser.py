"""**The web UI, driven in a real WebKit**: the engine the desktop app's WKWebView uses.

`test_web_behaviour.py` runs shipped functions against a fake DOM, which cannot see what a browser
does between `pointerdown` and `pointerup`, what a drag hands to the pointer, or whether an element
survives a repaint under the reader's hand. Those were checked by hand in Playwright's WebKit while
the star map, the studio, the tag picker and the capture editors were built; this keeps the checks.

A real server runs as a subprocess in its own directory (the suite's per-test `chdir` would move a
server running in this process to a new, empty data directory for every test), seeded through the
API. Playwright is a dev dependency and its WebKit must be installed (`uv run playwright install
webkit`; CI installs it). As with `node` (AGENTS.md, Verify), a missing browser FAILS rather than
skips: a test that vanishes when a tool is absent makes a local run greener than CI.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

TOKEN = "browser-test-token"
REPO = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"{}")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """A real `penumbra serve` with three orbits, each holding one tagged capture."""
    pytest.importorskip("fastapi")  # the `api` extra, which CI installs
    home = tmp_path_factory.mktemp("browser-server")
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
        tags = [["security", "testing", "benchmarks"], ["security", "agents"], ["models", "testing"]]
        for i, name in enumerate(["Alpha", "Beta", "Gamma"], start=1):
            note = {"texts": [f"Note {i} about {name}, a few words long."]}
            _call(base, "POST", f"/orbits/o{i}/sources", note)
            _call(base, "PUT", f"/orbits/o{i}/title", {"title": name})
        nodes = _call(base, "GET", "/horizon?limit=50")["nodes"]
        for node, chosen in zip(sorted(nodes, key=lambda n: n["origin"]), tags):
            _call(base, "PUT", f"/horizon/{node['id']}/tags", {"tags": chosen})
        _call(base, "GET", "/horizon/map")
        yield base
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


@pytest.fixture
def page(browser, server):
    view = browser.new_page(viewport={"width": 1440, "height": 900}, locale="en-US")
    errors: list[str] = []
    view.on("pageerror", lambda err: errors.append(str(err)))
    view.goto(f"{server}/#token={TOKEN}")
    view.wait_for_selector("#starmap-svg .map-planet", timeout=30000)
    view.wait_for_timeout(800)
    yield view
    view.close()
    assert not errors, f"the page threw: {errors}"


def _stored(page, path: str):
    return page.evaluate(
        f"fetch({json.dumps(path)}, {{headers: {{Authorization: 'Bearer {TOKEN}'}}}}).then(r => r.json())"
    )


def _until(check, timeout: float = 15.0):
    """Poll `check` until it returns something truthy, or fail with its last value: saves are
    debounced and run in the background, and a fixed sleep is a guess a slow runner loses."""
    deadline = time.time() + timeout
    while True:
        got = check()
        if got or time.time() > deadline:
            assert got, f"still not true after {timeout}s: {got!r}"
            return got
        time.sleep(0.1)


def test_a_dragged_planet_snaps_to_a_ring_and_keeps_its_place(page):
    """A planet follows the pointer along the nearest ring (lit while it would land there), stays
    where it is let go, and the place survives a reload (invariant 85)."""
    planet = page.locator('#starmap-svg .map-planet[data-key="orbit:o2"]')
    box = planet.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(300)
    box = planet.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    centre = page.locator("#starmap-svg .map-hole-hit").bounding_box()
    tx, ty = centre["x"] + centre["width"] / 2 + 20, centre["y"] + centre["height"] / 2 + 340
    page.mouse.down()
    for i in range(1, 25):
        page.mouse.move(x + (tx - x) * i / 24, y + (ty - y) * i / 24)
        page.wait_for_timeout(16)
    lit = page.evaluate("document.querySelectorAll('.map-ring.is-landing').length")
    page.mouse.up()
    assert lit == 1
    placed = _until(lambda: (p := _stored(page, "/horizon/map")["planets"]["o2"])["ring"] >= 1 and p)
    page.reload()
    ring = placed["ring"]
    reloaded = f"typeof starMap === 'object' && starMap.places?.o2?.ring === {ring}"
    page.wait_for_function(reloaded, timeout=30000)


def test_the_studio_keeps_its_slider_under_the_pointer_and_saves(page):
    """The studio's controls are not rebuilt by the map's redraws while it is open (`studioHolds`)."""
    page.evaluate("openMapFocus({kind: 'planet', orbit: 'o1'})")
    page.wait_for_timeout(600)
    page.locator('.planet-card-tab[data-tab="studio"]').click()
    slider = page.locator(".planet-studio input[type=range]")
    handle = slider.element_handle()
    slider.fill("1.6")
    page.wait_for_timeout(200)
    assert page.evaluate("(el) => el.isConnected", handle), "the slider was rebuilt under the pointer"
    page.locator(".planet-studio select").nth(0).select_option("lava")

    def saved():
        style = _stored(page, "/horizon/map")["planets"]["o1"]["style"]
        return (style["kind"], style["size"]) == ("lava", 1.6)

    _until(saved)


def test_a_tag_press_lands_even_when_the_counts_change_mid_press(page):
    """WebKit sends no click for a press whose button left the document before pointerup; the tag row
    writes new counts into its buttons rather than rebuilding them."""
    before = page.evaluate("document.querySelectorAll('#starmap-lenses .lens[aria-pressed=true]').length")
    chip = page.locator("#starmap-lenses .lens:not([aria-pressed=true])").first
    box = chip.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.evaluate("starMap.tags = starMap.tags.map((t, i) => i === 0 ? {...t, count: t.count + 1} : t);"
                  " paintStarMapLenses();")
    page.wait_for_timeout(80)
    page.mouse.up()
    pressed = "document.querySelectorAll('#starmap-lenses .lens[aria-pressed=true]').length"
    assert _until(lambda: page.evaluate(pressed) == before + 1, timeout=5), "the press was lost to a repaint"


def test_a_capture_is_renamed_and_retagged_in_its_card(page):
    """A capture's title and tags are the reader's (invariant 83): rename, add a tag, remove one."""
    page.locator(".view-mode-btn[aria-pressed=false]").click()
    page.wait_for_timeout(600)
    page.locator("#stream .node .node-open").first.click()
    page.wait_for_timeout(1000)
    card = page.locator("#starmap-card")
    card.locator(".card-rename").click()
    card.locator(".orbit-rename-input").fill("My bookmark")
    card.locator(".orbit-rename-input").press("Enter")
    title = "document.querySelector('#starmap-card .card-title')?.textContent"
    page.wait_for_function(f"{title} === 'My bookmark'", timeout=10000)
    count = card.locator(".tag-chip").count()
    card.locator(".tag-add").click()
    card.locator(".tag-add-input").fill("Mine")
    card.locator(".tag-add-input").press("Enter")
    page.wait_for_function("[...document.querySelectorAll('#starmap-card .tag-chip .node-tag')]"
                           ".some((el) => el.textContent === '#mine')", timeout=10000)
    card.locator(".tag-chip .tag-remove").first.click()
    page.wait_for_function(f"document.querySelectorAll('#starmap-card .tag-chip').length === {count}",
                           timeout=10000)


def test_the_map_settings_escape_leaves_a_fields_escape_alone(page):
    """Escape closes the map's settings from anywhere, but not while a field that owns Escape has it."""
    page.locator("#map-settings-open").click()
    page.wait_for_timeout(200)
    page.locator("#capture-input").focus()
    assert page.evaluate("document.activeElement.id") == "capture-input"
    page.keyboard.press("Escape")
    assert not page.evaluate("document.getElementById('map-settings').hidden"), "a field's Escape was taken"
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("Escape")
    assert page.evaluate("document.getElementById('map-settings').hidden")
