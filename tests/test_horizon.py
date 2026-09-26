"""`horizon.py` — Tier 0 storage, the index, and promotion into an orbit.

**No `importorskip`.** These run on a bare `uv sync`, like `test_runner.py`'s and `test_auth.py`'s
— a storage layer whose tests can silently not be collected is the trap AGENTS.md's Verify section
describes. The claim is about the EXTRAS (`api`, `chatterbox`), not about every dependency:
`horizon.py` does reach `rlm_harness` transitively, through `orbit.py` -> `ingest.py` ->
`parsers/web.py`'s SSRF guard, and `rlm-harness` is a CORE dependency that a bare sync installs.
Pinned at the bottom by a meta-path blocker in a subprocess rather than by this docstring.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from penumbra import horizon

#: This suite chdirs into a tmp_path (conftest), so a subprocess needs the repo root explicitly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
from penumbra.orbit import load_orbit
from penumbra.schema import Source, SourceBlock


def _source(origin: str = "https://example.com/a", *, kind: str = "web", text: str = "hello") -> Source:
    return Source(id="s0", kind=kind, origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


# --- capture -------------------------------------------------------------------------------------


def test_add_node_stores_the_row_and_the_blocks_separately():
    """Blocks on disk, metadata in the index — a listing of a thousand nodes must not carry a
    thousand corpora."""
    node = horizon.add_node(_source(text="the body"))
    assert node.id.startswith("nd-")
    assert node.kind == "web"
    assert node.chars == len("the body")

    blocks = json.loads(horizon.node_blocks_path(node.id).read_text(encoding="utf-8"))
    assert blocks == [{"locator": "whole", "text": "the body"}]
    # The text is NOT in the index: that is the whole point of the split.
    with sqlite3.connect(horizon.index_path()) as conn:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node.id,)).fetchone()
    assert "the body" not in str(row)


def test_capturing_the_same_url_twice_is_one_node():
    """Dedupe by origin, free, because the id IS the hash of the origin — the property invariant 12
    already requires of `--source`. "You already have that" is not an error a reader should handle.

    `origin_is_the_identity=True` is the CAPTURE PATH saying so, which is what the queue does
    (`add_pending_node` mints the id before the fetch, invariant 79). It used to be inferred from
    `is_url(origin)` — and an upload's origin is a filename the caller chose, so a file NAMED
    `https://example.com/paper.md` took this branch and silently replaced a real capture of that URL.
    """
    first = horizon.add_node(
        _source("https://example.com/a", text="v1"), origin_is_the_identity=True
    )
    second = horizon.add_node(
        _source("https://example.com/a", text="v2 — a later fetch"), origin_is_the_identity=True
    )
    assert first.id == second.id
    assert horizon.count_nodes() == 1
    # The blocks are NOT overwritten: another orbit's promotion may already have copied from them.
    blocks = json.loads(horizon.node_blocks_path(first.id).read_text(encoding="utf-8"))
    assert blocks[0]["text"] == "v1"


def test_pasted_text_dedupes_on_its_own_content():
    """Pasted text has no origin to be stable about, so it hashes what it says. Paste the same thing
    twice and you get one node, which is what a bag you throw things into should do."""
    def pasted(text: str) -> Source:
        return Source(id="s0", kind="text", origin="", blocks=[SourceBlock(locator="whole", text=text)])

    a = horizon.add_node(pasted("same"))
    b = horizon.add_node(pasted("same"))
    c = horizon.add_node(pasted("other"))
    assert a.id == b.id != c.id
    assert horizon.count_nodes() == 2


def test_node_ids_are_nfc_normalized_and_filename_safe():
    """Invariant 10's reasoning: two Unicode spellings of one name must not become two nodes. And a
    hex id is filename-safe by construction, so there is no `slug()` step here to get wrong."""
    composed = "https://example.com/café"        # café with U+00E9
    decomposed = "https://example.com/café"     # café with e + combining acute
    assert horizon.node_id_for(composed) == horizon.node_id_for(decomposed)
    assert horizon.node_id_for("https://x/../../etc/passwd").replace("nd-", "").isalnum()


def test_flags_and_preview_survive_the_round_trip():
    """`flags` is invariant 6's advisory metadata and `preview` is invariant 51's display-only page
    data — both belong to the node, not only to the promoted source."""
    src = _source()
    src = src.model_copy(update={"flags": ["b", "a"], "preview": {"title": "T", "site": "S"}})
    node = horizon.add_node(src)
    assert node.flags == ["a", "b"]           # sorted on the way in, so two captures compare equal
    assert node.preview == {"title": "T", "site": "S"}
    assert horizon.get_node(node.id).preview["title"] == "T"


# --- the delta rule (invariant 34, at Tier 0) ------------------------------------------------------


def test_two_writers_to_different_fields_both_survive():
    """The OUTCOME the delta rule exists for. Not a proof of it — an independent review pointed out
    that this passes against a whole-row implementation too, because each `update_node` re-reads
    inside itself, so the snapshot is never stale. `test_update_node_emits_a_delta_not_a_whole_row`
    below is the one that actually discriminates; this one is the readable statement of intent."""
    node = horizon.add_node(_source())
    horizon.update_node(node.id, summary="written by B")
    horizon.update_node(node.id, title="written by A")

    fresh = horizon.get_node(node.id)
    assert fresh.title == "written by A"
    assert fresh.summary == "written by B"


def test_update_node_emits_a_delta_not_a_whole_row(monkeypatch):
    """**The test the delta rule actually rests on**, and it had to be rewritten: the version above
    was a hollow green.

    Invariant 34 records TWO faults, and is explicit that a lock alone would not have helped: a
    caller read a snapshot, ran something SLOW, and wrote the whole object back over everything
    written meanwhile. Distillation is exactly that slow step here — a model call between reading a
    node and writing its summary. But a test that only checks the OUTCOME of two sequential writes
    cannot see the difference, because a whole-row implementation re-reads inside each call.

    So this reads the SQL. The statement must name the caller's columns and nothing else, and no
    `SELECT` may precede it inside the call — a whole-row write needs one, and could not pass.
    """
    node = horizon.add_node(_source())
    statements: list[str] = []
    real_connect = horizon.sqlite3.connect

    def traced(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(horizon.sqlite3, "connect", traced)
    horizon.update_node(node.id, title="t", summary="s")

    updates = [stmt for stmt in statements if stmt.strip().upper().startswith("UPDATE")]
    assert len(updates) == 1, statements
    # The trace callback expands bound parameters into the SQL, so the COLUMN NAMES are what this
    # can compare — which is the property anyway: a whole-row write names all twelve.
    set_clause = updates[0].split(" SET ", 1)[1].rsplit(" WHERE ", 1)[0]
    columns = [part.split("=", 1)[0].strip() for part in set_clause.split(",")]
    assert columns == ["title", "summary", "updated_at"], updates[0]
    before = statements[: statements.index(updates[0])]
    assert not [stmt for stmt in before if stmt.strip().upper().startswith("SELECT")], (
        f"update_node read the row before writing it, which is the whole-row shape: {before}"
    )


def test_update_node_refuses_a_field_it_does_not_know():
    """A typo that silently never persists is the failure this is guarding. It also keeps `id` and
    `created_at` out of reach — the two things that must never change."""
    node = horizon.add_node(_source())
    for bad in ("sumary", "id", "created_at", "updated_at"):
        with pytest.raises(ValueError, match="not updatable"):
            horizon.update_node(node.id, **{bad: "x"})


def test_update_node_bumps_updated_at_but_never_created_at():
    node = horizon.add_node(_source())
    updated = horizon.update_node(node.id, state="ready")
    assert updated.created_at == node.created_at
    assert updated.updated_at >= node.updated_at


def test_update_node_on_a_missing_node_returns_none_rather_than_raising():
    assert horizon.update_node("nd-nope", state="ready") is None


def test_store_blocks_clears_a_previous_error_itself():
    """Its docstring takes credit for this, and the credit was unearned: the only test covering it
    was satisfied by `intake.submit`'s own clear, so deleting `error=None` here left the suite
    green. A node that failed and was later filled must not display the old message beside a
    successful parse."""
    node = horizon.add_pending_node("https://example.com/a", "web")
    horizon.update_node(node.id, state="failed", error="404 while fetching")

    filled = horizon.store_blocks(node.id, _source(text="fetched at last"))
    assert filled.state == "ready_undistilled"
    assert filled.error is None
    assert filled.chars == len("fetched at last")


def test_store_blocks_on_a_removed_node_cleans_up_after_itself():
    """The other half of the orphan fix: if the row vanished while the parse ran, the blocks just
    written belong to nothing — and `add_node` would adopt them."""
    node = horizon.add_pending_node("https://example.com/a", "web")
    node_id = node.id
    horizon.remove_node(node_id)

    assert horizon.store_blocks(node_id, _source()) is None
    assert not horizon.node_blocks_path(node_id).exists()


# --- listing -------------------------------------------------------------------------------------


def test_list_nodes_is_newest_first_and_paged():
    """Paged rather than "everything": the premise is that this grows past what an orbit could
    hold, so a listing that loads all of it has Tier 1's problem one level up."""
    for n in range(5):
        horizon.add_node(_source(f"https://example.com/{n}"))
    first_two = horizon.list_nodes(limit=2)
    assert len(first_two) == 2
    assert [n.origin for n in first_two] == [n.origin for n in horizon.list_nodes(limit=5)[:2]]
    assert horizon.list_nodes(limit=2, offset=4)[0].origin not in {n.origin for n in first_two}
    assert horizon.count_nodes() == 5


