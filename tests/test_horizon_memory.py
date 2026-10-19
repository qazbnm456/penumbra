"""A capture's text as a kit memory item (`memory_store.py`, `horizon._become_item`): becoming one,
waiting to become one, never becoming two, and leaving nothing behind when it is removed or cleared.

Offline, real SQLite in the tmp_path conftest moves into. Every failure the store could raise is
injected by wrapping the real store, so the rest of each path runs for real.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from penumbra import horizon, memory_store
from penumbra.intake import IntakeQueue
from penumbra.schema import Source, SourceBlock


def _source(origin: str = "https://example.com/a", *, text: str = "hello there") -> Source:
    return Source(id="s0", kind="web", origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


def _busy() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = 5  # SQLITE_BUSY
    return exc


def _item_count() -> int:
    with sqlite3.connect(memory_store.store_path(horizon.DEFAULT_HORIZON_DIR)) as conn:
        return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def _until(predicate, timeout: float = 5.0) -> bool:
    """`IntakeQueue.wait_idle` counts queued items, not nudges, so a nudge's work is waited on."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _failing_add(monkeypatch, exc: BaseException, *, times: int = 1) -> list[int]:
    """Make the store's `add` raise `exc` the first `times` calls, then behave."""
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    real = store.add
    calls = [0]

    def add(*args, **kwargs):
        calls[0] += 1
        if calls[0] <= times:
            raise exc
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "add", add)
    return calls


# --- becoming an item ------------------------------------------------------------------------------


def test_a_capture_becomes_one_item_holding_its_text_and_its_provenance():
    page = horizon.add_node(_source(text="the body"))
    pasted = horizon.add_node(_source("pasted:a note", text="my own words"))
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    for node, provenance, text in ((page, "observed", "the body"), (pasted, "said", "my own words")):
        assert node.state == "ready_undistilled"
        [item] = store.find_meta("node_id", node.id)
        assert (item.text, item.provenance, item.origin) == (text, provenance, node.origin)
        assert item.meta["kind"] == "web"


def test_an_empty_capture_still_becomes_an_item_and_says_it_was_empty():
    node = horizon.add_node(_source(text="   "))
    [item] = memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", node.id)
    assert item.text == node.origin and item.meta["empty_text"] is True


def test_a_busy_store_leaves_the_capture_waiting_and_storing_it_again_finishes_it(monkeypatch):
    """A transient error is not a failure: the text is on disk, and `index_stored` takes it from
    there, never fetching it again."""
    _failing_add(monkeypatch, _busy())
    node = horizon.add_node(_source())
    assert node.state == "stored_unindexed" and "locked" in node.error
    assert horizon.stored_unindexed() == [node.id]
    done = horizon.index_stored(node.id)
    assert done.state == "ready_undistilled" and done.error is None
    assert horizon.stored_unindexed() == [] and _item_count() == 1


def test_any_other_store_error_fails_the_capture_but_keeps_its_text_for_a_retry(monkeypatch):
    _failing_add(monkeypatch, ValueError("no"))
    node = horizon.add_node(_source())
    assert node.state == "failed" and "no" in node.error
    assert horizon.has_stored_blocks(node)
    assert horizon.index_stored(node.id).state == "ready_undistilled"


def test_an_item_a_crash_left_behind_is_found_rather_than_added_twice():
    """A crash between `add` and the transaction that records it leaves an item no row points at;
    the next attempt finds it by the capture's id."""
    node = horizon.add_node(_source())
    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("UPDATE nodes SET memory_rowid = NULL, state = 'stored_unindexed' WHERE id = ?",
                     (node.id,))
    assert horizon.index_stored(node.id).state == "ready_undistilled"
    assert _item_count() == 1


