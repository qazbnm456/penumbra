"""A capture's id: a temporary `nd-<hash>` until its text is a kit memory item, then the item's
`m<n>`, with the temporary one kept as `former_id` and still resolving everywhere.

Offline, real SQLite in the tmp_path conftest moves into.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from penumbra import filing, horizon, memory_store, organize
from penumbra.schema import Source, SourceBlock

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _source(origin: str = "https://example.com/a", *, text: str = "hello there") -> Source:
    return Source(id="s0", kind="web", origin=origin, blocks=[SourceBlock(locator="whole", text=text)])


def _busy() -> sqlite3.OperationalError:
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = 5  # SQLITE_BUSY
    return exc


def _fail_first_add(monkeypatch) -> None:
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    real, calls = store.add, [0]

    def add(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise _busy()
        return real(*args, **kwargs)

    monkeypatch.setattr(store, "add", add)


# --- the re-key ------------------------------------------------------------------------------------


def test_a_capture_takes_its_item_id_and_keeps_the_temporary_one():
    temp = horizon.node_id_for("pasted:a", "words", origin_is_the_identity=False)
    node = horizon.add_node(_source("pasted:a", text="words"))
    [item] = memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", temp)
    assert (node.id, node.former_id) == (item.id, temp)
    assert horizon.get_node(temp) == node == horizon.get_node(node.id)
    assert horizon.resolve_id(temp) == horizon.resolve_id(node.id) == node.id
    assert horizon.ids_of(temp) == {temp, node.id}
    assert horizon.node_blocks_path(temp).exists(), "the blocks file keeps the temporary name"


def test_a_capture_still_being_read_has_only_its_temporary_id():
    pending = horizon.add_pending_node("https://example.com/q", "web")
    assert pending.id.startswith("nd-") and pending.former_id is None
    assert horizon.resolve_id(pending.id) == pending.id


def test_the_re_key_moves_every_row_that_names_the_capture(monkeypatch):
    """`memberships` and `pending_memberships` cascade; the tables other modules create do not, so
    the re-key updates each by name, read from the file's foreign keys."""
    _fail_first_add(monkeypatch)
    waiting = horizon.add_node(_source("pasted:w", text="waiting words"))
    assert waiting.state == "stored_unindexed" and waiting.id.startswith("nd-")
    temp = waiting.id
    with horizon._connect() as conn:
        filing._ensure(conn)
        conn.executescript(organize._LEFT_SCHEMA)
        conn.execute("INSERT INTO filing_dismissed (node_id, orbit_id, dismissed_at) "
                     "VALUES (?, 'o', 0)", (temp,))
        conn.execute("INSERT INTO organize_left (node_id, orbits, left_at) VALUES (?, 'sig', 0)", (temp,))
        conn.execute("INSERT INTO memberships (node_id, orbit_id, source_id, promoted_at) "
                     "VALUES (?, 'm', 's1', 0)", (temp,))
    done = horizon.index_stored(temp)
    assert done.id.startswith("m") and done.former_id == temp
    with horizon._connect() as conn:
        for table in ("filing_dismissed", "organize_left", "memberships"):
            ids = {r[0] for r in conn.execute(f"SELECT node_id FROM {table}")}
            assert ids == {done.id}, table
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_an_item_id_already_taken_fails_the_capture_with_the_reason():
    """The kit store deleted under a kept index numbers from `m1` again; the capture that would
    take an id a row already has lands `failed`, it does not raise."""
    first = horizon.add_node(_source("pasted:one", text="first"))
    assert first.id == "m1"
    memory_store.erase(horizon.DEFAULT_HORIZON_DIR)
    second = horizon.add_node(_source("pasted:two", text="second"))
    assert second.state == "failed" and "already in use" in second.error
    assert horizon.get_node("m1").origin == "pasted:one"


# --- every public function resolves the temporary id ---------------------------------------------


