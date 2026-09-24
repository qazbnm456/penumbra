"""`intake.py` — the serial capture queue.

No `importorskip`: `intake.py` imports `inbox` and `ingest`, both core (see `test_inbox.py`'s
docstring for the one transitive dependency and why it does not need an extra). Every test injects
a fake `parse`, so nothing here touches the network or a real parser.
"""

from __future__ import annotations

import itertools
import threading
import time
from pathlib import Path

import pytest

from rlm_notebook import inbox
from rlm_notebook.intake import IntakeQueue
from rlm_notebook.schema import Source, SourceBlock


def _parsed(origin: str, node_id: str, *, kind: str = "web", text: str = "body") -> Source:
    return Source(id=node_id, kind=kind, origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


@pytest.fixture
def stopped_queues():
    """Every queue this suite starts gets stopped, or a daemon thread outlives its test and the
    next one sees work it never submitted."""
    made: list[IntakeQueue] = []
    yield made
    for q in made:
        q.stop(timeout=5)


def _queue(stopped_queues, parse) -> IntakeQueue:
    q = IntakeQueue(parse=parse)
    stopped_queues.append(q)
    return q


# --- the capture lands immediately -----------------------------------------------------------------


def test_submit_returns_a_queued_node_before_anything_is_parsed(stopped_queues):
    """**A node exists the moment it is submitted.** The reader sees their capture land instantly;
    a spinner with nothing behind it is not the same thing."""
    started = threading.Event()
    release = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    node = q.submit("https://example.com/a")
    assert node.state == "queued"
    assert node.kind == "web"          # ingest.kind_for's guess, shown until the parse lands
    assert node.chars == 0
    assert inbox.get_node(node.id) is not None

    assert started.wait(5), "the worker never picked the item up"
    release.set()
    assert q.wait_idle(5)


def test_the_worker_stores_the_blocks_and_corrects_the_kind(stopped_queues):
    """`store_blocks` takes `kind` from the parsed `Source`, not from `kind_for`'s guess.

    This used to say the shipped parsers could not produce the correction it tests, because
    `parse_web` hardcoded `kind="web"`. That stopped being true when content-type sniffing landed:
    a URL serving a PDF really is filed `web` at capture and really does come back `pdf`, so this
    pins a correction that HAPPENS rather than a defence against a hypothetical.
    `test_a_pdf_url_is_parsed_as_a_pdf_not_refused_as_an_empty_page` drives the real path."""
    q = _queue(stopped_queues, lambda o, n: _parsed(o, n, kind="pdf", text="twelve chars"))
    node = q.submit("https://example.com/looks-like-a-page")
    assert q.wait_idle(5)

    done = inbox.get_node(node.id)
    assert done.state == "ready_undistilled"
    assert done.kind == "pdf", "the parse must correct kind_for's guess"
    assert done.chars == len("twelve chars")
    assert inbox.node_source(node.id).blocks[0].text == "twelve chars"


def test_the_worker_marks_a_node_parsing_while_it_works_on_it(stopped_queues):
    """Observed from INSIDE the parse, because that is the only moment it is true.

    Nothing used to watch this, so deleting the `state="parsing"` write left the suite green — and
    `resume_interrupted` exists entirely to recover nodes stranded in that state. A state nothing
    proves is ever written is a state nothing proves is worth recovering.
    """
    observed: list[str] = []

    def parse(origin, node_id):
        observed.append(inbox.get_node(node_id).state)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    node = q.submit("https://example.com/a")
    assert q.wait_idle(5)

    assert observed == ["parsing"]
    assert inbox.get_node(node.id).state == "ready_undistilled"


# --- serial, which is the whole point ----------------------------------------------------------------


def test_items_are_parsed_one_at_a_time(stopped_queues):
    """**Invariant 3, and it is not a performance choice.** Four PDFs parsed at once died with
    `rc=134` (SIGABRT) because PDFium is not thread-safe, and dropping a folder or a bookmarks
    export is exactly the shape that would drive many at once. So: no overlap, ever."""
    windows: list[tuple[float, float]] = []
    recorder = threading.Lock()

    def parse(origin, node_id):
        start = time.monotonic()
        time.sleep(0.05)
        with recorder:
            windows.append((start, time.monotonic()))
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    for n in range(5):
        q.submit(f"https://example.com/{n}")
    assert q.wait_idle(10)

    assert len(windows) == 5
    ordered = sorted(windows)
    for (_, end), (start, _) in itertools.pairwise(ordered):
        assert start >= end, f"two captures overlapped by {end - start:.3f}s"


# --- failure is a state, never a lost capture ---------------------------------------------------------


def test_a_parse_failure_keeps_the_message_and_the_worker_survives(stopped_queues):
    """A dead link and an unparseable PDF are different problems, and a reader who cannot tell them
    apart cannot act on either. And one bad item must not end intake for everything after it."""
    def parse(origin, node_id):
        if "bad" in origin:
            raise ValueError("404 while fetching")
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    bad = q.submit("https://example.com/bad")
    good = q.submit("https://example.com/good")
    assert q.wait_idle(5)

    failed = inbox.get_node(bad.id)
    assert failed.state == "failed"
    assert "404 while fetching" in failed.error
    assert inbox.get_node(good.id).state == "ready_undistilled", "the worker died on the first item"


def test_resubmitting_a_failed_node_retries_it(stopped_queues):
    """"Try that again" is a submit, not a second verb — and the old error must not survive a
    successful retry."""
    attempts: list[str] = []

    def parse(origin, node_id):
        attempts.append(origin)
        if len(attempts) == 1:
            raise ValueError("transient")
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    node = q.submit("https://example.com/flaky")
    assert q.wait_idle(5)
    assert inbox.get_node(node.id).state == "failed"

    q.submit("https://example.com/flaky")
    assert q.wait_idle(5)
    retried = inbox.get_node(node.id)
    assert retried.state == "ready_undistilled"
    assert retried.error is None, "a successful retry must clear the old message"
    assert len(attempts) == 2


# --- idempotence, cancellation, resume -----------------------------------------------------------------


def test_submitting_the_same_origin_twice_parses_once(stopped_queues):
    parses: list[str] = []
    q = _queue(stopped_queues, lambda o, n: (parses.append(o), _parsed(o, n))[1])

    first = q.submit("https://example.com/a")
    assert q.wait_idle(5)
    second = q.submit("https://example.com/a")
    assert q.wait_idle(5)

    assert first.id == second.id
    assert parses == ["https://example.com/a"]
    assert inbox.count_nodes() == 1


def test_cancel_pending_lands_the_waiting_items_as_stopped(stopped_queues):
    """**They used to stay `queued`, and that was invariant 79's own failure mode.**

    "Nothing was parsed, so nothing is lost, and `resume_interrupted` can pick them up later" was
    true only across a RESTART, which is not a thing a reader does. In the meantime an independent
    reviewer watched three nodes sit at `queued` forever: drawn identically to a node still being
    read, with the page polling at 2.2 requests a second because `queued` counts as busy, offering
    no Try again (that is `failed`-only) and answering an open with a raw
    `404: node '...' has no stored text yet`. Invariant 79's sentence is that a permanent `queued`
    "looks exactly like still working" — it was.

    A dropped item now lands somewhere TRUE and ACTIONABLE. Not a parse failure, and the message
    says so, but the same shape: terminal, visible, and retryable through `submit`'s existing
    failed-node reset, so the row's Try again works with no new endpoint.
    """
    release = threading.Event()
    started = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    first = q.submit("https://example.com/0")
    assert started.wait(5)
    waiting = [q.submit(f"https://example.com/{n}") for n in range(1, 4)]

    assert q.cancel_pending() == 3
    release.set()
    assert q.wait_idle(5)

    assert inbox.get_node(first.id).state == "ready_undistilled", "the in-flight item still finished"
    stopped = [inbox.get_node(n.id) for n in waiting]
    assert [n.state for n in stopped] == ["failed"] * 3, "a dropped item may not look like a live one"
    assert all(n.error == "stopped before it was read" for n in stopped), [n.error for n in stopped]
    # And the retry path reaches them: `submit` resets a `failed` node to `queued`.
    assert q.submit(waiting[0].origin).state == "queued"


def test_resume_picks_up_queued_and_interrupted_work_but_not_failures(stopped_queues):
    """`parsing` is a lie once the process that owned it is gone, so it is reset. `failed` is NOT
    resumed: retrying a parse that failed on its own terms, on every restart, is how a poisoned
    item becomes a loop."""
    q = _queue(stopped_queues, lambda o, n: _parsed(o, n))
    stale_queued = inbox.add_pending_node("https://example.com/q", "web")
    stale_parsing = inbox.add_pending_node("https://example.com/p", "web")
    inbox.update_node(stale_parsing.id, state="parsing")
    dead = inbox.add_pending_node("https://example.com/f", "web")
    inbox.update_node(dead.id, state="failed", error="gone")

    resumed = q.resume_interrupted()
    assert set(resumed) == {stale_queued.id, stale_parsing.id}
    assert q.wait_idle(5)

    assert inbox.get_node(stale_queued.id).state == "ready_undistilled"
    assert inbox.get_node(stale_parsing.id).state == "ready_undistilled"
    assert inbox.get_node(dead.id).state == "failed"


def test_a_node_removed_while_queued_is_skipped_rather_than_an_error(stopped_queues, caplog):
    """The reader changed their mind. That is not a failure, and it must not stop the item after
    it."""
    release = threading.Event()
    started = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    blocker = q.submit("https://example.com/0")
    assert started.wait(5)
    doomed = q.submit("https://example.com/1")
    survivor = q.submit("https://example.com/2")

    inbox.remove_node(doomed.id)
    release.set()
    assert q.wait_idle(5)

    assert inbox.get_node(doomed.id) is None
    assert inbox.get_node(blocker.id).state == "ready_undistilled"
    assert inbox.get_node(survivor.id).state == "ready_undistilled"
    # The "rather than an error" half, which was previously unasserted: `_run`'s blanket handler
    # swallows anything `_process` raises, so replacing the guard with a `raise` left the suite
    # green. The log record is the only observable difference.
    assert "unhandled error" not in caplog.text


# --- the status line may not lie (invariant 60) ---------------------------------------------------------


def test_status_reports_what_is_actually_happening(stopped_queues):
    release = threading.Event()
    started = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    assert q.status() == {"running": False, "current": None, "pending": 0}

    first = q.submit("https://example.com/0")
    assert started.wait(5)
    q.submit("https://example.com/1")

    mid = q.status()
    assert mid["running"] is True
    assert mid["current"] == first.id
    assert mid["pending"] == 1

    release.set()
    assert q.wait_idle(5)
    assert q.status()["current"] is None


def test_stop_is_safe_on_a_queue_that_never_started():
    IntakeQueue(parse=lambda o, n: _parsed(o, n)).stop(timeout=1)


def test_an_empty_origin_is_refused_rather_than_hashed(stopped_queues):
    """Queueing "nothing" has no meaning, and `node_id_for`'s content fallback needs content, which
    by definition does not exist before the parse."""
    q = _queue(stopped_queues, lambda o, n: _parsed(o, n))
    with pytest.raises(ValueError, match="needs an origin"):
        q.submit("   ")


# --- regressions found by an independent review ---------------------------------------------------


def test_a_failure_anywhere_in_processing_never_leaves_a_node_parsing(stopped_queues, monkeypatch):
    """**`parsing` means "a worker owns this right now".** A node left in it after the worker moved
    on is invariant 79's worst available failure: it looks exactly like still working, and only a
    restart clears it.

    `get_node`, the `parsing` write and `store_blocks` all used to sit OUTSIDE `_process`'s `try`.
    Measured with a raising `store_blocks`: `state='parsing', error=None`.
    """
    def boom(*args, **kwargs):
        raise OSError("ENOSPC")

    monkeypatch.setattr(inbox, "store_blocks", boom)
    q = _queue(stopped_queues, lambda o, n: _parsed(o, n))
    node = q.submit("https://example.com/a")
    assert q.wait_idle(5)

    got = inbox.get_node(node.id)
    assert got.state == "failed"
    assert "ENOSPC" in got.error


def test_even_a_baseexception_from_the_parser_is_recorded(stopped_queues):
    """`_process` catches `Exception`; `_run` is the backstop for everything else. Recording in both
    is what makes "never left at `parsing`" a property of the WORKER rather than of one function's
    exception list."""
    def boom(origin, node_id):
        raise KeyboardInterrupt("from inside the parser")

    q = _queue(stopped_queues, boom)
    node = q.submit("https://example.com/a")
    assert q.wait_idle(5)
    assert inbox.get_node(node.id).state == "failed"


def test_a_node_removed_during_its_parse_leaves_no_orphan_blocks(stopped_queues):
    """**Silent wrong content, not just a leaked file.** `add_node` ADOPTS an orphan blocks file
    (that branch exists for a crash between the two writes), so a blocks file left behind by a
    removed node is handed to the next capture of the same origin. Measured: a re-capture with 10
    characters of fresh text reported `chars=4`, the length of the orphan."""
    started = threading.Event()
    release = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id, text="OLD4")

    q = _queue(stopped_queues, parse)
    node = q.submit("https://example.com/x")
    assert started.wait(5)
    inbox.remove_node(node.id)
    release.set()
    assert q.wait_idle(5)

    assert not inbox.node_blocks_path(node.id).exists(), "an orphan the next capture would adopt"
    recaptured = inbox.add_node(_parsed("https://example.com/x", "s0", text="NEW-TEN-CH"))
    assert recaptured.chars == len("NEW-TEN-CH"), "a stale orphan was adopted"