def test_list_nodes_filters_by_state():
    a = horizon.add_node(_source("https://example.com/a"))
    horizon.add_node(_source("https://example.com/b"))
    horizon.update_node(a.id, state="failed", error="404")
    assert [n.id for n in horizon.list_nodes(state="failed")] == [a.id]
    assert horizon.count_nodes(state="failed") == 1
    assert horizon.get_node(a.id).error == "404"


# --- promotion -----------------------------------------------------------------------------------


def test_promotion_assigns_the_orbit_s_own_source_id_not_the_node_id():
    """The node id is a PLACEHOLDER. `append_sources` renumbers against the receiving orbit from
    the max id in use (invariant 50), and `Source.marker()` derives the citation coordinate from
    `.id` at blob time (invariant 4) — so nothing stored ever had the placeholder baked in."""
    node = horizon.add_node(_source())
    membership = horizon.promote_node(node.id, "myorbit")

    assert membership.source_id != node.id
    orbit = load_orbit("myorbit")
    assert [s.id for s in orbit.sources] == [membership.source_id]
    promoted = orbit.sources[0]
    assert promoted.origin == "https://example.com/a"
    assert promoted.blocks[0].text == "hello"
    # The coordinate a citation must echo is built from the ASSIGNED id.
    assert promoted.marker("whole") == f"[[SRC:{membership.source_id}|whole]]"


