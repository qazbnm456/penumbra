"""**The web UI's behaviour, EXECUTED — not grepped for.**

Round seven deleted a `readableError` test that re-compiled the function's regex literals and never
called it; replacing the body with `return text` had left the suite green. Round eight found the
same shape one round later in round seven's own two flagship fixes: `closeTicker` and
`trajTakeFocus` could each be replaced by a no-op with all 931 tests passing, because their tests
asserted that a function NAME appeared in the source. A source-text assertion cannot see
reachability, ordering, or whether a call does anything at all.

`tests/web_dom_harness.mjs` runs the shipped functions against a small fake DOM. Its limits are
stated there and they are real. Three of them were themselves found by an independent review and
are now closed: it matches the selector subset `app.js` writes instead of reading a table, refuses
to focus a hidden or disabled element, and blurs to `<body>` when a focused element is hidden —
without which `trapTab`'s body was unreachable (`querySelectorAll` returned `[]` for everything, so
`if (true) return;` at the top of it left 961 tests passing) and round ten's drawer-focus fix could
be reverted green. Layout, styles and real events remain out of scope.

`node` is required rather than skipped-if-absent, for the reason `tests/test_readable_error.py`
gives: a test that vanishes with a missing tool makes a local run greener than CI.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("web_dom_harness.mjs")
WEB = Path(__file__).resolve().parents[1] / "penumbra" / "web"


def _run(scenario: str, mode: str | None = None) -> dict:
    node = shutil.which("node")
    assert node, (
        "node is required to execute the shipped web functions. CI installs it; see "
        ".github/workflows/ci.yml."
    )
    done = subprocess.run(
        [node, str(HARNESS)],
        input=json.dumps({"scenario": scenario, "mode": mode}),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, f"harness failed: {done.stderr}"
    return json.loads(done.stdout)["result"]


def test_the_trajectory_drawer_takes_focus_inerts_the_page_and_gives_focus_back():
    """`aria-modal="true"` is a promise with four parts, and this runs all four."""
    result = _run("drawerFocus")
    live = result["whileOpen"]

    assert live["focusInsideDrawer"], (
        "the drawer opened without moving focus into itself, so Tab starts on the page behind it"
    )
    assert live["trapInstalled"] == 1, "no keydown trap, so Tab escapes at the drawer's edges"
    assert "layout" in live["inerted"], "the page behind the drawer is still reachable by Tab"

    after = result["afterClose"]
    assert after["stillInert"] == [], "closing left part of the page inert and unusable"
    assert after["focusBack"] == "settings-open", (
        "focus did not return to the control that opened the drawer"
    )
    assert after["held"] == 0, "the inert bookkeeping was not released, so a reopen double-counts"

    # **The trigger a re-render has replaced.** `.ticker-toggle` lives inside a chat turn, so any
    # re-render between opening and closing detaches the node the drawer recorded — `.focus()` on a
    # detached element is a silent no-op, and the reader ends on `<body>`: the same "parked outside
    # an aria-modal dialog" state as opening there. Measured as zero focusin events during close.
    detached = _run("drawerFocus", "detach")["afterClose"]
    assert detached["focusIsAttached"], (
        "focus was handed to a node that is no longer in the document, so it went nowhere"
    )
    assert detached["focusBack"] == "fresh-ticker-toggle", (
        f"focus did not fall back to the live equivalent control: {detached['focusBack']!r}"
    )

    # **`<body>` IS NOT A RETURN TARGET.** `openTrajectory` awaits its fetch, and the Steps pill is
    # replaced during that gap — so what got recorded was `<body>`, and the attachment guard let it
    # through, because `document.body.contains(document.body)` is true. Every close path then called
    # `focus()` on `<body>`: the reader is ejected from the focus order with no indicator, and the
    # next Tab restarts at the wordmark. The whole fallback chain was unreachable.
    from_body = _run("drawerFocus", "body")["afterClose"]
    assert from_body["focusBack"] not in (None, "", "body"), (
        f"focus was handed to <body>, which is not a place a reader can be: {from_body!r}"
    )
    assert from_body["focusBack"] == "ask-input", (
        f"with no live trigger the chain must reach the composer, got {from_body['focusBack']!r}"
    )


def test_a_panels_own_backdrop_and_the_toast_rail_are_not_the_page_behind_it():
    """**Two siblings that are the overlay's own machinery, and inerting them broke both.**

    `inert` removes a subtree from hit-testing AND from the accessibility tree. The drawer's
    backdrop carries `pointer-events: auto` and a `closeTrajectory` click listener, so inerting it
    killed click-outside-to-close while the CSS and the listener both still promised it — Escape and
    ✕ still worked, which is why nothing noticed. `#notices` is where every toast lands, so a toast
    raised FROM a dialog had a dead ✕ (the click passed through to the dialog behind) and was never
    announced; `notify` defaults to `life = 0` for a bad tone, so it never went away either.
    """
    live = _run("drawerFocus")["whileOpen"]
    assert not live["backdropInert"], (
        "the drawer inerted its own backdrop, so clicking outside it does nothing"
    )
    assert not live["noticesInert"], (
        "the toast rail was inerted, so a toast raised from this surface cannot be dismissed or "
        "announced"
    )


def test_a_modal_still_inerts_everything_that_really_is_behind_it():
    """The other side of the same rule: sparing two siblings must not spare the page."""
    result = _run("modalStillInertsThePage")
    assert result["headerInert"] and result["horizonInert"], (
        "a modal no longer inerts the page behind it, which is the whole point of the mechanism"
    )
    assert result["backdropInert"], (
        "another surface's backdrop IS the page behind this one; only the drawer spares its own"
    )
    assert not result["noticesInert"], "the toast rail is never the page behind anything"
    assert "notices" not in result["touched"]


def test_a_live_stream_is_really_closed_and_a_second_open_does_not_orphan_the_first():
    """**`closeTicker` was a no-op as far as the suite could tell**, and re-opening one run id
    orphaned an `EventSource` that then reconnected for the life of the tab.

    Overwriting the map entry left the first stream with no handle: its own `onerror` looks the run
    up, finds the newer entry or nothing, and returns — so nothing could ever close it. Reachable by
    asking in orbit A, navigating away, and coming back while it still runs. Same leak the map
    was added to stop, re-entering per RUN instead of per orbit open.
    """
    result = _run("tickerLifecycle")

    assert result["afterFirst"] == {"opened": 1, "size": 1}
    second = result["afterSecond"]
    assert second["opened"] == 2 and second["size"] == 1, (
        "a second ticker for one run id must replace the first, not sit beside it"
    )
    assert second["firstClosed"], (
        "the first stream was dropped rather than closed - it has no handle left and will "
        "reconnect every few seconds for the life of the tab"
    )
    assert not second["secondClosed"], "the live stream was closed instead of the orphan"

    # **The stale teardown.** `reattachInFlightRuns` remounts on every orbit open and its 2.5s
    # poll outlives the mount that started it, so on the second Horizon↔orbit round trip during a
    # run the PREVIOUS mount's `done({gone: true})` looked the run id up, found the NEW mount's
    # stream, and closed that — born at t+13324ms, killed 584ms later, no EventSource ever created
    # again, while the clock and Stop kept promising otherwise.
    stale = result["afterStaleClose"]
    assert stale["liveStillOpen"], (
        "a teardown holding a stale handle closed the live stream for that run - the exact inverse "
        "of the collision `openTicker` was taught to avoid, through the same lookup"
    )
    assert stale["size"] == 1, "the registry lost the live stream it still owns"

    after = result["afterClose"]
    assert after["allClosed"], "closeTicker did not actually close the stream"
    assert after["size"] == 0, "the registry still holds a handle to a closed stream"
    assert result["survivedExtraCloses"], "closing twice, or closing an unknown run, must be safe"


@pytest.mark.parametrize("scenario", ["drawerFocus", "modalStillInertsThePage", "tickerLifecycle"])
def test_the_harness_reaches_the_real_source(scenario: str) -> None:
    """The harness extracts functions from `app.js` BY NAME. A rename must fail loudly here rather
    than quietly testing a copy that no longer ships - which is the failure mode this whole file
    exists to end.
    """
    assert _run(scenario), f"{scenario} returned nothing"


def test_a_run_in_flight_disables_the_controls_that_would_start_a_second_one():
    """**Round eight's "it costs money" fix shipped with no test of any kind.**

    An independent review put `if (true) return;` in `syncRunGuards`' body and all 945 tests stayed
    green — fourth instance of this project's recurring failure, in the newest code, on the one fix
    the CHANGELOG prices in money. The harness beside this file was built for exactly that class and
    had not been pointed at it.

    What it guards: after a reload, `reattachInFlightRuns` restores the run indicator and its Stop,
    but each control's own in-flight flag lives in the tab's memory and the tab is new. One press of
    Generate podcast then bought a SECOND worker — two run ids, two `penumbra.worker` processes,
    two status rows counting in parallel, nothing said.
    """
    result = _run("runGuards")
    def by_id(rows: list[dict]) -> dict:
        # The harness reports an id, or the className for the controls that have no id.
        return {row["id"]: row for row in rows}

    idle, busy, reloaded, released, other = (
        by_id(result[k]) for k in ("idle", "busy", "afterReload", "released", "otherOrbit")
    )

    for control in ("podcast-generate", "guide-regenerate", "chat-starter-btn"):
        assert not idle[control]["off"], f"{control} starts disabled with nothing running"
        assert busy[control]["off"], (
            f"{control} is still pressable while a run is in flight - one press buys a second "
            "billed worker on the same orbit"
        )
        assert busy[control]["tip"], f"{control} is disabled with no reason given"
        assert reloaded[control]["off"], f"{control} came back live after a reload"
        assert not released[control]["off"], f"{control} was left disabled after the run ended"

    # **A STATIC control's tooltip is RESTORED, not deleted.** `applyStaticI18n` writes these at
    # boot and on a language change only, so deleting the key left the control with no help text for
    # the rest of the session — after a run it had nothing to do with. An independent review
    # reverted this fix wholesale with all 953 tests still green, because the fakes here carried no
    # `i18nTipSource`; they do now.
    for control in ("podcast-generate", "guide-regenerate"):
        original = idle[control]["tip"]
        assert original, f"{control} starts with no tooltip, so this proves nothing"
        assert busy[control]["tip"] != original, f"{control} did not say why it was disabled"
        assert released[control]["tip"] == original, (
            f"{control} lost its help text for the rest of the session: "
            f"{released[control]['tip']!r} (was {original!r})"
        )

    # **Never touch a control something else disabled for its own reason.** Marking one that was
    # already off meant releasing the guard turned it back ON, handing back a button that should
    # still have been unusable.
    for phase, rows in (("idle", idle), ("busy", busy), ("afterReload", reloaded), ("released", released)):
        assert rows["add-note"]["off"], (
            f"a control disabled by another flow was re-enabled by the run guard, in {phase}"
        )
        assert rows["add-note"]["tip"] is None, "the guard took over another control's tooltip"

    # A run on a DIFFERENT orbit is not this orbit's business.
    for control in ("podcast-generate", "guide-regenerate", "chat-starter-btn"):
        assert not other[control]["off"], (
            f"{control} was disabled by a run on another orbit - `activeRuns` is keyed per "
            "orbit precisely so it is not"
        )

    # **THE COMPOSER, and only after a reload.** The exemption's stated reason is "the pending turn
    # is its own guard" — true in this tab, and exactly what a new tab does not have. Measured: a
    # reload with a run in flight left `#ask-submit` live the instant you typed, and the last turn's
    # `↻ Regenerate` live too, each issuing a real `POST /ask` with a fresh run id. That is a second
    # billed worker, and since `_ACTIVE_RUNS` keeps one slot per orbit (invariant 23), Stop then
    # reaches only the second and the first cannot be stopped at all.
    for control in ("ask-submit", "turn-regenerate-btn"):
        assert not idle[control]["off"], f"{control} is disabled with nothing running"
        assert not busy[control]["off"], (
            f"{control} was taken away during a run THIS TAB started, where the pending turn "
            "already guards it - that is the exemption this guard deliberately keeps"
        )
        assert reloaded[control]["off"], (
            f"{control} is live while a RECOVERED run is in flight - one press buys a second "
            "billed worker and orphans the first run's cancel handle"
        )
        assert not released[control]["off"], f"{control} was left disabled after the run ended"


def test_recovering_a_run_marks_the_orbit_so_the_composer_is_guarded_too():
    """**The flag's whole lifecycle, run through `reattachInFlightRuns` itself.**

    The guard scenario above INJECTS the recovery flag, which proves the guard reads it and nothing
    about whether anything sets it — so `recoveredRuns.add` and `.delete` could both be deleted with
    every test still green. This runs the real function with one-line stubs for its collaborators,
    which is the only way the wiring is under test rather than described.
    """
    # "silent" is the race this recovery exists for: the run ends between the `/runs` answer and
    # the stream opening, so NO terminal event ever arrives and the mount's own teardown is the only
    # thing that can close the socket it opened.
    for mode in ("fail", "finish", "silent"):
        result = _run("recovery", mode)
        mount = result["afterMount"]
        assert mount["flagged"], (
            f"[{mode}] recovering a run did not mark the orbit, so the composer stays live and "
            "one press buys a second billed worker"
        )
        assert mount["guardSawFlag"], (
            f"[{mode}] the guard was not re-run after the flag was set, so it read a stale answer"
        )
        assert result["flagCleared"], (
            f"[{mode}] the flag outlived the run, leaving the composer disabled for good"
        )
        assert result["finished"] == 1, f"[{mode}] the status row never ended"
        assert result["ownStreamClosed"], (
            f"[{mode}] the mount ended without closing the stream it opened - the socket leak this "
            "whole mechanism exists to stop"
        )


def test_a_recovered_run_that_failed_says_so_instead_of_offering_a_result():
    """**"That run has finished. Load the result" over a run that FAILED.**

    The reader's question was gone, the provider's reason was nowhere, and the button's only outcome
    was nothing — on the one path that has no other channel, after a call that was still billed.
    Invariant 60's own sentence. The same failure WITHOUT a reload renders correctly, so the
    machinery existed; the recovered path just could not tell the two apart.

    The ticker's terminal event is where it can: `failed` carries the server's message.
    """
    failed = _run("recovery", "fail")["rendered"]
    assert len(failed) == 1, f"expected one row, got {failed}"
    assert "That question did not run" in failed[0], (
        f"a failed run was not reported as one: {failed[0]!r}"
    )
    assert "the provider rejected the key" in failed[0], (
        f"the server's reason was dropped, which is the only actionable half: {failed[0]!r}"
    )
    assert "Load the result" not in failed[0], "a failed run still offers a result that is not there"

    finished = _run("recovery", "finish")["rendered"]
    assert any("run-recovered-done" in row for row in finished), (
        f"a run that ended cleanly lost its row entirely: {finished}"
    )


def test_a_orbit_switch_during_a_run_does_not_kill_the_new_streams_trace():
    """**The second Horizon↔orbit round trip killed the live trace for good.**

    Each `reattachInFlightRuns` mount starts a 2.5s poll that outlives it. On the second mount the
    FIRST mount's poll fired, found the run gone from its own snapshot, and tore down — closing the
    stream the SECOND mount had just opened, 584ms after it opened, with no EventSource ever created
    again. The row froze while the clock and Stop kept running and the run was still alive
    server-side.
    """
    result = _run("recovery", "stale")
    assert result["streams"] == 2, "the second mount did not open its own stream"
    assert result["liveStillOpen"], (
        "the previous mount's teardown closed the new mount's live stream - the model's own words "
        "stop arriving and nothing says so"
    )


def test_stopping_a_recovered_run_releases_the_orbit_too():
    """**Stop went through a second teardown, and the second one forgot the bookkeeping.**

    `onCancel` set `watching = false` and removed the row by hand, so the shared teardown's own
    `if (!watching) return;` swallowed the ONLY `recoveredRuns.delete` in the file. The orbit then
    stayed marked as recovering for the life of the tab, and every ordinary in-tab run afterwards
    took `#ask-submit` and `↻ Regenerate` away — exactly the lie the guard's comment refuses:
    "asking while an artifact generates is a reasonable thing to want".

    Two teardown paths is how one of them ends up missing a step, so there is one now.
    """
    result = _run("recovery", "stop")
    assert "error" not in result, result.get("error")
    assert result["flagCleared"], (
        "Stop left the orbit marked as recovering, so every later in-tab run disables the "
        "composer for the rest of the session"
    )
    assert result["finished"] == 1, "Stop did not end the status row, so the header dot stays lit"
    assert result["ownStreamClosed"], "Stop left the recovered run's stream open"
    # ...and the composer is RE-DECIDED once the flag is gone: a ↻ Regenerate built while the lock
    # held stayed disabled until a reload, because `syncRunGuards` only releases what it marked.
    assert result["composerResynced"], "Stop did not re-decide the composer after recovery ended"
    assert result["rendered"] == [], (
        "Stop left a row behind - the reader stopped it, they do not need telling it ended"
    )


def test_starting_a_run_is_what_makes_the_guard_fire():
    """**The seam neither other scenario could see.**

    `syncRunGuards` is driven with `activeRuns` INJECTED; `reattachInFlightRuns` is driven with
    `runStatus` STUBBED. So `noteRunStarted` — the only line in the file that ever populates
    `activeRuns` — was testable by nobody. Deleting it left all 953 tests green while `busy` became
    permanently false, every guard released, and "one press buys a second billed worker" came back
    invisibly.

    **This test covers the BOOKKEEPING, not the seam, and it used to claim otherwise.** It calls
    `noteRunStarted` directly; production never does — the only call is the first statement of
    `runStatus`. A later review deleted that statement and all 979 tests were still green, against a
    docstring here saying exactly that deletion was now caught. Pinning a function is not pinning
    the call to it, and the sentence that conflated them is the same failure one level up. The seam
    is `test_the_call_that_starts_a_run_is_what_takes_the_guard` below, which executes the real
    `runStatus`.
    """
    result = _run("runBookkeeping")

    assert result["idle"] == {"busy": False, "off": False}, "an orbit starts busy"
    assert result["started"] == {"busy": True, "off": True}, (
        "starting a run did not mark the orbit busy, so no guard can ever fire"
    )
    # A COUNT, not a flag: `/overview` fires two runs, and one ending must not release the other.
    assert result["stillOne"] == {"busy": True, "off": True}, (
        "one of two runs ending released the guard while the other was still going"
    )
    assert result["ended"] == {"busy": False, "off": False}, "the guard never released"
    # The header's run dot and the orbit list both repaint off this event.
    assert result["emitted"].count("runs:changed") == 4, (
        f"every start and finish must announce itself: {result['emitted']}"
    )


@pytest.mark.parametrize("scenario", ["drawerFocusOrder", "tabTrap"])
def test_the_focus_scenarios_reach_the_real_source(scenario: str) -> None:
    assert _run(scenario), f"{scenario} returned nothing"


def test_the_drawer_renders_before_it_takes_focus():
    """**Round ten's fix, which shipped with no test — reverting either half left the suite green.**

    `trajShowDrawer` focuses the drawer's first focusable; `renderTrajectory` then hides `#traj-run`
    on any single-run trace, and every persisted "Steps" pill opens with exactly one run id. Hiding
    a focused element blurs it to `<body>`, so the reader landed outside an `aria-modal` dialog that
    hides the page behind it from a screen reader: two Tab presses to reach anything.

    The harness could not catch it either, which is why this arrives with the shim change that lets
    it: focusing a hidden element is now the no-op a browser performs.
    """
    shipped = _run("drawerFocusOrder", "render-first")
    assert not shipped["onBody"], "focus was left on <body> under an aria-modal dialog"
    assert shipped["insideDrawer"], f"focus landed outside the drawer: {shipped}"
    assert shipped["focusedId"] == "traj-search", shipped
    # The `:not([hidden])` and `:not(:disabled)` halves of the same selector.
    assert not shipped["onHidden"], "focus was put on a control the reader cannot see"
    assert not shipped["onDisabled"], "focus was put on a disabled control"

    # The other order is the bug, through the same shipped `trajTakeFocus`.
    reverted = _run("drawerFocusOrder", "focus-first")
    assert reverted["onBody"], (
        "focusing before the render must strand the reader on <body> — if this passes, the harness "
        "has stopped modelling the thing that made the bug invisible"
    )


def test_tab_is_trapped_inside_the_drawer_and_skips_what_cannot_be_reached():
    """`trapTab` guards the other half of `aria-modal`: six consecutive Tabs used to walk the page
    behind the overlay. Its body was unreachable in the harness until now, so this is the first time
    it has been executed by any test.
    """
    result = _run("tabTrap")
    assert result["candidates"] == [
        "traj-close",
        "traj-search",
        "traj-copy",
        "traj-link",
        "traj-custom",
    ], result
    # Each exclusion is a different clause of the selector, and the last two could not be tested at
    # all until the harness learned the attribute-to-property mapping: `[tabindex]`, `[tabindex='-1']`
    # and `a[href]` matched nothing, so those clauses were deletable with the suite green.
    for why, ident in result["excluded"].items():
        assert ident not in result["candidates"], f"{why}: {ident} is not a tab stop"

    assert result["forwardFromLast"] == {"landed": "traj-close", "prevented": True}, result
    assert result["backFromFirst"] == {"landed": "traj-custom", "prevented": True}, result
    # Interior presses, and any other key, must be left to the browser.
    assert result["interiorIsLeftAlone"]["prevented"] is False, result
    assert result["otherKey"]["prevented"] is False, result


def test_the_call_that_starts_a_run_is_what_takes_the_guard():
    """**The seam itself: `runStatus`'s first statement, executed.**

    The test above drives `noteRunStarted` by hand, so deleting the ONE production call to it —
    `app.js:469`, the first line of `runStatus` — left the whole suite green. The harness could not
    do better: `runStatus` builds its own tree with `document.createElement`, which the shim did not
    have, so every scenario stubbed it. It has one now, and this runs the real function.

    What it costs if it regresses is priced in money: `activeRuns` stays empty, `syncRunGuards`
    releases every guard, and one press after a reload buys a second billed worker on an orbit
    whose `_ACTIVE_RUNS` slot (invariant 23) means the first can then never be stopped.
    """
    result = _run("runStatusTakesTheGuard")

    assert result["before"] == {"busy": False, "off": False}, "an orbit does not start busy"
    assert result["during"] == {"busy": True, "off": True}, (
        "calling runStatus did not mark the orbit busy, so no guard fired — the seam is open"
    )
    assert result["after"] == {"busy": False, "off": False}, "finish() must release the guard"


@pytest.mark.parametrize(
    ("mode", "note"),
    [
        ("404-known", "That orbit is not here any more."),
        ("corrupt", "orbits/x.json exists but is not a valid orbit file"),
        ("offline", "Lost contact with the Penumbra server"),
        ("server", "Something went wrong on the server"),
    ],
)
def test_a_failed_load_never_invents_an_empty_orbit(mode: str, note: str):
    """**One dropped request fabricated the reader's orbit, permanently and silently.**

    `openOrbit`'s `catch` was bare, so every failure meant "does not exist yet". Blocking a
    single request to an orbit with four sources and two turns rendered it as: title "Untitled
    orbit", no sources, "Ask a question once you've added a source.", an empty notices rail, and
    the `?orb=` dropped from the address bar. Four false statements about the reader's own data, no
    error, no retry, and it did not heal when the request started working again — while "Add source"
    from that screen writes into an orbit the reader believes is empty.

    It also discarded what the server had gone to the trouble of saying: invariant 27 makes a
    corrupted orbit file a 409 carrying the sentence that says how to fix it, and the boot path
    turned that into "that orbit is not here any more" — telling a reader their orbit was
    deleted when the server had just said it was broken and repairable.
    """
    result = _run("openOrbitFailure", mode)

    assert result["opened"] is False, "a failed load must not report success"
    assert result["invented"] is False, (
        "an orbit was installed into state from a failed request — this is the fabrication"
    )
    assert result["switchedView"] is False, "the reader must be left where they were"
    assert len(result["notices"]) == 1, f"exactly one thing should be said: {result['notices']}"
    assert note in result["notices"][0], result["notices"][0]
    # The message is the one the READER gets: the scenario runs the real `readableError`, so a raw
    # status or a browser's internal wording reaching this assertion is a real defect and not a stub.
    assert "Failed to fetch" not in result["notices"][0]
    assert "500:" not in result["notices"][0]


def test_a_freshly_minted_id_is_still_created_lazily():
    """The one case the placeholder is FOR (invariant 37): the UI mints an id and the orbit is
    created by its first source, so a 404 there is expected rather than news. `fresh` is what
    separates it from a facet, a picker row or a bookmark naming something that should exist."""
    result = _run("openOrbitFailure", "404-fresh")

    assert result["opened"] is True
    assert result["invented"] is True, "a minted id must still open an empty orbit to work in"
    assert result["switchedView"] is True
    assert result["notices"] == [], "minting an orbit is not an error to report"


def test_a_citation_stroke_is_reachable_and_operable_without_a_mouse():
    """**The product's signature interaction was mouse-only.**

    `DESIGN.md` §2 calls the stroke "the literal visual expression of the product's core value", and
    it carried a `click` listener and nothing else: measured at runtime, `tabindex: null`,
    `role: null`, `aria-label: null`. A recorded Tab walk of a whole orbit — 37 stops, Sources
    tabs through to Generate summary — reached not one citation, and a screen reader read it as
    ordinary prose that happened to do nothing. SC 2.1.1 (Keyboard) and SC 4.1.2 (Name, Role,
    Value), both Level A. At rest the only mark of a clickable stroke was `cursor: pointer` and a
    hover filter, neither of which exists for a keyboard or on touch.

    Runs the real `renderAnswerWithCitations` over the real markdown renderer, so the strokes under
    test are the ones a reader gets — including the split-fragment case, where a stroke crossing an
    inline `**` is emitted as several spans that must all behave alike.
    """
    result = _run("citationStroke")

    assert result["strokes"] >= 2, "the answer should split across the inline marker"
    assert result["tabIndex"] == 0, "a citation is not reachable by Tab"
    assert result["role"] == "button", "a screen reader is told nothing about what this is"
    assert result["hasKeydown"] == 1, "there is no key handler, so Enter and Space do nothing"

    # **ONE tab stop per citation, not one per fragment.** A stroke crossing an inline `**` is
    # emitted as several spans, and making every one operable turned one reference into three
    # identical-sounding buttons — two of them announcing no number, since only the last fragment
    # carries `data-reference`. Visually they join into one mark, so this was keyboard-only, and it
    # arrived WITH the keyboard fix.
    assert result["operable"] == 1, f"{result['operable']} tab stops for one citation"
    assert result["numbered"] == 1, "exactly one superscript per citation"
    assert result["hiddenFragments"] == result["strokes"] - 1
    assert result["lastIsTheOperableOne"], "the stop belongs on the fragment carrying the number"

    # Enter and Space both activate, and anything else is left to the browser.
    assert result["openedByEnter"] == 1, "Enter did not open the reference"
    assert result["openedTotal"] == 2, "Space must activate too, and an ordinary key must not"
    assert result["preventedDefault"], "Space would otherwise scroll the page"

    # The reciprocal highlight, which was bound to the mouse alone: a keyboard reader got the
    # destination and not the answer to "which source is this".
    assert result["litOnFocus"], "focusing a stroke did not light its reference row"
    assert result["clearedOnBlur"], "leaving it did not clear the highlight"


def test_a_citation_with_no_run_stays_plain_rather_than_pretending():
    """Invariant 29's graceful degradation: a turn saved before run ids existed cannot open a
    reference, so its strokes are deliberately inert. Making them focusable would be the opposite
    failure to the one above — an affordance that promises something it cannot do."""
    result = _run("citationStroke", "no-run")

    assert result["strokes"] >= 2, "the strokes should still render"
    assert result["operable"] == 0, "nothing is operable without a run to open"
    assert result["tabIndex"] is None, "an inert citation must not be a tab stop"
    assert result["role"] is None
    assert result["hasKeydown"] == 0
    # ...but pointing at one still says which source it is, which needs no run id.
    assert result["litOnFocus"] or result["openedTotal"] == 0


def test_the_keyboard_shortcuts_reach_the_field_the_screen_is_for():
    """**The product had no shortcuts at all**, which is the clearest "web page, not app" tell in it
    and the one that matters most for the planned Tauri shell: a window with none is a browser tab
    with the chrome removed. Every global `keydown` in `app.js` handled exactly one key, `Escape`.

    ⌘K is one binding with one meaning — "start typing the thing this screen is for" — rather than
    two the reader has to tell apart.
    """
    horizon = _run("shortcuts", "horizon")
    assert horizon["cmdK"] == {"focus": "capture-input", "prevented": True}
    assert horizon["cmdF"] == {"focus": "stream-search", "prevented": True}
    assert horizon["cmdComma"]["opened"] == 1, "Cmd-, did not open Settings"

    orbit = _run("shortcuts", "orbit")
    assert orbit["cmdK"]["focus"] == "ask-input", "in an orbit the composer is the field"

    # Ctrl is the same binding on Windows and Linux, which a Tauri build ships to as well.
    assert horizon["ctrlK"]["focus"] == "capture-input"


def test_a_shortcut_that_cannot_act_leaves_the_browsers_own_alone():
    """**⌘F is the case that forces this.** The find field is hidden on an empty Horizon, so an
    unconditional `preventDefault` would take the browser's Find away and put nothing in its place:
    the reader presses a key they have used for thirty years and the page silently eats it.

    `HTMLElement.focus()` is a no-op on something not rendered, so "did I focus it" has to be asked
    rather than assumed — the binding reports whether it acted, and only then is the browser's own
    shortcut swallowed.
    """
    empty = _run("shortcuts", "no-find")
    assert empty["cmdF"]["prevented"] is False, "the browser's Find was swallowed for nothing"
    assert empty["cmdF"]["focus"] != "stream-search", "a hidden field cannot take focus"
    # ...while the bindings that CAN act still do.
    assert empty["cmdK"] == {"focus": "capture-input", "prevented": True}


def test_no_shortcut_swallows_a_bare_key_or_an_unbound_combination():
    """This product is mostly a text field, so a bare-letter shortcut would have to guess whether
    the reader is typing — and the guessing is where that class of bug lives. Modifier combinations
    only, and an unbound one is left entirely to the browser."""
    for mode in ("horizon", "orbit", "no-find"):
        result = _run("shortcuts", mode)
        assert result["plainK"]["prevented"] is False, f"{mode}: a bare 'k' was swallowed"
        assert result["cmdP"]["prevented"] is False, f"{mode}: an unbound combination was swallowed"


def test_the_audio_transport_is_this_products_own_and_actually_drives_the_element():
    """**`<audio controls>` was the last un-themed surface, on the most expensive artifact.**

    Chrome's stock black pill — play, slider, volume, a `⋮` overflow menu — inside a hand-drawn
    ink-on-paper panel, while the native file picker had already been replaced for showing OS chrome
    in the wrong locale and the scrollbars and `<select>`s were themed for the same reason. It is
    also the worst one to leave cross-platform: a Tauri build is WKWebView on macOS, WebView2 on
    Windows and WebKitGTK on Linux, three genuinely different players.

    The element still does all the work; only its chrome is ours. A real `<button>` and a real
    `<input type="range">`, because both are keyboard-operable and nameable for free.
    """
    r = _run("transport")

    assert r["role"] == "BUTTON" and r["scrubIsRange"] == "range", (
        "hand-rolled widgets lose keyboard operation and an accessible name"
    )

    # Before metadata there is no duration, and the scrub must not pretend to know where it is.
    assert r["cold"]["clock"].endswith("--:--")
    assert r["cold"]["scrubOff"] is True

    # Metadata arrives: the scrub spans the episode and the clock says how long it is.
    assert r["ready"]["clock"] == "0:00 / 2:34"
    assert r["ready"]["scrubMax"] == "154" and r["ready"]["scrubOff"] is False

    # Press toggles, and the LABEL follows the element's state rather than a local flag.
    assert r["playing"]["label"] == "Pause" and r["plays"] == 1
    assert r["paused"]["label"] == "Play" and r["pauses"] == 1

    # `timeupdate` moves both the handle and the clock.
    assert r["advanced"]["clock"] == "1:05 / 2:34"
    assert r["advanced"]["scrubValue"] == "65"

    # A drag or an arrow key seeks LIVE — this is what makes the transcript follow the handle
    # instead of jumping when the drag ends.
    assert r["afterDrag"] == {"seekedTo": 100, "clock": "1:40 / 2:34"}

    # A range announces a NUMBER unless told otherwise, and "437" means nothing here.
    assert r["advanced"]["valuetext"] == "1:05 / 2:34"


def test_being_locked_out_replaces_the_app_rather_than_leaving_it_looking_live():
    """**Every affordance on a locked-out page was dead and none of them looked it.**

    Opening without `?token=` — which an ordinary bookmark does, and which is also what a
    mis-handshaked Tauri sidecar produces — gave a facet rail, "+ New orbit", Settings, the theme
    toggle and a FOCUSED capture field, all of them inert in effect and live in appearance. The
    remedy was one line of body text telling the reader to hand-edit a URL, and there was no field
    anywhere in the product to paste a token into although the app already persists one.

    Invariant 60's rule ("a status line may not claim something the page is not doing") one layer
    out: the whole surface was making the claim.
    """
    result = _run("tokenGate")

    assert result["shown"], "the gate did not open"
    assert result["focused"] == "token-gate-input", "the reader has to hunt for the one field"
    assert result["errorShown"] and "not accepted" in result["errorText"]

    # Unreachable, not merely unhelpful — the same treatment the Trajectory drawer gets.
    assert result["layoutInert"] and result["headerInert"] and result["captureInert"]
    assert not result["gateInert"], "the gate inerted itself"
    # `#notices` stays live for the same reason it is exempt everywhere else: a message about the
    # failure has to have somewhere to land.
    assert not result["noticesInert"]


def test_a_source_is_named_by_its_title_not_its_host():
    """**The one human-readable identifier the product has was reachable nowhere.**

    `.src-title` is line-clamped to two lines with no tooltip; the row button's `aria-label` said
    "Open arxiv.org" and OVERRODE its own content, so a screen reader never heard the title at all;
    and the source viewer headed itself with the host. Three surfaces, one cause —
    `sourceDisplayName` returned the host and never looked at the scraped title.

    The Horizon's whole thesis is that if recall cannot be visual it has to be typographic. A title
    that is truncated everywhere and absent from the accessibility tree is neither.
    """
    result = _run("sourceName")

    assert result["withTitle"] == "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
    # No preview (a pasted note, a local file): the old behaviour, which was right for those.
    assert result["noPreview"] == "example.com"
    assert result["pasted"].startswith("a pasted"), result["pasted"]
    # Whitespace-only is not a title.
    assert result["blankTitle"] == "example.com"


def test_the_trajectory_axis_labels_what_the_strip_actually_partitions():
    """**A TRUE label over an untrue layout**, which is the half that had to go.

    `renderTrajTimeline` normalises segment widths by the sum of tool `duration_s`, while the axis
    read `formatTimecode(total_s)` — the run's wall clock. Measured on a 99.1s run whose four tool
    calls took 185ms between them: a 180ms `read_skill` drawn as 67% of an axis labelled `1:39`, the
    40.6s the model spent thinking between calls drawn as nothing, and a 2.9s sub-LM call given the
    same 108px floor as a 2ms validator.

    Laying out against `total_s` is the other fix and is wrong here — `TRAJ_SEG_MIN_PX` exists
    because these calls are milliseconds, so every segment would collapse to a sliver. The wall
    clock is already on the header stat, where it is true.
    """
    result = _run("trajAxis")

    # 185ms of tool time on a 99.1s run: the axis says the former, because that is what it divides.
    assert result["axis"] == "185ms", result
    assert "1:39" not in result["axis"], "the axis is labelled with a clock the layout ignores"
    # ...and the sub-second case is not floored to 0:00, which is what `formatTimecode` would do.
    assert result["subSecond"] == "185ms"
    assert result["seconds"] == "2.9s"
    assert result["minutes"] == "1:39"


def test_reference_numbers_follow_reading_order_not_the_model_s_array():
    """**The interface owns the numbering (invariant 48.5) and was assigning it in array order.**

    `collectReferences` iterates each artifact's citations as the model emitted them, so a model
    that cited a source out of the order it wrote about it produced marks running 1, 3, 4, 6, 5 down
    a single answer — measured on a seeded orbit. The whole reason the model is forbidden from
    numbering its own citations is that there should be exactly one coherent scheme; a scheme that
    counts in emission order is not coherent to the reader, who meets them in prose order.

    `answer_span` is the model pointing at its own prose (invariant 49), which is exactly the
    coordinate needed to sort by where each mark will be met.
    """
    result = _run("referenceOrder")

    assert result["ordered"] == ["s1", "s2", "s3", "s8", "s9"], (
        f"numbers do not follow the prose: {result['ordered']}"
    )
    # **The other five surfaces render the same numbered stroke and were left in emission order.**
    # The first fix touched the overview and the chat turns, which is where the defect had been
    # measured — the class is every artifact `renderAnswerWithCitations` draws. A Timeline read
    # `[3] … [1] … [2]` beneath an overview reading `[1] [2] [3]`, and because Copy/Download
    # renumbers from this same list, the wrong numbers left the product as a file.
    assert result["otherSurfaces"] == ["p1", "p3", "g1", "g3", "f1", "f3", "t1", "t3"], (
        f"a surface is still numbered in the model's emission order: {result['otherSurfaces']}"
    )

    # A citation with no span cannot be located, so it keeps its array position — the honest
    # fallback rather than a guess.
    assert result["noSpans"] == ["b", "a"]

    # **The MIXED case, which is the designed common one and which the first fix got wrong.**
    # `instructions.py` tells the model to leave `answer_span` out when it cannot point that
    # precisely, and `citations.locate_answer_spans` nulls any span it cannot find verbatim — so an
    # array with some spans and some not is what the product asks for, not an edge case. The first
    # comparator here was `a.seen < 0 || b.seen < 0 ? a.at - b.at : …`, which is not a consistent
    # ordering: one span-less citation dragged its neighbours back into emission order, so
    # `[s3(Gamma), sX, s1(Alpha)]` came out `s3, sX, s1` and the reader met `[3] … [1]`.
    assert result["oneMissingInTheMiddle"] == ["s1", "sX", "s3"], result["oneMissingInTheMiddle"]
    assert result["oneMissingThirdOfFour"] == ["s1", "s2", "sX", "s3"], (
        result["oneMissingThirdOfFour"]
    )


def test_a_printed_orbit_carries_the_list_its_numbers_point_at():
    """**Cmd+P printed superscript numbers with no list to look them up in.**

    `@media print` hides `.col-studio`, which is chrome, and `#panel-references` lives inside it,
    while `.citation::after` kept printing each mark's number — and the stylesheet's comment claimed
    "the references print with it". Un-hiding the panel would not fix it: the panel is only built
    while its tab is showing. So the list is built at `beforeprint`, from `collectReferences()`, the
    same order every mark on the page was stamped from.
    """
    result = _run("printReferences")

    assert result["onTheHorizon"] == 0, "the Horizon has no references and must not print any"
    # Reading order (s1 is met first in the prose), and an unverified citation says so on paper.
    assert result["printed"] == [
        "a.txt · page:1 (unverified)q-s1",
        "b.txt · page:1q-s2",
    ], result["printed"]
    # Title + list, once each: a second print dialog must not stack a second of either.
    assert result["afterTwoPrints"] == 2, "a second print dialog stacked a second list or title"
    # The orbit's name heads the page: print hides the header, which is the only place it was.
    assert result["title"] == "Voyager notes" and result["titleFirst"], result
    assert result["afterPrint"] == 0, "the print-only list stayed on the screen afterwards"


def test_removing_a_source_re_verifies_every_surface_not_only_the_overview():
    """**Remove a source and its citations in chat and in the podcast kept reading as verified.**

    The server re-verifies every saved citation against the smaller corpus (invariants 5 and 11),
    and the remove handler took the new sources, overview and podcast from its response but not the
    TURNS, and re-rendered only the overview. So after ✕ a chat answer and the podcast transcript
    still showed a citation to the removed source as checked — and Copy and Export carried that out
    as verified — while the References panel beside them said unverified. Correct after F5, which
    is what made it look like a flake. Found by an independent review.
    """
    result = _run("removeSourceReverifies")

    assert result["turnVerified"] is False, "the turns were not taken from the server's response"
    assert "chat:rerender" in result["emitted"], "the turns were not re-rendered"
    assert result["refreshed"] >= 1
    for surface in ("turnStroke", "podcastStroke"):
        stroke = result[surface]
        assert "is-unverified" in stroke["cls"].split(), f"{surface} still looks verified: {stroke}"
        assert "Not found in this source" in stroke["title"], f"{surface}'s hover still says verified"
    # A re-stamp numbers a stroke ONCE, on its last fragment. It stamped every fragment, so a claim
    # crossing `*emphasis*` read "¹a ¹parametric¹ model" after any guide or answer arrived.
    assert result["fragments"] == [None, "2"], result["fragments"]


def test_a_orbit_can_leave_the_product_as_an_artifact():
    """**The product could not hand over the thing it exists to produce.**

    `README.md` and `AGENTS.md` both describe the purpose as "get a distilled research artifact out
    the other end", and an independent review counted the export paths across 8,269 lines of
    `app.js`: `navigator.clipboard` appeared ONCE, copying a markdown link's URL; there was no copy
    on an answer, the overview or a Guide kind; no export of any kind; and `@media print` matched
    zero rules, so Cmd+P printed the three-column application shell. The only way out was the
    podcast's audio file — and select-and-copy, which the citation click handler broke by firing on
    the mouseup that ends a drag.

    Markdown, because that is what a reader pastes into, and with the SAME numbered reference list
    the panel shows — so what leaves carries its evidence rather than bare assertions.
    """
    result = _run("exportMarkdown")
    doc = result["orbit"]

    # The whole orbit, in the order a reader would want it.
    for expected in ("# Voyager notes", "## Sources", "## Overview", "## Conversation", "## Notes"):
        assert expected in doc, f"{expected!r} missing from the export:\n{doc}"
    assert "### When did it cross?" in doc, "a turn's question heads its answer"
    assert "In August 2012." in doc
    assert "- check the power budget" in doc, "notes leave with the orbit"

    # References travel with the prose, numbered the way the panel numbers them, and an unverified
    # citation says so — the artifact must not launder a claim that failed verification.
    assert "### References" in doc
    assert "1. Crossing the heliopause · page:2" in doc, "a source is named, not `s1`"
    # A pasted source spanning a blank line stays ONE list item, and its quote stays in the item.
    assert "3. Alpha is first. Beta is second.\n   > Alpha is first. Beta" in doc, doc
    # ...and the internal `pasted:… #hash` origin the interface hides everywhere else stays hidden.
    assert "pasted:" not in doc and "#64f31058" not in doc, doc
    assert "> electron density" in doc, "the quote is the evidence"
    assert "*(unverified)*" in doc, "an unverified citation left the product looking verified"
    # `whole` means "this source has one block" and is noise, exactly as in the hover label.
    assert "· whole" not in doc

    # The Guide kinds have three different shapes and all three come out with their references.
    assert "**Q?**" in result["faq"] and "### References" in result["faq"]
    assert "- **2012**: crossed the heliopause" in result["timeline"]
    # The English heading is the tab's own label, not the internal kind (`## summary`, `## faq`).
    assert result["faq"].startswith("## FAQ\n"), result["faq"]
    assert result["timeline"].startswith("## Timeline\n"), result["timeline"]


def test_the_print_stylesheet_drops_the_shell_and_keeps_the_thread():
    """`@media print` matched ZERO rules, so printing an orbit printed the app: header, facet
    rail, Sources panel, Studio, composer, and a conversation clipped at its scroller. Printing is
    the oldest way anyone takes a research artifact away."""
    import re

    css = (WEB / "style.css").read_text(encoding="utf-8")
    blocks = re.findall(r"@media print\s*\{(.*?)\n\}", css, re.DOTALL)
    assert blocks, "there is no print stylesheet"
    printed = "\n".join(blocks)

    # The chrome goes...
    for chrome in (".header", ".col-sources", ".col-studio", ".ask-form", "#notices", ".skip-link"):
        assert chrome in printed, f"{chrome} still prints"
    # ...the thread stops being a clipped scroller...
    assert ".chat-history" in printed and "overflow: visible" in printed
    # ...and a turn is not split down the middle of a page.
    assert "break-inside: avoid" in printed


def test_strikethrough_renders_as_a_deletion_not_as_tildes():
    """Models write GFM strikethrough, and the hand-written renderer (invariant 55) printed the
    tildes raw: "~~Chunk size~~ is less important than overlap" lost the retraction it meant."""
    parts = _run("markdownInline")["parts"]
    assert "DEL:Chunk size" in parts, parts
    assert not any("~~Chunk" in p for p in parts), parts
    # A lone tilde, or a pair inside a word with nothing to close it, stays plain text.
    assert any("~ alone" in p for p in parts), parts


def test_the_knowledge_graph_layout_is_stable_bounded_and_framed():
    result = _run("graphLayout")
    assert result["same"], "the same orbit drew a different picture on a second layout"
    assert result["inside"], "an entity was placed off the stage"
    assert result["box"]["w"] >= 900 and result["box"]["h"] >= 640, (
        "a small graph was framed tighter than the minimum, which blows its labels up"
    )
    assert result["captureNearAnchors"], "a capture was drawn away from the entities it names"
    assert result["linkedCloser"], "two linked entities ended up further apart than an unlinked one"


def test_the_view_mode_preference_falls_back_to_its_default():
    result = _run("viewModes")
    assert result["fresh"] == ["map", "graph"]
    assert result["stored"] == ["map", "cols"], "a stored value outside the pair was honoured"
    assert result["blocked"] == "graph", "blocked storage broke the default"


def test_a_scope_chip_names_what_it_reads():
    result = _run("scopeLabels")
    assert result["all"] == "Everything"
    assert result["tagHistory"] == "#sleep \u00b7 Sleep"
    assert result["entityChip"] == "Entity: REM"
    assert result["tagChip"] == "#sleep"
    assert result["orbitChip"] == "Orbit: Sleep"


def test_a_running_summary_keeps_its_stop_through_a_redraw():
    result = _run("distilControlSurvivesRedraw")
    assert result["idleOffersSpend"] and not result["idleHasStop"]
    assert result["redrawnHasStop"], "a redraw mid-pass lost the Stop while the pass kept running"
    assert result["redrawnShowsProgress"]
    assert not result["redrawnOffersSpend"], "a redraw mid-pass offered to spend again"


def test_an_orbit_with_a_run_in_flight_opens_in_the_columns():
    result = _run("orbitVisitWithRun")
    assert result["busy"] == "cols"
    assert result["recovered"] == "cols"
    assert result["quiet"] is None, "an orbit with nothing running ignored the reader's preference"
    assert result["empty"] == "cols"


def test_a_refresh_keeps_the_readers_scope_and_plan():
    result = _run("askContextOnRefresh")
    assert result["afterPick"] == "orbit:sleep"
    assert result["afterRefresh"] == {"chosen": "all", "dismissed": 0}, (
        "a background refresh reset the scope the reader chose, or hid their plan"
    )
    assert result["afterLens"] == "tag:x"


def test_a_summarise_control_claims_only_its_own_pass():
    result = _run("distilControlClaimsOnlyItsOwnPass")
    assert "Summarising 2 of 5" in result["mine"]
    assert "Summarising" not in result["other"], "another orbit claimed progress it is not making"
    assert "A summary pass is running." in result["other"]


def test_a_tag_lens_lights_an_orbit_whose_tag_is_outside_its_top_few():
    """The server's `all_tags` has to survive the page building the planet. It did not, so a tag
    named once in an orbit carrying twelve dimmed every planet even after the server was fixed."""
    result = _run("starMapLens")
    assert result["heldTagLit"], "the planet holding the tag was dimmed by its lens"
    assert result["otherTagDim"] and result["emptyOrbitDim"], "a lens must still dim what lacks the tag"
    assert result["noLensLit"] and result["displayStillCapped"]
    assert result["unionLit"], "several lenses combine as a union: any of them lights the planet"
    assert result["moonLit"] == " is-lensed" and result["moonFaded"] == " is-faded"
    assert result["localFaded"] == " is-faded" and result["moonPlain"] == ""


def test_dragging_a_graph_node_pulls_its_neighbours_by_distance_in_links():
    result = _run("graphDrag")
    assert result["B"] == 0.6 and result["E"] == 0.6, "one link away follows most"
    assert result["C"] == 0.3, "two links away follows less"
    assert not result["D"] and not result["A"], "further nodes, and the dragged one, are not pulled"


def test_a_pdf_pages_printed_line_breaks_are_joined_inside_sentences_only():
    result = _run("pdfReflow")
    out = result["out"]
    assert "even commercially." in out, "a break mid-sentence joins with a space"
    assert "space \u200bnext" in out, "a line already ending in a space gets no second one"
    assert "Page 2\u200b License" in out, "a Windows line end joins with one visible space"
    assert "commercially.\n• Adapt" in out, "a list item keeps its line"
    assert "The end.\nUnder" in out, "a line after a sentence ends keeps its break"
    assert "terms\n\nNext" in out, "a blank line is a paragraph"
    assert "中文斷\u200b行" in out, "CJK joins without a visible space"
    assert result["sameLength"], "offsets must not move, or a quote would highlight the wrong words"


def test_a_scraped_page_is_tidied_for_reading_and_quotes_still_land():
    result = _run("tidyText")
    assert result["shown"] == "Top line\n\n募集にあたって\nさらに、経済\nend"
    assert result["highlighted"] == "さらに、経済", "the map must send a quote to the same words"


def test_each_orbit_is_the_same_world_every_visit_and_neighbours_differ():
    result = _run("planetKinds")
    assert result["same"], "an orbit's world must not depend on the order orbits arrive in"
    assert result["distinct"], "while there are kinds to go round, no two planets share one"
    assert result["seeded"], "the generator must be deterministic for a seed"


def test_a_resting_note_shows_the_whole_summary_a_page_at_a_time():
    result = _run("restPages")
    assert result["shortPages"] == ["Sleep consolidates memory. Naps help too."], "short means one page"
    assert result["longPages"] > 1 and result["fits"], "a long one is paged to fit the column"
    assert result["whole"], "paging never drops a word"
    assert result["dwellShort"] == 8000, "never under 8 seconds"
    assert 8000 < result["dwellLong"] <= 30000, "a full page is held long enough to read, not a minute"


def test_the_details_column_opens_for_what_waits_and_closes_when_idle():
    result = _run("panelSettle")
    assert result["opensOverRemembered"], "something waiting must open a column remembered as closed"
    assert result["closesWhenEmpty"], "with nothing waiting the map takes the width"
    assert result["opensWhenSomethingArrives"], "an auto-closed column opens again when something arrives"
    assert result["readerCloseRespected"], "closed by the reader over the same items, it stays closed"
    assert result["opensWhenCountRises"], "a new item opens it again"
    assert result["listClosesIdle"], "the list with nothing chosen gives the column's width back"
    assert result["listKeepsHandOpened"], "a column the reader opened by hand stays open"
    assert result["choosingOpens"], "choosing a capture opens the column for it"
    assert result["closingAfterChoosingCloses"], "closing that capture puts the column away again"


def test_assign_opens_the_orbit_choice_and_needs_an_orbit_to_offer():
    result = _run("filingSettings")
    assert result["hiddenOnManual"], "the orbit choice belongs to assign only"
    assert result["shownOnAssign"], "choosing assign shows the orbit choice"
    assert result["keepsChosenOrbit"] == "cfp", "the saved orbit is the one shown"
    assert result["registered"], "the orbit choice must be saved with the rest"
    assert result["assignDisabledWithoutOrbits"], "assign with nowhere to go must not be offered"


def test_an_automatic_filing_is_announced_once_and_can_be_taken_out():
    result = _run("autoFiledNotices")
    assert result["afterLoad"] == 0, "filings from before the page loaded are already on the map"
    assert result["one"] == [{"message": "Filed automatically into CFP: gitspawn", "action": True}], (
        "one filing names its orbit and offers to take it out"
    )
    assert result["repeat"] == 0, "the same filing is never announced twice"
    assert result["many"] == [{"message": "Filed 2 automatically", "action": False}], (
        "several at once are one counted notice, with no button that could not say which to undo"
    )


def test_a_wikipedia_title_is_shown_without_the_encyclopedias_name():
    assert _run("pageTitles") == ["咖啡", "Aurora", "睡眠", "Rust - A language | Rust",
                                  "Black Hat Cyber Security Conference"]