def test_resume_does_not_re_enqueue_what_is_already_waiting(stopped_queues):
    """Measured before the fix: two submits plus a resume produced FOUR parse calls for two
    origins — two network fetches or two PDFium passes each."""
    calls: list[str] = []
    started = threading.Event()
    release = threading.Event()

    def parse(origin, node_id):
        calls.append(origin)
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    q.submit("https://example.com/a")
    q.submit("https://example.com/b")
    assert started.wait(5)
    assert q.resume_interrupted() == [], "everything was already queued"
    release.set()
    assert q.wait_idle(5)
    assert len(calls) == 2, calls


def test_status_never_denies_work_while_naming_a_node(stopped_queues):
    """Invariant 60. The old `status()` read `qsize()`, which counts the stop sentinel and reads
    zero between the worker's `get()` and its first state write — so it reported
    `{"running": False, "current": "nd-…", "pending": 1}`, denying and naming in one dict."""
    started = threading.Event()
    release = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    q.submit("https://example.com/s")
    assert started.wait(5)

    stopper = threading.Thread(target=lambda: q.stop(timeout=2))
    stopper.start()
    time.sleep(0.2)
    reported = q.status()
    release.set()
    stopper.join()

    assert not (reported["current"] is not None and reported["running"] is False), reported


def test_the_worker_resolves_its_directory_once_and_does_not_follow_a_chdir(stopped_queues, tmp_path):
    """One node SPLIT ACROSS TWO DIRECTORIES was the measured symptom: the row under the old cwd
    saying `ready_undistilled`, the blocks under the new one — exactly the "renders and then fails
    to open" state `store_blocks`'s ordering comment says must never exist."""
    import os

    here = Path(os.getcwd())
    elsewhere = tmp_path / "next-test"
    elsewhere.mkdir()
    release = threading.Event()

    q = _queue(stopped_queues, lambda o, n: (release.wait(5), _parsed(o, n))[1])
    node = q.submit("https://example.com/a")
    time.sleep(0.1)
    os.chdir(elsewhere)
    try:
        release.set()
        assert q.wait_idle(5)
    finally:
        os.chdir(here)

    assert (here / "inbox" / "nodes" / f"{node.id}.json").exists()
    assert not (elsewhere / "inbox").exists(), "the worker followed the chdir"