def test_every_function_that_takes_a_node_id_accepts_the_temporary_one(tmp_path):
    node = horizon.add_node(_source("pasted:x", text="some text"))
    temp = node.former_id
    assert horizon.get_node(temp).id == node.id
    assert horizon.update_node(temp, error=None).id == node.id
    assert horizon.edit_node(temp, tags=["t"]).id == node.id
    assert horizon.edited_fields(temp) == ["tags"]
    assert horizon.claim_node(temp, expect="ready_undistilled", to="distilling") is True
    assert horizon.claim_node(temp, expect="distilling", to="ready_undistilled") is True
    assert horizon.node_source(temp).id == node.id
    assert horizon.has_stored_blocks(horizon.get_node(temp))
    assert horizon.index_stored(temp).id == node.id
    membership = horizon.promote_node(temp, "orb", orbits_dir=tmp_path / "orbits")
    assert membership.node_id == node.id
    assert [m.node_id for m in horizon.memberships_for(temp)] == [node.id]
    assert list(horizon.memberships_for_nodes([temp])) == [temp], "keyed by the id the caller passed"
    filing.dismiss(temp, "elsewhere")
    organize.remember_left({temp}, "sig")
    assert horizon.remove_node(temp) is True
    assert horizon.get_node(temp) is None and horizon.get_node(node.id) is None


# --- dedupe, removal and the address -------------------------------------------------------------


def test_capturing_the_same_content_again_after_the_switch_is_the_same_capture():
    node = horizon.add_node(_source("pasted:same", text="same words"))
    again = horizon.add_node(_source("pasted:same", text="same words"))
    assert again.id == node.id
    url = horizon.add_node(_source(), origin_is_the_identity=True)
    assert horizon.add_pending_node("https://example.com/a", "web").id == url.id
    assert horizon.count_nodes() == 2


def test_removal_by_either_id_purges_the_item_and_frees_the_address():
    node = horizon.add_node(_source("pasted:gone", text="words to forget"))
    store = memory_store.store(horizon.DEFAULT_HORIZON_DIR)
    assert horizon.remove_node(node.former_id) is True
    assert store.find_meta("node_id", node.former_id) == [] and store.get(node.id) is None
    again = horizon.add_node(_source("pasted:gone", text="words to forget"))
    assert again.id != node.id and again.former_id == node.former_id


def test_a_removal_by_item_id_never_deletes_the_text_of_a_capture_made_since():
    node = horizon.add_node(_source("pasted:r", text="kept twice"))
    blocks_file = f"{node.former_id}.json"
    assert horizon.remove_node(node.id) is True
    again = horizon.add_node(_source("pasted:r", text="kept twice"))
    horizon._unlink_blocks_of_gone(blocks_file, base_dir=horizon.DEFAULT_HORIZON_DIR)  # a late unlink
    assert horizon.node_source(again.id).blocks[0].text == "kept twice"
    assert memory_store.store(horizon.DEFAULT_HORIZON_DIR).find_meta("node_id", again.former_id)


# --- claims and the orbit path ---------------------------------------------------------------------


def test_an_orbit_storing_a_queued_capture_releases_its_claim():
    horizon.add_pending_node("https://example.com/a", "web")
    assert horizon.record_orbit_sources("o", [_source()]) == 1
    assert horizon.indexing_in_flight() is False
    assert horizon.clear_all() == 1, "a clear is not refused by a claim nobody holds"


def test_an_orbit_membership_survives_intake_re_keying_the_capture_meanwhile(monkeypatch):
    pending = horizon.add_pending_node("https://example.com/a", "web")

    def intake_stores_it_first(node_id, claim, *, base_dir):
        assert horizon.claim_for_parse(node_id, base_dir=base_dir)
        try:
            horizon.store_blocks(node_id, _source(), base_dir=base_dir)
        finally:
            horizon.release_parse(node_id)
        return False   # intake won; the orbit only records where the capture belongs

    monkeypatch.setattr(horizon, "_claim_unstored", intake_stores_it_first)
    assert horizon.record_orbit_sources("o", [_source()]) == 1
    [membership] = horizon.nodes_in_orbit("o")
    assert membership.node_id == horizon.resolve_id(pending.id) and membership.node_id.startswith("m")


# --- the steps and the epoch ----------------------------------------------------------------------