def test_promotion_does_not_consume_the_node():
    """The node is what persists; an orbit is a view over a selection of them. That is the whole
    "different facets of yourself" premise."""
    node = horizon.add_node(_source())
    horizon.promote_node(node.id, "work")
    horizon.promote_node(node.id, "personal")

    assert horizon.get_node(node.id) is not None
    assert {m.orbit_id for m in horizon.memberships_for(node.id)} == {"work", "personal"}
    assert [m.node_id for m in horizon.nodes_in_orbit("work")] == [node.id]


def test_promoting_something_the_orbit_already_holds_is_not_an_error():
    """`append_sources` dedupes by origin. A 409 here would make "add everything with this tag" fail
    on the one item the reader had already added by hand."""
    node = horizon.add_node(_source())
    first = horizon.promote_node(node.id, "myorbit")
    again = horizon.promote_node(node.id, "myorbit")

    assert again.source_id == first.source_id
    assert len(load_orbit("myorbit").sources) == 1
    assert len(horizon.memberships_for(node.id)) == 1


def test_promotion_of_a_missing_node_raises_rather_than_creating_an_empty_orbit():
    with pytest.raises(ValueError, match="no such node"):
        horizon.promote_node("nd-nope", "myorbit")
    assert load_orbit("myorbit") is None


def test_node_source_carries_the_blocks_back_out():
    node = horizon.add_node(_source(text="body text"))
    src = horizon.node_source(node.id)
    assert src.id == node.id           # the placeholder, replaced at promotion
    assert src.blocks[0].text == "body text"
    assert horizon.node_source("nd-nope") is None


# --- removal -------------------------------------------------------------------------------------


def test_removing_a_node_drops_its_memberships_but_never_a_promoted_source():
    """An orbit that silently lost a cited source because someone tidied their horizon would break
    invariant 12's promise that a source already cited in a saved turn keeps meaning what it meant.
    The source was COPIED; removal forgets the node, not the copy."""
    node = horizon.add_node(_source())
    horizon.promote_node(node.id, "myorbit")

    assert horizon.remove_node(node.id) is True
    assert horizon.get_node(node.id) is None
    assert horizon.memberships_for(node.id) == []
    assert not horizon.node_blocks_path(node.id).exists()
    assert len(load_orbit("myorbit").sources) == 1, "promotion is a copy; removal must not reach it"


def test_removing_a_node_that_is_not_there_says_so_rather_than_raising():
    """"Not there" and "not even an id" are different answers, and a future
    `DELETE /horizon/{node_id}` needs to tell them apart: 404 versus 400."""
    assert horizon.remove_node("nd-" + "0" * 16) is False
    with pytest.raises(ValueError, match="not a node id"):
        horizon.remove_node("nd-nope")


def test_the_cascade_is_actually_on():
    """`PRAGMA foreign_keys` is OFF by default in SQLite and is per-CONNECTION. Without setting it
    every time, the `ON DELETE CASCADE` is decoration and removal silently orphans membership rows —
    which the test above would still pass, because it asks `memberships_for`, which filters by a
    node id nothing else returns."""
    node = horizon.add_node(_source())
    horizon.promote_node(node.id, "myorbit")
    horizon.remove_node(node.id)
    with sqlite3.connect(horizon.index_path()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM memberships").fetchone()[0] == 0


# --- regressions found by an independent review ---------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "../../victim",
        "../../orbits/myorbit",
        "nd-../../victim",
        "/etc/passwd",
        "nd-ABCDEF0123456789",     # uppercase is not what `node_id_for` mints
        "nd-0123456789abcde",      # 15, not 16
        "",
        "nd-0123456789abcdef/../x",
    ],
)
def test_a_node_id_never_becomes_an_arbitrary_path(hostile, tmp_path):
    """**`remove_node("../../orbits/myorbit")` deleted a live orbit file and returned `False`.**

    Reproduced before the fix, both forms: the relative one escaped `horizon/nodes/`, and an absolute
    one discarded the directory outright, because `Path("horizon/nodes") / "/etc/x"` IS `/etc/x`. The
    id is hex-safe only when this module MINTED it — invariant 10's whole distinction, and an
    earlier draft of invariant 78 asserted the opposite, which is what would have told the endpoint
    author no guard was needed.
    """
    victim = tmp_path / "victim.json"
    victim.write_text("precious")
    horizon.add_node(_source())  # so horizon/nodes/ exists, as it would on any real server

    with pytest.raises(ValueError):
        horizon.node_blocks_path(hostile)
    with pytest.raises(ValueError):
        horizon.remove_node(hostile)
    assert victim.exists()