def test_stop_racing_submit_never_starts_a_second_worker(stopped_queues):
    """**Invariant 3's forbidden shape, reached from inside the thing built to prevent it.** The old
    `stop()` cleared `_thread`, released `_guard`, and only then enqueued the sentinel; a `submit()`
    in that window started worker #2. Measured consequence: −0.155s between consecutive parse
    windows, i.e. real overlap."""
    seen: set[str] = set()

    def watch(stop_watching):
        while not stop_watching.is_set():
            seen.update(t.name for t in threading.enumerate() if t.name.startswith("rlm-intake"))

    for attempt in range(25):
        q = _queue(stopped_queues, lambda o, n: _parsed(o, n))
        q.submit(f"https://example.com/warm-{attempt}")
        stop_watching = threading.Event()
        watcher = threading.Thread(target=watch, args=(stop_watching,))
        watcher.start()
        # A submit that LOSES the race now raises rather than handing back a `queued` node nothing
        # will parse - see `test_a_stopped_queue_refuses_a_capture_instead_of_promising_one`. That
        # is the correct outcome here and is not what this test is about, so it is swallowed rather
        # than left to surface as an unhandled thread exception.
        def racing_submit(queue: IntakeQueue = q, which: int = attempt) -> None:
            try:
                queue.submit(f"https://example.com/{which}")
            except RuntimeError:
                pass

        racers = [
            threading.Thread(target=q.stop, kwargs={"timeout": 2}),
            threading.Thread(target=racing_submit),
        ]
        for t in racers:
            t.start()
        for t in racers:
            t.join()
        stop_watching.set()
        watcher.join()

    # Every queue names its worker "rlm-intake", so two live at once on ONE queue is the failure —
    # and each iteration builds a fresh queue, so a second NAME never appears unless one spawned two.
    assert seen <= {"rlm-intake"}, seen