def test_a_capture_removed_while_it_was_being_stored_leaves_no_item_and_no_text(monkeypatch):
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    real = store.add
    removed: list[str] = []

    def add_then_remove(*args, **kwargs):
        item = real(*args, **kwargs)
        assert horizon.remove_node(kwargs["meta"]["node_id"]) is True
        removed.append(item.id)
        return item

    monkeypatch.setattr(store, "add", add_then_remove)
    with pytest.raises(horizon.CaptureRemoved) as caught:
        horizon.add_node(_source())
    assert horizon.get_node(caught.value.node_id) is None
    assert store.get(removed[0]) is None and store.purged(removed[0]) is not None
    assert not horizon.node_blocks_path(caught.value.node_id).exists()


# --- removal and clearing --------------------------------------------------------------------------


def test_removing_a_capture_purges_its_item_and_its_text():
    node = horizon.add_node(_source(text="a secret worth forgetting"))
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    [item] = store.find_meta("node_id", node.id)
    assert horizon.remove_node(node.id) is True
    assert store.get(item.id) is None and store.purged(item.id) is not None
    assert store.search("secret") == []
    assert not horizon.node_blocks_path(node.id).exists()


def test_clearing_refuses_while_a_capture_is_being_stored_and_no_claim_starts_while_it_clears():
    node = horizon.add_node(_source())
    assert horizon._claim(node.id)
    try:
        with pytest.raises(horizon.IndexingInFlight):
            horizon.clear_all()
    finally:
        horizon._release(node.id)
    queued = horizon.add_pending_node("https://example.com/q", "web")
    horizon._CLEARING["on"] = True
    try:
        assert horizon._claim("nd-" + "1" * 16) is False
        assert horizon.claim_for_parse(queued.id) is False
    finally:
        horizon._CLEARING["on"] = False


def test_removing_a_waiting_capture_purges_an_item_a_crash_left_behind():
    node = horizon.add_node(_source(text="a leftover secret"))
    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("UPDATE nodes SET memory_rowid = NULL, state = 'stored_unindexed' WHERE id = ?",
                     (node.id,))
    assert horizon.remove_node(node.id) is True
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    assert store.find_meta("node_id", node.id) == [] and store.search("leftover") == []


def test_a_removal_that_decides_to_keep_a_filed_capture_keeps_its_text():
    node = horizon.add_node(_source(text="still wanted"))
    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("INSERT INTO memberships (node_id, orbit_id, source_id, promoted_at) "
                     "VALUES (?, 'o', 's1', 0)", (node.id,))
    assert horizon.remove_node(node.id, only_if_unfiled=True) is False
    [item] = memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", node.id)
    assert item.text == "still wanted"


def test_a_waiting_capture_that_is_already_an_item_is_only_marked_ready():
    """An orbit stored it while it also waited in the queue; a retry must not leave it waiting."""
    node = horizon.add_node(_source())
    horizon.update_node(node.id, state="stored_unindexed")
    assert horizon.index_stored(node.id).state == "ready_undistilled"
    assert horizon.stored_unindexed() == [] and _item_count() == 1


def test_clearing_erases_the_store_and_a_new_capture_starts_a_new_one():
    horizon.add_node(_source(text="before"))
    assert horizon.clear_all() == 1
    assert _item_count() == 0
    node = horizon.add_node(_source("https://example.com/b", text="after"))
    assert node.state == "ready_undistilled" and _item_count() == 1


# --- an orbit recording a capture that is not an item yet ------------------------------------------


def test_a_membership_recorded_while_the_capture_waits_is_written_when_it_becomes_an_item(monkeypatch):
    _failing_add(monkeypatch, _busy())
    source = _source("pasted:orbit text", text="filed text")
    assert horizon.record_orbit_sources("my-orbit", [source]) == 1
    [node] = horizon.list_nodes()
    assert node.state == "stored_unindexed" and horizon.nodes_in_orbit("my-orbit") == []
    assert horizon.record_orbit_sources("my-orbit", [source]) == 0, "pending counts as recorded"
    horizon.index_stored(node.id)
    [membership] = horizon.nodes_in_orbit("my-orbit")
    assert (membership.node_id, membership.source_id) == (node.id, "s0")