def _three_b_one_database(base: Path) -> None:
    """A Horizon as the 3b-1 build wrote it: the baseline at version 0, a row, a `node_ids` table."""
    base.mkdir()
    with sqlite3.connect(horizon.index_path(base)) as conn:
        conn.executescript(horizon._SCHEMA)
        conn.execute(f"PRAGMA application_id = {horizon._APPLICATION_ID}")
        conn.execute(
            "INSERT INTO nodes (id, kind, origin, state, created_at, updated_at, blocks_file) "
            "VALUES ('nd-0000000000000001', 'text', 'pasted:x', 'queued', 1, 1, 'nd-0000000000000001.json')"
        )
        # The tables other modules created for themselves then, which steps 10-13 drop.
        conn.executescript(_OLD_MODULE_TABLES)


#: `search.py`'s index and `concepts.py`'s alias tables as builds before the kit's search made them.
_OLD_MODULE_TABLES = """
CREATE TABLE search_rows (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    indexed_at REAL NOT NULL
);
CREATE VIRTUAL TABLE search_fts USING fts5(meta, body, content='', contentless_delete=1);
CREATE TRIGGER search_rows_forget AFTER DELETE ON search_rows BEGIN
    DELETE FROM search_fts WHERE rowid = old.rowid;
END;
CREATE TABLE entity_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL);
CREATE TABLE entity_seen (name TEXT NOT NULL);
INSERT INTO search_rows (node_id, indexed_at) VALUES ('nd-0000000000000001', 1);
"""

#: Every name the dropped tables left in `sqlite_master`, the FTS5 shadow tables included.
_OLD_NAMES = ("search_rows", "search_fts", "search_rows_forget", "entity_aliases", "entity_seen")


def _shape(base: Path) -> list:
    with sqlite3.connect(horizon.index_path(base)) as conn:
        return sorted(conn.execute("SELECT type, name, sql FROM sqlite_master").fetchall(), key=str)


