"""The Horizon's intake queue: one worker, one item at a time.

`horizon.py` stores nodes; this is what fills them. The two are separate because parsing is
invariant 3's host-side, SERIAL business and storage is not — and because a storage layer that
owned a thread would be untestable without one.

The rules, argued in `docs/invariants/79-a-capture-always-lands.md` rather than restated here: a
capture lands as a `queued` node before anything is fetched, a parse failure is a `failed` node that
keeps its message, and intake runs ONE item at a time. The incidents are in `CHANGELOG.md`.

**Single-process, like `api._ACTIVE_RUNS`** (invariant 23). Two `uvicorn` workers would each get
their own queue and their own worker thread; the SQLite index underneath them is safe across
processes, the queue is not. Documented rather than defended, exactly as invariant 23 does.

## Two things a reader of THIS file has to hold onto

**Every state change goes through `_process`, and `_process` cannot leave a node at `parsing`.**
That state means "a worker owns this right now", so a node left in it after the worker moved on is
the exact failure invariant 79 names as the worst available: it looks exactly like still working.
Measured before it was fixed — a `store_blocks` that raised left `state='parsing', error=None`,
recoverable only by a restart — which is why `_run` records a failure even for a `BaseException`
`_process` did not expect.

**`stop()` is terminal and `cancel_pending()` is not.** Stopping sets `_stopping` under `_guard`,
drains, and enqueues the sentinel WITHOUT releasing the lock in between — an earlier version cleared
`_thread` first and released, and a `submit()` landing in that window started a SECOND worker,
reaching invariant 3's forbidden shape from inside the thing built to prevent it (measured: −0.155s
between consecutive parse windows, i.e. real overlap).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from pathlib import Path

from . import horizon
from .ingest import ingest_one, kind_for, with_injection_flags
from .schema import Node, Source

_log = logging.getLogger(__name__)

#: Put on the queue to end the worker loop. A sentinel object rather than `None`, so a bug that
#: enqueues `None` fails loudly instead of quietly shutting intake down. Only `stop()` ever puts
#: one, and only while holding `_guard` with a live worker — so it can never be stranded in an
#: empty queue waiting to kill the NEXT worker that starts.
_STOP = object()

#: "Nothing to parse, but check whether the idle hook should run." Enqueued by `nudge()`.
#:
#: A distinct sentinel rather than a flag on a node id, because the two differ in the thing that
#: matters: a nudge is NOT outstanding work. It never enters `_outstanding`, so `status()` never
#: reports the queue as running because of one, and `_maybe_idle`'s `_outstanding == 0` test - the
#: whole point of the exercise - stays true while it is being handled.
_NUDGE = object()

#: How long `stop()` waits by default. Generous because the in-flight item may be a scanned PDF
#: going through OCR, and killing that thread is not an option — the choice is between waiting and
#: lying about having stopped. `stop()` RETURNS whether the worker actually ended, so a caller that
#: cannot wait (an ASGI shutdown hook) passes a short timeout and reads the answer; the worker is a
#: daemon thread, so process exit collects it either way.
_JOIN_TIMEOUT = 120.0

ParseFn = Callable[[str, str], Source]


def default_parse(origin: str, node_id: str) -> Source:
    """`ingest_one` plus the injection scan, which is the combination every other entry point uses.

    Invariant 6's flags are ADDITIVE metadata and gate nothing, but they have to be applied on every
    path a source can enter by — `ingest.with_injection_flags` exists because that had already been
    forgotten once."""
    return with_injection_flags(ingest_one(origin, node_id))


class IntakeQueue:
    """One worker thread draining a FIFO. Construct one per horizon directory; the API holds a
    singleton (`shared`), and tests construct their own with a fake `parse`."""

    def __init__(
        self,
        *,
        base_dir: str | Path = horizon.DEFAULT_HORIZON_DIR,
        parse: ParseFn | None = None,
        on_idle: Callable[[], None] | None = None,
    ) -> None:
        #: RESOLVED once, here, and never re-resolved. `horizon.horizon_dir` builds a `Path` from
        #: whatever it is handed, so a relative `"horizon"` would be resolved against the process's
        #: CURRENT working directory on every syscall — on the WORKER thread, which outlives any
        #: single call. Measured: hold a worker inside `parse`, `chdir` elsewhere, release, and one
        #: node ends up SPLIT ACROSS TWO DIRECTORIES — the row under the old cwd saying
        #: `ready_undistilled`, the blocks under the new one. That is exactly the "renders and then
        #: fails to open" state `store_blocks`'s ordering comment says must never exist. Resolving
        #: once is also the only reading that makes invariant 34's "where you START this decides
        #: where your data lives" true for a thread.
        self._base_dir = Path(base_dir).resolve()
        self._parse = parse or default_parse
        #: Called on the WORKER thread once the queue goes empty. This module deliberately knows
        #: nothing about what it does — the auto-summary policy belongs to whoever configures the
        #: queue, and keeping it out here is what makes invariant 80's "intake makes no model call"
        #: a STRUCTURAL fact (`intake.py` imports nothing model-related) rather than a promise.
        #: Anything it raises is logged and swallowed: a policy hook must not end intake.
        self._on_idle = on_idle
        #: Called on the WORKER thread after a node's blocks are stored. Same contract as `_on_idle`:
        #: the policy (filing into the landing orbit) belongs to whoever configures the queue, and
        #: anything it raises is logged and swallowed, because a capture that parsed has landed.
        self._on_ready: Callable[[str], None] | None = None
        self._queue: queue.Queue[object] = queue.Queue()
        self._thread: threading.Thread | None = None
        #: Guards `_thread`, `_stopping`, and the pairing of "drain" with "enqueue the sentinel".
        self._guard = threading.RLock()
        self._stopping = False
        self._cancel_generation = 0
        self._current: str | None = None
        #: Submitted but not yet finished, and the ids currently in the queue. NOT
        #: `Queue.unfinished_tasks` (undocumented) and NOT `qsize()` (reads zero in the window
        #: between the worker's `get()` and its first state write, and counts the sentinel).
        #: `_queued` is what stops `resume_interrupted` re-enqueueing something already waiting,
        #: which used to parse it twice.
        self._idle = threading.Condition()
        self._outstanding = 0
        self._queued: set[str] = set()

    # -- submitting -------------------------------------------------------------------------------

    def submit(self, origin: str) -> Node:
        """Capture `origin`, returning the node immediately — parsed or not.

        Idempotent through `add_pending_node`, which is idempotent through `node_id_for`: submitting
        a URL already in the Horizon returns the node that is there rather than queueing it twice. A
        node that previously FAILED is reset to `queued` and retried, which is what makes "try that
        again" a submit rather than a second verb.
        """
        # **A STOPPED queue refuses, rather than handing back a `queued` node nothing will parse.**
        # `nudge()` already guards on this; `submit` did not, so a capture racing ASGI shutdown
        # returned a node in the state invariant 79 calls the failure mode ("a permanent `queued` —
        # which looks exactly like still working"), and leaked `_outstanding` on the way. Narrow in
        # the shipped server, because `intake.shared()` rebuilds a stopped queue per request — but
        # "narrow" is what every one of these has been.
        #
        # Raised, not returned: the caller has an HTTP response to write and a node it must not
        # pretend was captured. `RuntimeError` rather than a new class, because the only honest
        # thing to say is that this queue is finished.
        with self._guard:
            if self._stopping:
                raise RuntimeError("this intake queue has been stopped and cannot accept captures")
        node = horizon.add_pending_node(origin, kind_for(origin), base_dir=self._base_dir)
        if node.state == "failed":
            # `update_node` returns None if the row vanished in this window. Keep the node we
            # already have rather than returning None under a non-optional annotation; `_process`
            # handles a node that is gone by the time it is picked up.
            node = horizon.update_node(node.id, base_dir=self._base_dir, state="queued", error=None) or node
        if node.state in ("queued", "failed") and not self._enqueue(node.id):
            # `_enqueue` refuses on a queue that stopped in the window `submit`'s own check cannot
            # cover. Say so rather than handing back a node nothing will ever parse.
            with self._guard:
                stopping = self._stopping
            if stopping:
                raise RuntimeError("this intake queue has been stopped and cannot accept captures")
        return node

    @property
    def base_dir(self) -> Path:
        """The RESOLVED horizon directory. Exposed because anything running on this queue's thread —
        the idle hook, for instance — has to use the same one: re-deriving a relative path there
        would undo exactly what `__init__` resolves once to prevent."""
        return self._base_dir

    @property
    def cancel_generation(self) -> int:
        """Bumped by every `cancel_pending`. A long task running on this queue's thread captures it
        and compares, which is how a Stop reaches work that is not in the FIFO."""
        with self._guard:
            return self._cancel_generation

    def has_pending_work(self) -> bool:
        """Whether anything is queued or in flight. A hook running on the worker thread checks this
        to YIELD: without it, a capture arriving mid-batch sat at `queued` for the whole batch —
        measured at 2.6s with one stand-in call, and a minute or more at the real default of 20."""
        with self._idle:
            return self._outstanding > 0

    @property
    def stopped(self) -> bool:
        """Whether `stop()` has been called. A stopped queue refuses to start a worker ever again,
        so anything holding one has to be able to ask — see `shared()`."""
        with self._guard:
            return self._stopping

    def nudge(self) -> None:
        """Ask the idle hook to run, on THIS QUEUE'S THREAD, without anything to parse.

        **Two capture paths never touch this queue**, and both are deliberate: pasted text and an
        uploaded file are already bytes in hand, so `capture_into_horizon` and the upload handler
        store them directly rather than making the reader watch a FIFO for something that takes
        microseconds. The cost was invisible until the auto-summary path was tested end to end: the
        hook fires when the QUEUE goes idle, a queue that was never busy never goes idle, and an
        operator who turned the toggle on got nothing at all for a paste or a drop - the two most
        common captures on a surface whose whole promise is "throw anything in". Their nodes sat at
        `ready_undistilled` until some unrelated URL capture happened to sweep them up.

        On the worker thread and not the caller's, which is the entire reason this is a queue
        message rather than a direct call: the hook makes model calls, and a request handler is the
        one place those must not happen (it would hold the response open for the length of a batch).

        Cheap and idempotent. If work is already queued the nudge is handled after it, finds
        `_outstanding` non-zero, and does nothing - the real completion will fire the hook anyway.
        """
        with self._guard:
            if self._stopping:
                return
        self._ensure_worker()
        self._queue.put(_NUDGE)

    def set_ready_hook(self, on_ready: Callable[[str], None] | None) -> None:
        """Install the after-parse policy. See `_on_ready`."""
        self._on_ready = on_ready

    def set_idle_hook(self, on_idle: Callable[[], None] | None) -> None:
        """Install (or clear) the callback run when the queue goes empty. Public because the POLICY
        belongs to the caller — see `_on_idle`'s comment for why this module must not know what the
        hook does."""
        self._on_idle = on_idle

    def resume_interrupted(self) -> list[str]:
        """Re-enqueue everything a previous run left unfinished, and return what was picked up.

        Rows in an OWNED state are reset first (`horizon.reset_interrupted_states`): the process that
        owned them is gone, so the state is a lie. `parsing` falls back to `queued` — the blocks
        file was never written — and `distilling` to `ready_undistilled`, where the blocks exist and
        only the summary is missing. `failed` rows are NOT resumed — a parse that failed on its own
        terms would fail again, and retrying it forever on every restart is how a poisoned item
        becomes a loop. Submitting it
        again is an explicit act.

        Safe to call while the queue is busy: `_enqueue` refuses an id already waiting, so a node
        submitted a moment ago is not parsed twice.
        """
        # BOTH owned states, through the one map in `horizon.py`. `distilling` used to have no reset
        # anywhere, so a crash between claiming a node and writing its summary stranded it in a
        # state nothing selects — the same lie as a stale `parsing`, wearing a different name.
        horizon.reset_interrupted_states(base_dir=self._base_dir)
        resumed = [
            node.id
            for node in horizon.list_nodes(state="queued", limit=10_000, base_dir=self._base_dir)
            if self._enqueue(node.id)
        ]
        return resumed

    # -- observing and stopping -------------------------------------------------------------------

    def status(self) -> dict[str, object]:
        """What a status line may say, and nothing more (invariant 60).

        Read from `_outstanding`, never from `qsize()`: the queue counts the stop sentinel and reads
        zero in the window between the worker's `get()` and its first state write. An earlier
        version reported `{"running": False, "current": "nd-…", "pending": 1}` — simultaneously
        denying that anything was running, naming the node being parsed, and counting a sentinel.
        """
        with self._idle:
            outstanding = self._outstanding
        current = self._current
        return {
            "running": outstanding > 0,
            "current": current,
            "pending": max(0, outstanding - (1 if current is not None else 0)),
        }

    def cancel_pending(self) -> int:
        """Drop everything still waiting, mark it STOPPED, and return how many. Does NOT end the
        worker.

        **The rows used to stay at `queued`, and that was the bug invariant 79 is named after.**
        "Nothing was parsed, so nothing is lost, and `resume_interrupted` can pick them up later"
        was true only across a RESTART — which is not a thing a reader does. In the meantime three
        nodes sat at `queued` forever, drawn identically to a node still being read (same dot, no
        state word), with the page polling at 2.2 requests a second because `queued` counts as busy,
        offering no Try again (that is `failed`-only) and answering an open with a raw
        `404: node '...' has no stored text yet`. Invariant 79's own sentence is that a permanent
        `queued` "looks exactly like still working". It was.

        So a dropped item lands in a state that is TRUE and ACTIONABLE: `failed`, carrying "stopped
        before it was read". That is not a parse failure and the message says so, but it is the same
        SHAPE — terminal, visible, retryable — and `submit` already treats a `failed` node as the
        retry path, so the row's Try again button works with no new endpoint.

        The item currently being parsed is not affected: a native PDFium parse cannot be interrupted
        without taking the process with it, so the guarantee is "nothing further starts", not "this
        stops now".
        """
        with self._guard:
            # Bumped even when the FIFO is empty: a Stop has to reach work that is not IN the FIFO,
            # such as the idle hook's summary batch running on this queue's own thread.
            self._cancel_generation += 1
            dropped = self._drain()
        # OUTSIDE the lock: each of these is a SQL write, and holding `_guard` across them would
        # block every `submit` for the length of the batch.
        for node_id in dropped:
            horizon.update_node(
                node_id,
                base_dir=self._base_dir,
                state="failed",
                error="stopped before it was read",
            )
        return len(dropped)

    def stop(self, *, timeout: float = _JOIN_TIMEOUT) -> bool:
        """Cancel what is waiting, end the worker, and report whether it actually ended.

        TERMINAL: a stopped queue does not restart, so `_ensure_worker` refuses afterwards. Build a
        new one rather than reviving this.

        The drain and the sentinel happen under ONE hold of `_guard`, with `_stopping` set first.
        An earlier version cleared `_thread`, released, and then enqueued — and a `submit()` landing
        in that window started a second worker. See the module docstring.
        """
        with self._guard:
            self._stopping = True
            thread = self._thread
            self._thread = None
            self._drain()
            if thread is not None:
                self._queue.put(_STOP)
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def wait_idle(self, timeout: float = 30.0) -> bool:
        """Block until nothing is queued or in flight. For tests and for a caller that genuinely
        needs the batch finished; the UI polls `status()` instead."""
        with self._idle:
            return self._idle.wait_for(lambda: self._outstanding == 0, timeout=timeout)

    # -- queue bookkeeping --------------------------------------------------------------------------

    def _enqueue(self, node_id: str) -> bool:
        """Queue `node_id` unless it is already waiting. Returns whether it was added.

        **The stopped check is HERE as well as in `submit`, and this is the one that closes the
        window.** `submit`'s check releases `_guard` before `add_pending_node` and this call, so a
        `stop()` landing in between let a node through: `_ensure_worker` then correctly refused to
        start a worker while `_outstanding` had already been incremented and the id put on the
        queue. A permanent `queued` node (invariant 79's named failure) plus a leaked `_outstanding`
        — so `wait_idle` never returns and `status()` reports running forever. Same shape the
        `submit` guard was added for, one window smaller.

        The check and the increment happen under ONE hold of `_guard`, so a `stop()` — which needs
        `_guard` for its whole drain — cannot land between them.

        **`_guard` OUTSIDE `_idle`, and that order is the module's rule, not a preference.** This
        was the one place that took them the other way round: `_idle` then `_guard`, while `stop`
        and `cancel_pending` hold `_guard` across `_drain`, which takes `_idle` through
        `_finish_one`. Two locks acquired in opposite orders by two threads is a deadlock with
        nothing to time out — the intake thread and the caller of `stop()` each waiting on a lock
        the other holds, and an ASGI shutdown blocking on the join behind them. Latent rather than
        routine (the window is the few instructions between the two acquisitions), which is exactly
        what makes it worth pinning: it would surface as an unreproducible hang under load.
        """
        with self._guard:
            if self._stopping:
                return False
            with self._idle:
                if node_id in self._queued:
                    return False
                self._queued.add(node_id)
                self._outstanding += 1
        self._ensure_worker()
        self._queue.put(node_id)
        return True

    def _finish_one(self, node_id: str) -> None:
        with self._idle:
            self._queued.discard(node_id)
            self._outstanding -= 1
            if self._outstanding <= 0:
                self._outstanding = 0
                self._idle.notify_all()

    def _drain(self) -> list[str]:
        """Empty the queue of real work and return the node ids dropped. Caller holds `_guard`.

        Returns the IDS rather than a count, because the caller has to be able to say what happened
        to each of them — see `cancel_pending`.

        Drains PAST a sentinel rather than stopping at it — breaking on `_STOP` left everything
        behind it queued AND still counted, so `wait_idle` never returned. A sentinel found here is
        re-enqueued because `stop()` only ever puts one while a worker is alive to consume it. A
        nudge is discarded: it is not work, and nothing is waiting on it.
        """
        dropped: list[str] = []
        found_stop = False
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            self._queue.task_done()
            if item is _STOP:
                found_stop = True
                continue
            if item is _NUDGE:
                continue
            dropped.append(str(item))
            self._finish_one(str(item))
        if found_stop:
            self._queue.put(_STOP)
        return dropped

    # -- the worker -------------------------------------------------------------------------------

    def _ensure_worker(self) -> None:
        with self._guard:
            if self._stopping:
                return
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, name="rlm-intake", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                self._queue.task_done()
                return
            if item is _NUDGE:
                self._queue.task_done()
                self._maybe_idle()
                continue
            node_id = str(item)
            self._current = node_id
            try:
                self._process(node_id)
            except BaseException as exc:  # noqa: BLE001 - the worker must outlive any single item
                # `_process` records its own failures; this is the backstop for anything it did not
                # expect. Recording here too is what makes "a node is never left at `parsing`" a
                # property of the WORKER rather than of one function's exception list.
                self._record_failure(node_id, exc)
                _log.exception("intake: unhandled error on %s", node_id)
            finally:
                self._current = None
                self._queue.task_done()
                self._finish_one(node_id)
                self._maybe_idle()

    def _maybe_idle(self) -> None:
        """Run the idle hook if this was the last outstanding item.

        Checked under `_idle` so it cannot fire while another item is still counted, and called
        OUTSIDE that lock so a slow hook does not block `wait_idle` or a concurrent `submit`.
        """
        if self._on_idle is None:
            return
        with self._idle:
            if self._outstanding != 0:
                return
        try:
            self._on_idle()
        except BaseException:  # noqa: BLE001 - a policy hook must never end intake, see below
            # `BaseException`, not `Exception`, and that difference was measured. `config._env_int`
            # raises `SystemExit` for a malformed `PN_*` value, which is a `BaseException` — so a
            # typo in `PN_AUTO_DISTIL_MAX_PER_BATCH` escaped an `except Exception` here, unwound
            # `_run`, and ENDED THE WORKER THREAD. `threading` swallows `SystemExit` without a
            # traceback, so the operator got no signal at all: captures simply stopped being
            # parsed until the next submit happened to restart the thread. This docstring's
            # promise — "anything it raises is logged and swallowed" — has to be true for every
            # exception, or it is worth less than no promise.
            _log.exception("intake: the idle hook failed")

    def _record_failure(self, node_id: str, exc: BaseException) -> None:
        """Move a node to `failed` with the message, and never raise while doing it.

        A dead link and an unparseable PDF are different problems, and a reader who cannot tell them
        apart cannot act on either — so the message is kept rather than flattened to a boolean. If
        this itself fails (the row is gone, the disk is full), log and move on: the worker surviving
        matters more than the record.
        """
        try:
            horizon.update_node(
                node_id,
                base_dir=self._base_dir,
                state="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception:  # noqa: BLE001 - housekeeping must not take the worker down
            _log.exception("intake: could not record the failure of %s", node_id)

    def _process(self, node_id: str) -> None:
        """Parse one node. **Every step is inside the try**, which is the point.

        `get_node`, the `parsing` write and `store_blocks` all used to sit outside it, so a failure
        in any of the three left the node at `parsing` with no message — measured with a raising
        `store_blocks`: `state='parsing', error=None`, recoverable only by a restart.
        """
        try:
            node = horizon.get_node(node_id, base_dir=self._base_dir)
            if node is None:
                # Removed while it sat in the queue. Not an error — the reader changed their mind.
                return
            horizon.update_node(node_id, base_dir=self._base_dir, state="parsing")
            source = self._parse(node.origin, node_id)
            # `store_blocks` handles the node being removed DURING the parse: it deletes the blocks
            # it just wrote rather than leaving an orphan, which `add_node` would otherwise adopt.
            horizon.store_blocks(node_id, source, base_dir=self._base_dir)
        except Exception as exc:  # noqa: BLE001 - a parser may raise anything; the node records it
            # Broad on purpose. `ingest_one` reaches trafilatura, pypdfium2, yt-dlp and two OCR
            # backends, and the contract is that a capture never kills the worker and never
            # disappears — it becomes a `failed` node the reader can see and retry.
            self._record_failure(node_id, exc)
            return
        if self._on_ready is not None:
            try:
                self._on_ready(node_id)
            except BaseException:  # noqa: BLE001 - see `_maybe_idle`: a policy hook never ends intake
                _log.exception("intake: the after-parse hook failed for %s", node_id)


#: The API's single queue, created on first use. Single-process, like `api._ACTIVE_RUNS`
#: (invariant 23) — see the module docstring.
_SHARED: IntakeQueue | None = None
_SHARED_GUARD = threading.Lock()


def shared() -> IntakeQueue:
    """The process-wide queue, rebuilt if the last one was stopped.

    **The rebuild is not a convenience.** `stop()` is terminal by design, and the API stops this on
    ASGI shutdown — so without it, a second server lifecycle in one process (which is every test
    using `with TestClient(app)`, and any embedder starting the app twice) would hand out a queue
    whose worker refuses to start. A URL captured after that sits at `queued` forever while the
    request returns 200: invariant 79's "worst available failure", the one that looks exactly like
    still working. Reproduced before this branch existed.
    """
    global _SHARED
    with _SHARED_GUARD:
        if _SHARED is None or _SHARED.stopped:
            _SHARED = IntakeQueue()
        return _SHARED