def test_an_orbit_storing_a_queued_capture_wins_once_and_intake_then_leaves_it():
    pending = horizon.add_pending_node("https://example.com/a", "web")
    assert horizon.record_orbit_sources("o", [_source()]) == 1
    node = horizon.get_node(pending.id)
    assert node.state == "ready_undistilled" and [m.node_id for m in horizon.nodes_in_orbit("o")] == [node.id]
    assert horizon.claim_for_parse(node.id) is False, "stored already: never fetched again"


# --- intake stores what waits ----------------------------------------------------------------------


def test_the_queue_stores_waiting_captures_and_runs_the_after_parse_hook(monkeypatch):
    _failing_add(monkeypatch, _busy())
    node = horizon.add_node(_source())
    assert node.state == "stored_unindexed"
    ready: list[str] = []
    queue = IntakeQueue(parse=lambda origin, node_id: _source(origin))
    queue.set_ready_hook(ready.append)
    try:
        queue.nudge()
        assert _until(lambda: ready == [node.id])
    finally:
        queue.stop(timeout=5)
    assert horizon.get_node(node.id).state == "ready_undistilled" and ready == [node.id]


def test_resubmitting_a_failed_capture_with_stored_text_stores_it_rather_than_fetching(monkeypatch):
    fetched: list[str] = []
    queue = IntakeQueue(parse=lambda origin, node_id: fetched.append(origin) or _source(origin))
    try:
        node = queue.submit("https://example.com/a")
        assert queue.wait_idle(5)
        assert fetched == ["https://example.com/a"]
        with sqlite3.connect(horizon.index_path()) as conn:
            conn.execute("UPDATE nodes SET memory_rowid = NULL, state = 'failed', error = 'x' WHERE id = ?",
                         (node.id,))
        again = queue.submit("https://example.com/a")
        assert again.state == "stored_unindexed"
        assert _until(lambda: horizon.get_node(node.id).state == "ready_undistilled")
    finally:
        queue.stop(timeout=5)
    assert fetched == ["https://example.com/a"], "not fetched a second time"
    assert horizon.get_node(node.id).state == "ready_undistilled"


# --- the layout before the memory store ------------------------------------------------------------


def test_an_index_from_before_the_memory_store_is_set_aside_not_read_or_deleted():
    base = Path(horizon.DEFAULT_HORIZON_DIR)
    (base / "nodes").mkdir(parents=True)
    (base / "nodes" / "nd-0000000000000001.json").write_text(json.dumps([]), encoding="utf-8")
    with sqlite3.connect(horizon.index_path()) as conn:
        conn.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO nodes VALUES ('nd-0000000000000001')")
    horizon._INITIALIZED.discard(str(horizon.index_path().resolve()))
    assert horizon.count_nodes() == 0
    [aside] = base.glob("pre-memory-*")
    assert (aside / "index.db").exists() and (aside / "nodes" / "nd-0000000000000001.json").exists()
    with sqlite3.connect(horizon.index_path()) as conn:
        assert conn.execute("PRAGMA application_id").fetchone()[0] == horizon._APPLICATION_ID
    horizon._INITIALIZED.discard(str(horizon.index_path().resolve()))
    assert horizon.count_nodes() == 0 and len(list(base.glob("pre-memory-*"))) == 1, \
        "our own database is never set aside"


def test_stopping_the_queue_leaves_a_capture_an_orbit_stored_while_it_waited():
    gate = threading.Event()

    def parse(origin, node_id):
        gate.wait(5)
        return _source(origin)

    queue = IntakeQueue(parse=parse)
    try:
        queue.submit("https://example.com/slow")
        waiting = queue.submit("https://example.com/a")
        assert horizon.record_orbit_sources("o", [_source()]) == 1
        assert queue.cancel_pending() == 1
        node = horizon.get_node(waiting.id)
        assert node.state == "ready_undistilled" and node.error is None
    finally:
        gate.set()
        queue.stop(timeout=5)


# --- pending memberships follow their orbit, and a purge never reaches a re-capture -----------------