def test_capturing_one_origin_from_many_threads_never_raises_and_never_diverges():
    """**Seven of eight captures raised `IntegrityError`, and the row disagreed with the disk.**

    SELECT-then-INSERT is a check-then-act, and `isolation_level=None` means nothing spans the two.
    `IntegrityError` is not an `OperationalError`, so `busy_timeout` never saw it and nothing
    retried — against a docstring promising "returns the existing node untouched rather than
    raising". Measured before the fix: 7 errors, and `row.chars = 80` against 40 characters of
    blocks on disk, because every losing thread still wrote the file.
    """
    barrier = threading.Barrier(8)
    errors: list[BaseException] = []
    results: list[str] = []

    def capture(n: int) -> None:
        # Different lengths on purpose: identical payloads would hide a row/disk divergence.
        src = _source("https://example.com/same", text="x" * (10 * (n + 1)))
        barrier.wait()
        try:
            # `origin_is_the_identity=True` — this models the QUEUE capturing one URL from eight
            # threads, which is the path where the origin really is the whole identity.
            results.append(horizon.add_node(src, origin_is_the_identity=True).id)
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=capture, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert len(set(results)) == 1, "one origin must be one node"
    assert horizon.count_nodes() == 1

    node = horizon.get_node(results[0])
    on_disk = sum(
        len(block["text"])
        for block in json.loads(horizon.node_blocks_path(node.id).read_text(encoding="utf-8"))
    )
    assert node.chars == on_disk, "the index and the blocks came from different captures"


def test_two_nodes_sharing_an_origin_cannot_silently_shadow_each_other():
    """**Node C's text never reached the orbit and the index said it had.**

    `append_sources` dedupes by ORIGIN, and the old fallback read "appended nothing" as "this same
    node is already here". It means *some* source shares the origin. Two distinct nodes both
    recorded a membership pointing at the FIRST one's source, the second's text was lost, and
    `promote_node` returned success — corrupted state, not a missed append.

    That was first fixed by REFUSING, which was right about shadowing and wrong about the outcome:
    nothing in the product can rename a node or a source, so the second document was permanently
    unfileable — invariant 79 lands the capture and invariant 78's promotion is then a dead end.
    The property this test exists for is that neither document is lost or mistaken for the other,
    and disambiguating the display origin keeps it while also letting both land.
    """
    def pasted(text: str) -> Source:
        return Source(id="s0", kind="text", origin="", blocks=[SourceBlock(locator="whole", text=text)])

    a = horizon.add_node(pasted("AAA"))
    c = horizon.add_node(pasted("CCC"))
    assert a.id != c.id

    first = horizon.promote_node(a.id, "orb")
    second = horizon.promote_node(c.id, "orb")

    # TWO sources, two ids, two memberships — and each membership points at its OWN node's text.
    assert first.source_id != second.source_id
    assert sorted(m.node_id for m in horizon.nodes_in_orbit("orb")) == sorted([a.id, c.id])
    assert [m.source_id for m in horizon.memberships_for(c.id)] == [second.source_id]
    sources = {s.id: s for s in load_orbit("orb").sources}
    assert set(sources) == {first.source_id, second.source_id}
    assert sources[first.source_id].blocks[0].text == "AAA"
    assert sources[second.source_id].blocks[0].text == "CCC", "C's text is what was being lost"
    # The ORIGINS differ, which is what keeps them tellable apart on screen.
    assert sources[first.source_id].origin != sources[second.source_id].origin


def test_re_promoting_the_same_node_still_works_after_that_guard():
    """The guard must not break the idempotent case it sits next to — it matches on the node's OWN
    prior membership, not on the origin."""
    node = horizon.add_node(_source())
    first = horizon.promote_node(node.id, "orb")
    again = horizon.promote_node(node.id, "orb")
    assert again.source_id == first.source_id
    assert len(load_orbit("orb").sources) == 1


def test_a_bad_value_is_refused_instead_of_poisoning_the_listing():
    """**One bad write made every later `list_nodes()` raise.** `_UPDATABLE` checked the column NAME;
    nothing checked the VALUE, so `state="bogus"` committed and then `Node.model_validate` failed on
    every read-back — the whole page, not just the bad row."""
    node = horizon.add_node(_source())
    for bad in ({"state": "bogus-state"}, {"tags": None}, {"chars": "lots"}, {"kind": "spreadsheet"}):
        with pytest.raises(ValueError):
            horizon.update_node(node.id, **bad)
    # Nothing was written, so the listing still reads.
    assert horizon.get_node(node.id).state == "ready_undistilled"
    assert len(horizon.list_nodes()) == 1