def test_stop_is_terminal_and_reports_whether_the_worker_ended():
    """A stopped queue does not restart — `_ensure_worker` refuses under `_stopping`. And `stop()`
    RETURNS the answer, so an ASGI shutdown hook can pass a short timeout and read it rather than
    blocking for the full two minutes on a scanned PDF."""
    q = IntakeQueue(parse=lambda o, n: _parsed(o, n))
    assert q.stop(timeout=1) is True, "stopping a queue that never ran is not a failure"

    q2 = IntakeQueue(parse=lambda o, n: _parsed(o, n))
    q2.submit("https://example.com/a")
    assert q2.wait_idle(5)
    assert q2.stop(timeout=5) is True
    assert q2.status()["running"] is False


def test_cancel_pending_drains_past_the_stop_sentinel(stopped_queues):
    """The `_STOP` branch had ZERO coverage, and it was wrong: breaking on the sentinel left
    everything BEHIND it queued AND still counted, so `wait_idle` never returned — measured
    `dropped=1, qsize=2, _outstanding=1` on a queue holding `[node, _STOP, node]`."""
    from rlm_notebook.intake import _STOP

    started = threading.Event()
    release = threading.Event()

    def parse(origin, node_id):
        started.set()
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, parse)
    q.submit("https://example.com/0")
    assert started.wait(5)

    first = q.submit("https://example.com/1")
    q._queue.put(_STOP)          # a stop landing between two waiting items
    second = q.submit("https://example.com/2")

    assert q.cancel_pending() == 2, "the item behind the sentinel was stranded"
    release.set()
    assert q.wait_idle(5), "_outstanding never reached zero for the stranded item"
    assert [inbox.get_node(n.id).state for n in (first, second)] == ["failed", "failed"]