def test_a_database_from_before_the_steps_gains_them_and_a_restart_changes_nothing(monkeypatch):
    base = Path("old")
    _three_b_one_database(base)
    node = horizon.get_node("nd-0000000000000001", base_dir=base)
    assert node is not None and node.former_id is None
    with sqlite3.connect(horizon.index_path(base)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(horizon._MIGRATIONS) == 13
        columns = [r[1] for r in conn.execute("PRAGMA table_info(nodes)")]
        assert "former_id" in columns
        # Steps 4-9: the labels live in the kit's memory store, so their old columns are gone.
        assert not {"title", "summary", "tags", "entities", "edited", "distilled_at"} & set(columns)
        # Steps 10-13: search and the alias tables are the kit's, so Penumbra's copies are gone.
        left = [r[0] for r in conn.execute("SELECT name FROM sqlite_master")
                if r[0].startswith(_OLD_NAMES)]
        assert left == []
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'nodes_former_id'").fetchone()
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'horizon_meta'").fetchone()
    before = _shape(base)
    monkeypatch.setattr(horizon, "_INITIALIZED", set())
    horizon.count_nodes(base_dir=base)
    assert _shape(base) == before, "a second start leaves the schema as it was"


def test_six_processes_bring_one_old_database_through_the_real_steps(tmp_path):
    old = tmp_path / "old"
    _three_b_one_database(old)
    probe = (
        "import sqlite3, sys, time; from penumbra import horizon\n"
        "conn = sqlite3.connect(horizon.index_path(sys.argv[1]), timeout=30)\n"
        "time.sleep(max(0.0, float(sys.argv[2]) - time.time()))\n"
        "horizon._migrate(conn)\n"
        "conn.close()\n"
    )
    import time

    start = time.time() + 1.5
    runs = [subprocess.Popen([sys.executable, "-c", probe, str(old), str(start)], cwd=str(_REPO_ROOT),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(6)]
    results = [run.communicate(timeout=60) for run in runs]
    assert all(run.returncode == 0 for run in runs), [err for _, err in results]
    with sqlite3.connect(horizon.index_path(old)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(horizon._MIGRATIONS)
        assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1
        assert "title" not in [r[1] for r in conn.execute("PRAGMA table_info(nodes)")]


def test_the_epoch_is_made_once_kept_and_replaced_by_a_clear(monkeypatch):
    first = horizon.epoch()
    monkeypatch.setattr(horizon, "_EPOCHS", {})
    assert horizon.cached_epoch() is None
    assert horizon.epoch() == first, "stored, so a restart reads the same one"
    assert horizon.cached_epoch() == first
    horizon.add_node(_source())
    horizon.clear_all()
    assert horizon.cached_epoch() not in (None, first)
    monkeypatch.setattr(horizon, "_EPOCHS", {})
    assert horizon.epoch() == horizon.epoch() != first


def test_a_database_removed_under_the_process_gets_a_new_epoch():
    first = horizon.epoch()
    for suffix in ("", "-wal", "-shm"):
        Path(f"{horizon.index_path()}{suffix}").unlink(missing_ok=True)
    horizon.count_nodes()
    assert horizon.epoch() != first


def test_an_edit_racing_the_switch_lands_on_the_capture(monkeypatch):
    """The temporary id is resolved again inside the write's transaction: a re-key committed after
    the first lookup does not turn the edit into a write to nothing."""
    _fail_first_add(monkeypatch)
    waiting = horizon.add_node(_source("pasted:race", text="raced"))
    real = horizon._resolved

    def resolve_then_rekey(node_id, base_dir):
        out = real(node_id, base_dir)
        monkeypatch.setattr(horizon, "_resolved", real)
        horizon.index_stored(node_id, base_dir=base_dir)   # the switch lands between lookup and write
        return out

    monkeypatch.setattr(horizon, "_resolved", resolve_then_rekey)
    edited = horizon.edit_node(waiting.id, title="Renamed")
    assert edited is not None and edited.id.startswith("m") and edited.title == "Renamed"
    assert edited.edited == ["title"]


def test_filing_a_waiting_capture_survives_it_becoming_an_item_meanwhile(monkeypatch, tmp_path):
    """The orbit file is written first, then the membership; a capture re-keyed between the two is
    filed under its item id, not refused as removed."""
    _fail_first_add(monkeypatch)
    waiting = horizon.add_node(_source("pasted:file", text="filed while it waited"))
    assert waiting.state == "stored_unindexed"
    real = horizon.mutate_orbit

    def write_then_rekey(*args, **kwargs):
        out = real(*args, **kwargs)
        horizon.index_stored(waiting.id)
        return out

    monkeypatch.setattr(horizon, "mutate_orbit", write_then_rekey)
    membership = horizon.promote_node(waiting.id, "orb", orbits_dir=tmp_path / "orbits")
    assert membership.node_id.startswith("m") and membership.node_id == horizon.resolve_id(waiting.id)
    assert [m.orbit_id for m in horizon.memberships_for(waiting.id)] == ["orb"]


def test_the_dropped_tables_are_named_only_by_the_steps_that_drop_them():
    """`entity_aliases` and `entity_seen` are also tables in the kit's store, attached as `mem` on
    every labels connection, so an unqualified name left anywhere would quietly read the kit's
    tables (or fail on a write). The four names may occur only in their `DROP TABLE` steps, and a
    deliberate read of the kit's own (`mem.entity_aliases`) is refused too: the kit's methods are
    the way in."""
    import re

    names = re.compile(r"\b(search_rows|search_fts|entity_aliases|entity_seen)\b")
    package = Path(horizon.__file__).parent
    found = []
    for path in sorted(package.rglob("*")):
        if path.suffix not in (".py", ".js", ".html") or not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if names.search(line):
                found.append((path.name, line.strip()))
    drops = {f'"DROP TABLE IF EXISTS main.{n}",' for n in ("search_rows", "search_fts", "entity_aliases",
                                                      "entity_seen")}
    assert sorted(found) == sorted(("horizon.py", d) for d in drops)
    assert {f"DROP TABLE IF EXISTS main.{n}" for n in ("search_rows", "search_fts", "entity_aliases",
                                                  "entity_seen")} <= set(horizon._MIGRATIONS)