def test_the_index_recovers_if_the_horizon_directory_is_deleted_underneath_it():
    """`rm -rf horizon/` against a running server is an ordinary thing for a user to do. The
    initialization cache is keyed by path and was never invalidated, so every later call raised
    `no such table: nodes` for the life of the process."""
    import shutil

    horizon.add_node(_source())
    assert horizon.count_nodes() == 1

    shutil.rmtree(horizon.horizon_dir())
    assert horizon.count_nodes() == 0          # a fresh, empty index rather than an OperationalError
    horizon.add_node(_source())
    assert horizon.count_nodes() == 1


# --- the storage properties the module docstring claims --------------------------------------------


def test_the_database_is_in_wal_mode():
    """Claimed in the module docstring as the half of the concurrency answer that works ACROSS
    processes. WAL is a property of the FILE, so this reads it back from a fresh connection that
    never set it."""
    horizon.add_node(_source())
    with sqlite3.connect(horizon.index_path()) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_concurrent_writers_all_land():
    """Not a proof of thread safety — it is the floor. Sixteen threads capturing sixteen different
    origins must produce sixteen rows, not an `OperationalError: database is locked` and fifteen.

    **This test found a real bug, and the bug was in the line that looked most harmless.** The first
    draft ran `PRAGMA journal_mode=WAL` on every connection, reasoned about as a no-op because WAL is
    a property of the FILE. It is a no-op only once the mode is ALREADY WAL: changing it needs an
    exclusive lock, and SQLite does NOT invoke the busy handler for that change, so a 15-second
    `busy_timeout` protects every statement here except that one. Measured at roughly one failure in
    six runs, with a looping probe putting the traceback on that exact pragma.
    """
    errors: list[BaseException] = []

    def capture(n: int) -> None:
        try:
            horizon.add_node(_source(f"https://example.com/{n}"))
        except BaseException as exc:  # noqa: BLE001 - recorded and re-raised by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=capture, args=(n,)) for n in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    assert horizon.count_nodes() == 16


def test_connect_never_sets_the_journal_mode():
    """A source assertion, and it has to be, because the behavioural symptom is a ONE-IN-SIX FLAKE.

    `PRAGMA journal_mode=WAL` is the single statement in this module that a `busy_timeout` does not
    cover (SQLite skips the busy handler when the mode is being CHANGED), so it belongs in
    `_initialize`, which runs once, and never in `_connect`, which runs on every operation. A test
    that only ran writers concurrently would pass five times out of six after the regression came
    back — the same reason invariants 36 and 54 are pinned against the source tree.
    """
    import inspect

    body = inspect.getsource(horizon._connect)
    assert "journal_mode" not in body, (
        "_connect must not touch journal_mode — it is the one pragma busy_timeout does not protect"
    )
    # And the two that genuinely are per-connection must still be there.
    assert "busy_timeout" in body
    assert "foreign_keys" in body
    assert "journal_mode" in inspect.getsource(horizon._initialize)


def test_initialization_runs_once_per_database():
    """The cache is what removes the in-process race outright; the retry inside `_initialize` only
    covers two PROCESSES creating the same new database, which no in-process lock can see."""
    horizon.add_node(_source())
    key = str(horizon.index_path().resolve())
    assert key in horizon._INITIALIZED

    calls = []
    real = horizon._initialize

    def counting(path):
        calls.append(path)
        return real(path)

    horizon._initialize = counting
    try:
        horizon.list_nodes()
        horizon.count_nodes()
        horizon.get_node("nd-nope")
    finally:
        horizon._initialize = real
    # Called every time, but each call short-circuits on the cache rather than re-running the DDL.
    assert len(calls) == 3
    assert horizon.count_nodes() == 1


