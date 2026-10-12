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
    """A real `penumbra serve` with three orbits, each holding one tagged capture, and two more
    untagged captures in the first, so its planet has moons to walk between."""
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
        for i in range(2):
            more = {"texts": [f"Another note {i} in Alpha, longer than the others."]}
            _call(base, "POST", "/orbits/o1/sources", more)
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
    where it is let go, and the place survives a reload (invariant 85).

    The map is held still (reduced motion), because a planet travels its ring: on a slow runner
    the planet measured a moment before the press had moved on, the press landed on empty space and
    panned the map instead, and no ring lit. Dragging works the same on a still map."""
    page.emulate_media(reduced_motion="reduce")
    page.reload()
    page.wait_for_selector("#starmap-svg .map-planet", timeout=30000)
    page.wait_for_timeout(800)
    planet = page.locator('#starmap-svg .map-planet[data-key="orbit:o2"]')
    box = planet.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    under = f"document.elementFromPoint({x}, {y})?.closest('.map-planet')?.dataset.key"
    assert page.evaluate(under) == "orbit:o2", "the press would not land on the planet"
    centre = page.locator("#starmap-svg .map-hole-hit").bounding_box()
    tx, ty = centre["x"] + centre["width"] / 2 + 20, centre["y"] + centre["height"] / 2 + 340
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 25):
        page.mouse.move(x + (tx - x) * i / 24, y + (ty - y) * i / 24)
        page.wait_for_timeout(16)
    page.wait_for_function("document.querySelectorAll('.map-ring.is-landing').length === 1", timeout=5000)
    page.mouse.up()
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


def test_walking_between_moons_keeps_the_card_and_the_camera_still(page):
    """Left and Right among a planet's moons: the card never collapses to "Loading" between two
    captures (a capture not yet in memory holds the card's height), and the camera keeps a zoom the
    reader made around the planet instead of gliding back on every step."""
    page.evaluate("openMapFocus({kind: 'planet', orbit: 'o1'})")
    page.wait_for_timeout(1200)
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("ArrowDown")
    page.wait_for_function("document.querySelector('#starmap-card .card-actions')", timeout=10000)
    page.evaluate("zoomBy(1.4)")
    page.wait_for_timeout(400)
    zoom = page.evaluate("mapCamera.k")
    for _ in range(4):
        before = page.evaluate("document.getElementById('starmap-card').offsetHeight")
        page.evaluate("""() => { window.__frames = []; const card = document.getElementById('starmap-card');
          const tick = () => {
            window.__frames.push([card.offsetHeight, !!card.querySelector('.card-detail .card-note')]);
            if (window.__frames.length < 45) requestAnimationFrame(tick); };
          requestAnimationFrame(tick); }""")
        page.keyboard.press("ArrowRight")
        page.wait_for_function("window.__frames.length >= 45", timeout=10000)
        frames = page.evaluate("window.__frames")
        after = frames[-1][0]
        assert not any(loading for _, loading in frames), "the card said Loading between two moons"
        assert min(height for height, _ in frames) >= min(before, after), (before, after, frames)
    assert page.evaluate("mapCamera.k") == pytest.approx(zoom), "the camera glided back to the planet"


def test_a_moon_read_still_in_flight_holds_the_card_and_lets_go_when_the_reader_moves_on(page):
    """A capture not in memory keeps the card at its height while it is read, says "Loading" only
    once the read is slow, and a planet card painted before the read lands does not inherit the
    height the moon's card was holding."""
    page.evaluate("openMapFocus({kind: 'planet', orbit: 'o1'})")
    page.wait_for_timeout(1200)
    page.evaluate("document.activeElement.blur()")
    # Every capture read takes 600ms from here, and nothing is held.
    page.evaluate("""() => { const real = window.api;
      window.api = (path, ...rest) => path.startsWith('/horizon/nd-')
        ? new Promise((done) => setTimeout(done, 600)).then(() => real(path, ...rest)) : real(path, ...rest);
      dropCapturesHeld(); }""")
    before = page.evaluate("document.getElementById('starmap-card').offsetHeight")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(100)
    card = "document.getElementById('starmap-card')"
    assert page.evaluate(f"{card}.offsetHeight") >= before, "the card collapsed while the moon was read"
    assert not page.evaluate(f"!!{card}.querySelector('.card-note')"), "Loading appeared at once"
    page.wait_for_function(f"!!{card}.querySelector('.card-note')", timeout=2000)
    page.keyboard.press("ArrowUp")
    page.wait_for_timeout(900)
    assert page.evaluate(f"{card}.style.minHeight") == "", "the planet card kept the moon's held height"


def test_a_moon_read_ahead_is_read_again_once_the_map_has_news(page, server):
    """The moons read ahead stay only until the map's data next refreshes, and one whose state the
    map now reports differently (a summary landed) is read again rather than shown from memory."""
    page.evaluate("openMapFocus({kind: 'planet', orbit: 'o1'})")
    page.wait_for_timeout(1200)
    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("ArrowDown")
    page.wait_for_function("document.querySelector('#starmap-card .card-actions')", timeout=10000)
    nxt = page.evaluate("(() => { const moons = starMap.orbits.find((o) => o.slug === 'o1').moons;"
                        " const at = moons.findIndex((m) => m.id === starMap.focus.id);"
                        " return moons[(at + 1) % moons.length].id; })()")
    page.wait_for_function(f"capturesHeld.byId.has({json.dumps(nxt)})", timeout=10000)
    _call(server, "PUT", f"/horizon/{nxt}/tags", {"tags": ["fresh-news"]})
    page.evaluate("renderStarMap()")
    page.wait_for_function(f"!capturesHeld.byId.has({json.dumps(nxt)})", timeout=10000)
    page.keyboard.press("ArrowRight")
    page.wait_for_function("[...document.querySelectorAll('#starmap-card .tag-chip .node-tag')]"
                           ".some((el) => el.textContent === '#fresh-news')", timeout=10000)
    stale = page.evaluate("""() => { holdCapture('nd-x', {node: {state: 'ready_undistilled'}});
      return heldCapture({id: 'nd-x', state: 'ready'}) === null
        && !!heldCapture({id: 'nd-x', state: ''}); }""")
    assert stale, "a capture the map reports as summarised was shown from memory"


def test_an_open_orbit_menu_in_the_waiting_card_survives_the_maps_refreshes(page, server):
    """A summary pass refreshes the map every poll, and each refresh repainted the details card,
    taking an open orbit menu with it. The card waits while one is open and catches up once it
    closes."""
    _call(server, "POST", "/horizon", {"texts": ["A loose note that is in no orbit yet."]})
    page.reload()
    page.wait_for_selector("#starmap-card .todo-list .orbit-pick-trigger", timeout=30000)
    trigger = page.locator("#starmap-card .todo-list .orbit-pick-trigger").first
    trigger.click()
    handle = trigger.element_handle()
    for _ in range(3):
        page.evaluate("renderStarMap()")
        page.wait_for_timeout(400)
    assert page.evaluate("(el) => el.isConnected && el.getAttribute('aria-expanded') === 'true'", handle), \
        "a map refresh closed the open orbit menu"
    page.locator("#starmap-card .card-title").first.click()  # a press anywhere else closes it
    page.wait_for_function("(el) => !el.isConnected", arg=handle, timeout=5000)


def test_a_capture_cards_orbits_are_marks_with_a_remove_and_an_add(page, server):
    """A capture's orbits are marks like its tags: each with a remove that takes it out of that orbit,
    then "+ Orbit", which opens the list of every orbit."""
    moon = page.evaluate("starMap.orbits.find((o) => o.slug === 'o3').moons[0]")
    page.evaluate(f"openMapFocus({{kind: 'capture', id: {json.dumps(moon['id'])}, title: 'x', state: 'ready',"
                  " orbit: 'o3'})")
    marks = "#starmap-card .orbit-pick .mark-orbit"
    page.wait_for_selector(marks, timeout=10000)
    assert page.locator(marks).all_text_contents()[0].startswith("Gamma")
    page.locator("#starmap-card .orbit-pick-trigger").click()
    assert page.evaluate("document.querySelector('#starmap-card .orbit-pick-menu').hidden === false")
    page.locator("#starmap-card .card-title").first.click()  # closes the list
    page.locator(f"{marks} .mark-x").first.click()
    _until(lambda: not _call(server, "GET", f"/horizon/{moon['id']}").get("orbits"))


def test_the_fine_sky_runs_only_in_the_dark_theme_and_says_why_when_it_cannot(browser, server):
    """In the light theme the map never draws the fine sky. In the dark theme it is drawn exactly when
    the machine allowed it, and the map's settings say which, so a missing sky is never unexplained.
    Wherever WebGL2 exists at all (CI's is often software, which the map refuses), the shaders are
    compiled and a frame drawn, so a shader that fails to build fails here rather than on a reader's
    machine."""
    for scheme in ("light", "dark"):
        view = browser.new_page(viewport={"width": 1280, "height": 860}, locale="en-US", color_scheme=scheme)
        errors: list[str] = []
        view.on("pageerror", lambda err, seen=errors: seen.append(str(err)))
        view.goto(f"{server}/#token={TOKEN}")
        view.wait_for_selector("#starmap-svg .map-planet", timeout=30000)
        view.wait_for_timeout(1500)
        state = view.evaluate("({shown: !document.getElementById('starmap-sky').hidden,"
                              " fine: document.getElementById('starmap').classList.contains('is-fine'),"
                              " probe: fineSky.probe, failed: fineSky.failed, status: fineSky.status})")
        if scheme == "light":
            assert not state["shown"] and not state["fine"], state
            assert state["status"] == "Only in the dark theme.", state
        elif state["shown"]:
            assert state["fine"] and not state["failed"] and state["status"].startswith("On, at"), state
            # Laid exactly over the SVG's box, whatever sits above the map (here a row of tags).
            boxes = view.evaluate("""() => ['starmap-sky', 'starmap-svg'].map((id) => {
              const r = document.getElementById(id).getBoundingClientRect();
              return [r.left, r.top, r.width, r.height];
            })""")
            assert all(abs(a - b) < 1 for a, b in zip(*boxes)), boxes
            # The Horizon's rim, a circle the bent shadow does not match, is not drawn; each planet's
            # light faces the hole (+x away from it); and the orbit card ends in its last row.
            rim = "getComputedStyle(document.querySelector('.map-hole-rim')).display"
            assert view.evaluate(rim) == "none"
            # Nor the keyboard's focus ring on the same circle: the Horizon's name lights instead.
            view.evaluate("document.querySelector('.map-hole-hit').focus()")
            view.keyboard.press("Shift")
            focused = view.evaluate("""() => ({
              ring: getComputedStyle(document.querySelector('.map-hole-hit')).stroke,
              name: getComputedStyle(document.querySelector('.map-hole-label')).textDecorationLine })""")
            assert focused == {"ring": "none", "name": "underline"}, focused
            view.evaluate("document.activeElement.blur()")
            facing = view.evaluate("""() => starMap.scene.planets.map(({ p, suns }) => {
              const pos = planetAt(p);
              const want = Math.atan2(pos.y - MAP_CENTRE.y, pos.x - MAP_CENTRE.x) * 180 / Math.PI;
              const got = Number((suns[0].getAttribute('transform') || '').replace(/[^-0-9.]/g, ''));
              return Math.abs(((got - want + 540) % 360) - 180);
            })""")
            assert facing and max(facing) < 5, facing
            view.evaluate("openMapFocus({kind: 'planet', orbit: 'o1'})")
            view.wait_for_selector("#starmap-card .card-foot .card-enter", timeout=5000)
            view.evaluate("closeMapFocus()")
            # The note follows the state, through Off and back.
            for choice, start in (("off", "Off"), ("auto", "On, at")):
                view.evaluate(f"localStorage.setItem('penumbra-map-quality', '{choice}'); syncFineSky()")
                assert view.evaluate("fineSky.status").startswith(start), choice
            # The list and back: the sky stops behind the hidden map and starts again with it.
            view.evaluate("setViewMode('horizon', 'list')")
            assert view.evaluate("document.getElementById('starmap-sky').hidden")
            view.evaluate("setViewMode('horizon', 'map')")
            view.wait_for_timeout(500)
            assert not view.evaluate("document.getElementById('starmap-sky').hidden")
        else:
            refused = state["status"].startswith(("Not on this computer", "Turned off"))
            assert state["failed"] and refused, state
        drew = view.evaluate("""() => {
          const canvas = document.createElement('canvas');
          canvas.style.width = '64px'; canvas.style.height = '64px';
          document.body.appendChild(canvas);
          if (!canvas.getContext('webgl2')) return 'no webgl2';
          const sky = PenumbraSky.create(canvas, {view: () => ({cx: 32, cy: 32, pxPerRs: 3})});
          const ms = sky.benchmark(1);
          sky.destroy();
          return ms > 0 ? 'drawn' : 'not drawn';
        }""")
        assert drew in ("drawn", "no webgl2"), drew
        view.close()
        assert not errors, f"the page threw: {errors}"