def test_a_pending_membership_goes_with_its_orbit_and_with_its_source(monkeypatch):
    _failing_add(monkeypatch, _busy(), times=2)
    horizon.record_orbit_sources("gone", [_source("pasted:a", text="first")])
    horizon.record_orbit_sources("kept", [_source("pasted:b", text="second")])
    horizon.forget_orbit("gone")
    horizon.forget_membership("kept", "s0")
    for node_id in horizon.stored_unindexed():
        assert horizon.index_stored(node_id).state == "ready_undistilled"
        assert horizon.memberships_for(node_id) == []


def test_an_orbit_stores_its_text_into_a_capture_that_failed_while_its_membership_waited():
    pending = horizon.add_pending_node("https://example.com/a", "web")
    horizon.update_node(pending.id, state="parsing")      # intake holds it: the orbit's row waits
    assert horizon.record_orbit_sources("o", [_source()]) == 1
    horizon.update_node(pending.id, state="failed", error="the fetch failed")
    assert horizon.record_orbit_sources("o", [_source()]) == 1, "not counted as recorded"
    assert horizon.get_node(pending.id).state == "ready_undistilled"
    assert [m.orbit_id for m in horizon.memberships_for(pending.id)] == ["o"]


def test_a_removal_never_purges_or_unlinks_what_a_capture_of_the_same_text_holds_now(monkeypatch):
    """Forget a paste while the store is busy, paste the same text again, then let the purge retry:
    the new capture keeps its own item and its blocks, and the old item is gone."""
    first = horizon.add_node(_source("pasted:same", text="the same words"))
    [old] = memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", first.id)
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    real_purge, later = store.purge, []
    monkeypatch.setattr(store, "purge", lambda *a, **k: (_ for _ in ()).throw(_busy()))
    monkeypatch.setattr(horizon, "_retry_store", lambda attempt, **k: later.append(attempt))
    assert horizon.remove_node(first.id) is True
    monkeypatch.setattr(store, "purge", real_purge)
    again = horizon.add_node(_source("pasted:same", text="the same words"))
    assert again.id == first.id and again.state == "ready_undistilled"
    assert later and later[0]() is True
    [kept] = store.find_meta("node_id", again.id)
    assert kept.id != old.id and store.get(old.id) is None
    horizon._unlink_blocks_of_gone(again.id, f"{again.id}.json", base_dir=horizon.DEFAULT_HORIZON_DIR)
    assert horizon.node_blocks_path(again.id).exists()


def test_a_purge_from_before_a_clear_never_touches_the_new_store(monkeypatch):
    first = horizon.add_node(_source("pasted:one", text="before the clear"))
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    later: list = []
    monkeypatch.setattr(store, "purge", lambda *a, **k: (_ for _ in ()).throw(_busy()))
    monkeypatch.setattr(horizon, "_retry_store", lambda attempt, **k: later.append(attempt))
    assert horizon.remove_node(first.id) is True
    horizon.clear_all()
    again = horizon.add_node(_source("pasted:two", text="after the clear"))
    assert later and later[0]() is True
    assert memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", again.id)


def test_a_capture_removed_and_made_again_while_its_item_was_added_is_left_for_its_own_store(monkeypatch):
    """The first capture's item never lands on the second row of the same id: the second stays
    waiting and is stored from its own text."""
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    real = store.add
    again: list = []

    def add_then_remove_and_recapture(*args, **kwargs):
        item = real(*args, **kwargs)
        if not again:
            node_id = kwargs["meta"]["node_id"]
            assert horizon.remove_node(node_id) is True
            again.append(horizon.add_node(_source("pasted:twice", text="said twice")))
        return item

    monkeypatch.setattr(store, "add", add_then_remove_and_recapture)
    with pytest.raises(horizon.CaptureRemoved):
        horizon.add_node(_source("pasted:twice", text="said twice"))
    [second] = again
    assert horizon.get_node(second.id).state == "stored_unindexed"
    done = horizon.index_stored(second.id)
    assert done.state == "ready_undistilled"
    [item] = store.find_meta("node_id", second.id)
    assert item.meta["captured_at"] == done.created_at and item.text == "said twice"