def test_horizon_imports_without_the_api_extra_or_dspy():
    """The docstring's no-`importorskip` claim, VERIFIED rather than trusted — the meta-path method
    AGENTS.md's Verify section requires, because a local venv that happens to have an extra
    installed is greener than CI.

    In a SUBPROCESS, deliberately. An in-process blocker cannot see an import that another test
    already cached in `sys.modules`, so it would pass by doing nothing on almost every full run —
    and a test that is green because it was a no-op is worse than no test. A fresh interpreter has
    nothing cached, so the blocker is reached by every import `horizon.py` actually performs,
    transitively.
    """
    import subprocess
    import sys

    probe = """
import sys

# The two EXTRAS, which is what the claim is about. `chatterbox`/`soundfile` matter because CI does
# NOT sync that extra, so a local venv holding it is GREENER than CI — the trap running the other
# way. `rlm_harness`/`dspy` are deliberately absent: they are core dependencies, and `horizon.py`
# reaches them through `parsers/web.py`'s SSRF guard, which a bare `uv sync` installs.
BLOCKED = {"fastapi", "starlette", "httpx", "uvicorn", "chatterbox", "soundfile"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("blocked by the test: " + name)


sys.meta_path.insert(0, Blocker())
import penumbra.horizon  # noqa: F401

leaked = sorted(n for n in sys.modules if n.split(".")[0] in BLOCKED)
assert not leaked, leaked
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        # The assertion below reports the child's stderr, which is more useful than a
        # CalledProcessError that hides it.
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


# --- states whose owning process is gone -----------------------------------------------------------


def test_claim_node_is_a_compare_and_set_not_a_label():
    """`update_node(state=...)` writes a LABEL: two callers both write it and both proceed. A claim
    has to fail for the loser, or two concurrent distillation passes bill the same node twice."""
    node = horizon.add_pending_node("https://example.com/a", "web")
    assert horizon.claim_node(node.id, expect="queued", to="parsing") is True
    assert horizon.get_node(node.id).state == "parsing"
    # The second caller loses, and nothing moves.
    assert horizon.claim_node(node.id, expect="queued", to="parsing") is False
    assert horizon.get_node(node.id).state == "parsing"
    assert horizon.claim_node("nd-" + "0" * 16, expect="queued", to="parsing") is False


def test_both_owned_states_are_recovered_and_each_falls_back_to_the_right_one():
    """**`distilling` used to have no reset anywhere.** A crash between claiming a node and writing
    its summary stranded it in a state NOTHING selects — `distil_pending` queries
    `ready_undistilled` — with the model call already paid for. It is the same lie as a stale
    `parsing`, wearing a different name, so both live in one map.

    The fallbacks differ and that is the point: a `parsing` node has no blocks file yet, so it goes
    back to `queued`; a `distilling` node has one, so only the summary is missing.
    """
    parsing = horizon.add_pending_node("https://example.com/p", "web")
    horizon.update_node(parsing.id, state="parsing")
    distilling = horizon.add_pending_node("https://example.com/d", "web")
    horizon.store_blocks(distilling.id, _source("https://example.com/d"))
    horizon.update_node(distilling.id, state="distilling")
    untouched = horizon.add_pending_node("https://example.com/f", "web")
    horizon.update_node(untouched.id, state="failed", error="gone")

    recovered = horizon.reset_interrupted_states()

    assert recovered == {"parsing": [parsing.id], "distilling": [distilling.id]}
    assert horizon.get_node(parsing.id).state == "queued"
    assert horizon.get_node(distilling.id).state == "ready_undistilled"
    assert horizon.get_node(untouched.id).state == "failed", "a real failure is not an owned state"


def test_recovery_is_a_no_op_when_nothing_was_interrupted():
    horizon.add_node(_source())
    assert horizon.reset_interrupted_states() == {}


# --- search: the product's actual promise, made queryable -------------------------------------------


def _distilled(origin: str, title: str, summary: str, tags: list[str], entities: list[str]):
    node = horizon.add_node(_source(origin, text="body"))
    horizon.update_node(
        node.id, state="ready", title=title, summary=summary, tags=tags, entities=entities
    )
    return node


def test_search_reads_every_field_distillation_produces():
    """**Until this existed the product's stated promise was unimplemented.** Distillation writes a
    title, a summary, tags and entities precisely so a node can be found by DESCRIPTION months later
    (invariant 80), and nothing could read any of it back. `origin` is in the set too, because a URL
    is often the one word a person does remember."""
    a = _distilled(
        "https://example.com/rams", "Less, but better", "Good design removes.", ["design"], ["Rams"]
    )
    b = _distilled(
        "https://other.test/tabs", "Why the tab stays open", "Attention and memory.", ["notes"], []
    )

    found = lambda q: {n.id for n in horizon.list_nodes(query=q)}
    assert found("Less") == {a.id}, "title"
    assert found("removes") == {a.id}, "summary"
    assert found("notes") == {b.id}, "tags"
    assert found("Rams") == {a.id}, "entities"
    assert found("other.test") == {b.id}, "origin"
    assert found("") == {a.id, b.id}, "an empty query is not a filter"
    assert found("   ") == {a.id, b.id}, "nor is whitespace"
    assert found("nothing at all") == set()


def test_search_is_case_insensitive_for_latin_and_works_for_han():
    """SQLite's `LIKE` folds case for ASCII, and Han has no case — which is every script this
    interface actually serves."""
    latin = _distilled("https://example.com/a", "Pattern Language", "", [], [])
    han = _distilled(
        "https://example.com/b", "第五公設與非歐幾何", "一條被當成缺陷的規則。", ["數學"], []
    )

    assert {n.id for n in horizon.list_nodes(query="pattern")} == {latin.id}
    assert {n.id for n in horizon.list_nodes(query="PATTERN")} == {latin.id}
    assert {n.id for n in horizon.list_nodes(query="非歐")} == {han.id}
    assert {n.id for n in horizon.list_nodes(query="缺陷")} == {han.id}
    assert {n.id for n in horizon.list_nodes(query="數學")} == {han.id}


def test_search_combines_with_the_state_filter_and_the_count_agrees():
    """`count_nodes` and `list_nodes` have to answer the same question, or a listing says "3 of 7"
    about two different sets."""
    kept = _distilled("https://example.com/a", "design notes", "", [], [])
    _distilled("https://example.com/b", "something else", "", [], [])
    pending = horizon.add_pending_node("https://example.com/design-pending", "web")

    assert {n.id for n in horizon.list_nodes(query="design")} == {kept.id, pending.id}
    assert horizon.count_nodes(query="design") == 2
    assert {n.id for n in horizon.list_nodes(query="design", state="ready")} == {kept.id}
    assert horizon.count_nodes(query="design", state="ready") == 1


def test_a_query_cannot_inject_sql():
    """The clause is built from a fixed column list and the needle is bound, never interpolated."""
    kept = _distilled("https://example.com/a", "safe", "", [], [])
    for hostile in ("' OR 1=1 --", "%", "_", "'; DROP TABLE nodes; --", "\\"):
        horizon.list_nodes(query=hostile)
    assert horizon.count_nodes() == 1
    assert horizon.get_node(kept.id) is not None
    # `%` is a LIKE wildcard, so it legitimately matches everything - that is the operator working,
    # not an injection. What must not happen is the table going away, asserted above.
    assert horizon.count_nodes(query="' OR 1=1 --") == 0


def test_search_never_reads_the_blocks_on_disk():
    """Invariant 78: the index is what a listing renders, and reading a thousand block files to
    answer a keystroke is the shape it exists to avoid. Asserted by removing the files."""
    node = _distilled("https://example.com/a", "findable", "and still findable", [], [])
    horizon.node_blocks_path(node.id).unlink()
    assert {n.id for n in horizon.list_nodes(query="findable")} == {node.id}

def test_search_ands_its_terms_and_leaves_cjk_alone(tmp_path):
    """Narrow by tag, then add the word you remember. That gesture returned NOTHING.

    A single `%design Rams%` is one substring against one column, so a node tagged `design` whose
    summary begins "Rams argues that..." did not match — the two words live in different columns and
    no single needle can span them. An independent review found it by clicking a tag and typing the
    next word, which is the product's core promise in one motion.

    The CJK half is the reason the split is on WHITESPACE and nothing else: a Chinese query has no
    spaces, so it stays one term and one substring, which is the only correct behaviour for a script
    with no word boundaries.
    """
    from penumbra.schema import Source, SourceBlock

    def node(origin: str, **fields):
        made = horizon.add_node(
            Source(id="s0", kind="text", origin=origin, blocks=[SourceBlock(locator="whole", text="x")]),
            base_dir=tmp_path,
        )
        horizon.update_node(made.id, base_dir=tmp_path, state="ready", **fields)

    node("pasted:one", title="Less, but better", summary="Rams argues that good design removes.",
         tags=["design", "principles"])
    node("pasted:two", title="Why the tab stays open", summary="It is held for one sentence.",
         tags=["attention"])
    node("pasted:three", title="設計的本質", summary="把事情變得簡單", tags=["設計"])

    def found(query):
        return sorted(n.origin for n in horizon.list_nodes(query=query, base_dir=tmp_path))

    # One term each, in DIFFERENT columns: `design` is a tag, `Rams` is in the summary.
    assert found("design") == ["pasted:one"]
    assert found("Rams") == ["pasted:one"]
    assert found("design Rams") == ["pasted:one"], "the two terms must AND, not concatenate"
    assert found("  design   Rams  ") == ["pasted:one"], "extra whitespace is not a term"
    # A term that matches nothing removes the row, which is what AND means.
    assert found("design zzzz") == []
    # CJK: one term, unchanged behaviour.
    assert found("設計") == ["pasted:three"]
    assert found("設計的本質") == ["pasted:three"], "a spaceless query is still ONE substring"
    # Mixed scripts split too.
    assert found("設計 簡單") == ["pasted:three"]

def test_a_promotion_that_loses_a_race_leaves_no_empty_orbit(tmp_path, monkeypatch):
    """`create=True` means promoting into a name that does not exist yet makes the orbit — which
    is right, and is what "file this into a new facet" means. It also means a promotion that FAILS
    afterwards can leave an orbit nobody asked for.

    Twelve concurrent promote/delete races all correctly lost the promote (the node was gone, the
    foreign key refused the membership, the compensating write undid the append) and all twelve left
    `racebook.json` on disk, showing in the facet rail as "Untitled orbit · 0". The source was
    rolled back; the FILE was not.

    Only an orbit this call created and left empty is removed. A pre-existing one is someone
    else's, and one that gained content from another writer in the meantime is not ours to judge.
    """
    from penumbra.orbit import orbit_path
    from penumbra.schema import Source, SourceBlock

    node = horizon.add_node(
        Source(id="s0", kind="text", origin="pasted:race", blocks=[SourceBlock(locator="whole", text="x")]),
        base_dir=tmp_path,
    )
    orbits = tmp_path / "nbs"

    # The node vanishes between the orbit write and the membership insert — exactly the race,
    # forced rather than hoped for.
    real_append = horizon.append_sources

    def append_then_delete(orbit, sources):
        out = real_append(orbit, sources)
        horizon.remove_node(node.id, base_dir=tmp_path)
        return out

    monkeypatch.setattr(horizon, "append_sources", append_then_delete)

    with pytest.raises(ValueError, match="removed while it was being promoted"):
        horizon.promote_node(node.id, "racebook", base_dir=tmp_path, orbits_dir=orbits)

    assert not orbit_path("racebook", base_dir=orbits).exists(), (
        "a promotion that failed left an orbit nobody asked for"
    )


def test_a_promotion_that_loses_a_race_keeps_a_orbit_that_already_existed(tmp_path, monkeypatch):
    """The other half, and the one that makes the rule safe: the rollback removes only an orbit
    THIS call brought into being. An existing orbit keeps its file and its other sources."""
    from penumbra.orbit import (
        load_orbit,
        mutate_orbit,
        orbit_path,
        remove_source,
    )
    from penumbra.schema import Source, SourceBlock

    orbits = tmp_path / "nbs"
    keeper = horizon.add_node(
        Source(
            id="s0",
            kind="text",
            origin="pasted:keep",
            blocks=[SourceBlock(locator="whole", text="keep me")],
        ),
        base_dir=tmp_path,
    )
    horizon.promote_node(keeper.id, "mine", base_dir=tmp_path, orbits_dir=orbits)
    assert orbit_path("mine", base_dir=orbits).exists()

    doomed = horizon.add_node(
        Source(id="s0", kind="text", origin="pasted:doomed", blocks=[SourceBlock(locator="whole", text="y")]),
        base_dir=tmp_path,
    )
    real_append = horizon.append_sources

    def append_then_delete(orbit, sources):
        out = real_append(orbit, sources)
        horizon.remove_node(doomed.id, base_dir=tmp_path)
        return out

    monkeypatch.setattr(horizon, "append_sources", append_then_delete)
    with pytest.raises(ValueError, match="removed while it was being promoted"):
        horizon.promote_node(doomed.id, "mine", base_dir=tmp_path, orbits_dir=orbits)

    assert orbit_path("mine", base_dir=orbits).exists(), "an existing orbit was deleted"
    kept = load_orbit("mine", base_dir=orbits)
    assert [s.origin for s in kept.sources] == ["pasted:keep"], "the rollback took the wrong source"

    # **And an EMPTY orbit that already existed.** This is the case the `existed` guard is really
    # for, and without it the emptiness check alone looks sufficient: an empty pre-existing orbit
    # is indistinguishable, after the rollback, from one this call created. Mutating the guard to
    # `if True` passed every assertion above until this one was written.
    empty_before = horizon.add_node(
        Source(
            id="s0",
            kind="text",
            origin="pasted:solo",
            blocks=[SourceBlock(locator="whole", text="z")],
        ),
        base_dir=tmp_path,
    )
    horizon.promote_node(empty_before.id, "shell", base_dir=tmp_path, orbits_dir=orbits)
    # Emptied by hand, the way removing its last source would.
    mutate_orbit("shell", lambda orb: remove_source(orb, orb.sources[0].id), base_dir=orbits)
    assert not load_orbit("shell", base_dir=orbits).sources

    victim = horizon.add_node(
        Source(
            id="s0",
            kind="text",
            origin="pasted:victim",
            blocks=[SourceBlock(locator="whole", text="w")],
        ),
        base_dir=tmp_path,
    )

    def append_then_delete_victim(orbit, sources):
        out = real_append(orbit, sources)
        horizon.remove_node(victim.id, base_dir=tmp_path)
        return out

    monkeypatch.setattr(horizon, "append_sources", append_then_delete_victim)
    with pytest.raises(ValueError, match="removed while it was being promoted"):
        horizon.promote_node(victim.id, "shell", base_dir=tmp_path, orbits_dir=orbits)

    assert orbit_path("shell", base_dir=orbits).exists(), (
        "an EMPTY orbit that already existed was deleted by someone else's failed promotion"
    )


def test_an_underscore_in_a_search_is_a_character_not_a_wildcard(tmp_path):
    """**`LIKE` has TWO wildcards and only one of them was a decision.**

    `%` staying live is recorded and right: typing one is the operator working. `_` is not — it is
    an ordinary character in precisely the text this searches (`my_notes.txt`, `design_system`,
    every snake_case filename, half the URLs), and unescaped it matches any single character. So
    searching `my_notes` also returned `myXnotes.txt`, with nothing on screen to explain why.
    """
    from penumbra import horizon
    from penumbra.schema import Source, SourceBlock

    def node(origin: str) -> None:
        horizon.add_node(
            Source(
                id="s0",
                kind="text",
                origin=origin,
                blocks=[SourceBlock(locator="whole", text=f"contents of {origin}")],
            ),
            base_dir=tmp_path,
        )

    for name in ("my_notes.txt", "myXnotes.txt", "report2024.txt"):
        node(name)

    found = [n.origin for n in horizon.list_nodes(query="my_notes", base_dir=tmp_path)]
    assert found == ["my_notes.txt"], f"the underscore matched any character: {found}"
    assert horizon.count_nodes(query="my_notes", base_dir=tmp_path) == 1, "the count must agree"

    # `%` is still the operator working — a recorded decision, not an oversight.
    assert len(horizon.list_nodes(query="%", base_dir=tmp_path)) == 3

    # ...and the escape character itself is not a wildcard either.
    node("bang!bang.txt")
    assert [n.origin for n in horizon.list_nodes(query="bang!bang", base_dir=tmp_path)] == [
        "bang!bang.txt"
    ]