def test_submit_returns_a_node_even_if_the_row_vanishes_mid_reset(stopped_queues, monkeypatch):
    """`inbox.update_node` returns `None` when the row is gone, and `submit` is annotated `-> Node`.
    A caller writing `submit(url).id` must not get an `AttributeError` because the reader removed
    the node in the window between `add_pending_node` and the failed-state reset."""
    q = _queue(stopped_queues, lambda o, n: _parsed(o, n))
    node = q.submit("https://example.com/a")
    assert q.wait_idle(5)
    inbox.update_node(node.id, state="failed", error="earlier failure")

    monkeypatch.setattr(inbox, "update_node", lambda *args, **kwargs: None)
    again = q.submit("https://example.com/a")
    assert again is not None, "submit returned None under a non-optional annotation"
    assert again.id == node.id

def test_resubmitting_a_failed_origin_is_the_retry_path(stopped_queues):
    """**"Try again" has no endpoint of its own — `submit` IS the retry**, and until now nothing
    tested the line that makes it one.

    `intake.submit` resets a node that previously FAILED back to `queued` and re-enqueues it. An
    independent reviewer neutered that single `if node.state == "failed":` branch and ran
    `test_intake.py` + `test_api_inbox.py`: 52 passed, green. The only button offered on a failed
    row would have done nothing at all, and the row would have kept its old error beside a state
    that looked like progress.

    Also pins the two things the reset has to do, because a half-reset is its own bug: the STATE
    goes back to `queued`, and the stale `error` goes away rather than sitting next to a fresh
    attempt.
    """
    attempts: list[str] = []

    def flaky(origin: str, node_id: str) -> Source:
        attempts.append(origin)
        if len(attempts) == 1:
            raise ValueError("first attempt fails")
        return _parsed(origin, node_id, text="it worked the second time")

    q = _queue(stopped_queues, flaky)
    node = q.submit("https://example.com/flaky")
    assert q.wait_idle(5)
    failed = inbox.get_node(node.id)
    assert failed.state == "failed" and failed.error

    # The SAME origin again. Same node (identity is content-derived), reset and retried.
    again = q.submit("https://example.com/flaky")
    assert again.id == node.id, "a retry must not mint a second node for one origin"
    assert again.state == "queued", "a failed node must be reset, or the retry enqueues nothing"
    assert again.error is None, "the old message must not sit beside a fresh attempt"

    assert q.wait_idle(5)
    healed = inbox.get_node(node.id)
    assert healed.state == "ready_undistilled"
    assert healed.error is None
    assert attempts == ["https://example.com/flaky"] * 2


# --- the two things a long task on this thread asks the queue --------------------------------------


def test_a_long_task_on_the_queues_thread_can_see_a_capture_waiting(stopped_queues):
    """**`has_pending_work` is how the summary batch YIELDS**, and it had no test at all.

    The idle hook runs on this queue's own thread, so anything it does blocks every capture behind
    it. Without the yield a capture arriving mid-batch sat at `queued` for the whole batch, measured
    at 2.6s with one stand-in call and a minute or more at the real default of 20 — and "queued"
    looks exactly like "still working", which is the thing invariant 79 exists to prevent.

    Both arms matter and neither was pinned: mutating `_auto_distil_after_intake`'s `should_stop`
    down to `return stopped` — dropping this AND the cancel-generation arm — left the whole suite
    green.
    """
    release = threading.Event()

    def slow(origin: str, node_id: str) -> Source:
        release.wait(5)
        return _parsed(origin, node_id)

    q = _queue(stopped_queues, slow)
    assert q.has_pending_work() is False, "an untouched queue has nothing outstanding"

    q.submit("https://example.com/slow")
    for _ in range(200):
        if q.has_pending_work():
            break
        time.sleep(0.01)
    assert q.has_pending_work() is True, "a submitted capture must be visible as outstanding work"

    # A SECOND capture while the first is still parsing: this is the state the hook yields for.
    q.submit("https://example.com/behind-it")
    assert q.has_pending_work() is True

    release.set()
    assert q.wait_idle(5)
    assert q.has_pending_work() is False, "an idle queue must report no outstanding work, or the "
    "summary batch yields forever and no capture is ever summarised"


def test_cancel_bumps_a_generation_a_running_batch_can_compare(stopped_queues):
    """**`cancel_generation` is how Stop reaches work that is not IN the FIFO.**

    The summary batch runs on this queue's thread, so draining the FIFO cannot touch it. It captures
    this number when it starts and compares it between nodes; a bump is the signal to stop. It is
    bumped even when the FIFO is EMPTY, which is the case that matters — a Stop pressed during a
    summary pass has nothing queued to drain.
    """
    q = _queue(stopped_queues, lambda origin, node_id: _parsed(origin, node_id))
    before = q.cancel_generation
    assert q.cancel_pending() == 0, "nothing is queued, so nothing is dropped"
    assert q.cancel_generation == before + 1, (
        "a Stop with an empty FIFO must still bump the generation, or it cannot reach the summary "
        "batch running on this queue's own thread"
    )
    assert q.cancel_pending() == 0
    assert q.cancel_generation == before + 2, "each Stop is its own generation"


def test_a_stopped_queue_refuses_a_capture_instead_of_promising_one(stopped_queues):
    """**A `queued` node nothing will ever parse is invariant 79's named failure.**

    `nudge()` guarded on `_stopping` and `submit` did not, so a capture racing ASGI shutdown got a
    node back in the state the invariant calls out by name ("a permanent `queued` — which looks
    exactly like still working"), and leaked `_outstanding` on the way out. Narrow in the shipped
    server, because `intake.shared()` rebuilds a stopped queue per request; every defect found in
    this file has been narrow.
    """
    q = _queue(stopped_queues, lambda origin, node_id: _parsed(origin, node_id))
    assert q.submit("https://example.com/before").state in ("queued", "ready_undistilled")
    assert q.wait_idle(5)

    q.stop(timeout=5)
    assert q.stopped

    with pytest.raises(RuntimeError, match="stopped"):
        q.submit("https://example.com/after")
    assert q.has_pending_work() is False, "a refused capture must not leak outstanding work"


def test_a_stop_landing_mid_submit_does_not_leave_a_node_nothing_will_parse(stopped_queues):
    """**`submit`'s own stopped check releases its lock before the enqueue**, so a `stop()` in that
    window let a node through: `_ensure_worker` correctly refused to start a worker while
    `_outstanding` had already been incremented and the id put on the queue. A permanent `queued`
    node — invariant 79's named failure — plus a leaked counter, so `wait_idle` never returns and
    `status()` reports running forever.

    Driven through the seam rather than by racing threads, because a race test that passes because
    it lost the race is worth nothing: `_enqueue` is called with the queue already stopped, which is
    exactly the state the window produces.
    """
    q = _queue(stopped_queues, lambda origin, node_id: _parsed(origin, node_id))
    node = inbox.add_pending_node("https://example.com/mid-stop", "web", base_dir=q.base_dir)
    q.stop(timeout=5)

    assert q._enqueue(node.id) is False, (
        "a stopped queue accepted work; `_ensure_worker` will refuse it and the counter leaks"
    )
    assert q.has_pending_work() is False, "the outstanding counter leaked on a refused enqueue"
    assert q.wait_idle(2), "wait_idle never returns once the counter has leaked"


def test_submit_itself_refuses_on_a_stopped_queue(stopped_queues):
    """**`submit`'s OWN stopped check, which `_enqueue`'s guard makes redundant on the happy path.**

    Both exist deliberately: `submit` refuses early so a stopped queue never even writes a `queued`
    row, and `_enqueue` closes the window between `submit`'s check and the enqueue. Removing
    `submit`'s left the suite green, because `_enqueue` caught everything the test drove — so the
    early refusal, and the fact that no ROW is created, had nothing pinning them.
    """
    from rlm_notebook import inbox as inbox_mod

    q = _queue(stopped_queues, lambda origin, node_id: _parsed(origin, node_id))
    q.stop(timeout=5)
    before = inbox_mod.count_nodes(base_dir=q.base_dir)

    with pytest.raises(RuntimeError, match="stopped"):
        q.submit("https://example.com/after-stop")

    assert inbox_mod.count_nodes(base_dir=q.base_dir) == before, (
        "a stopped queue wrote a node row before refusing - the row is the thing invariant 79 calls "
        "a permanent `queued`, and it is now there with nothing to parse it"
    )


def test_the_two_locks_are_always_taken_in_the_same_order(tmp_path):
    """A lock-order inversion is a deadlock with nothing to time out, and it was real here.

    `_enqueue` took `_idle` then `_guard`; `stop` and `cancel_pending` hold `_guard` across
    `_drain`, which reaches `_idle` through `_finish_one`. Two threads, opposite orders, each
    waiting on what the other holds — and an ASGI shutdown blocking on the join behind them.

    Racing for it is the wrong test: the window is a few instructions wide, so a green run would
    mean nothing. This asserts the PROPERTY instead. Both locks are wrapped in a proxy that records
    what each thread holds when it takes another, and any pair seen in both orders fails — which
    catches a reintroduction anywhere in the class, not just in the function that had the bug.
    """
    import threading

    from rlm_notebook.intake import IntakeQueue

    pairs: set[tuple[str, str]] = set()
    held: dict[int, list[str]] = {}
    record_lock = threading.Lock()

    class Tracked:
        def __init__(self, name, inner):
            self._name, self._inner = name, inner

        def __enter__(self):
            mine = held.setdefault(threading.get_ident(), [])
            with record_lock:
                for outer in mine:
                    pairs.add((outer, self._name))
            mine.append(self._name)
            return self._inner.__enter__()

        def __exit__(self, *exc):
            held[threading.get_ident()].pop()
            return self._inner.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    queue = IntakeQueue(base_dir=tmp_path / "inbox")
    queue._guard = Tracked("guard", queue._guard)
    queue._idle = Tracked("idle", queue._idle)
    try:
        for i in range(5):
            queue.submit(f"https://example.com/{i}")
        queue.cancel_pending()
        for i in range(5, 8):
            queue.submit(f"https://example.com/{i}")
    finally:
        queue.stop()

    assert pairs, "no nesting was ever observed, so this test proves nothing"
    inversions = {(a, b) for (a, b) in pairs if (b, a) in pairs}
    assert not inversions, (
        f"locks taken in both orders: {sorted(inversions)} — a deadlock with no timeout behind it"
    )
    assert pairs == {("guard", "idle")}, f"the module's order is guard-then-idle, saw {sorted(pairs)}"
