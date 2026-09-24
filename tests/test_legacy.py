"""The rename's on-disk and environment leftovers (`penumbra.legacy`, `horizon._migrate_legacy_schema`)."""

from __future__ import annotations

import sqlite3

from penumbra import horizon, legacy


def test_legacy_folders_move_once_and_never_merge(tmp_path):
    (tmp_path / "notebooks").mkdir()
    (tmp_path / "notebooks" / "a.json").write_text("{}")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "horizon").mkdir()  # already there: the old one must be left alone, not merged

    moved = legacy.migrate_data_dirs(tmp_path)

    assert moved == [("notebooks", "orbits")]
    assert (tmp_path / "orbits" / "a.json").exists()
    assert (tmp_path / "inbox").is_dir(), "a folder is never merged into an existing one"
    assert legacy.migrate_data_dirs(tmp_path) == [], "a second start moves nothing"
    assert legacy.stranded_dirs(tmp_path) == [("inbox", "horizon")], "the unmoved one is reported"


def test_old_environment_names_are_reported_not_honoured():
    env = {"RN_MAIN_MODEL": "x", "PN_API_KEY": "y", "PATH": "/bin"}
    assert legacy.legacy_env_names(env) == ["RN_MAIN_MODEL"]


def test_a_pre_rename_horizon_database_is_migrated_in_place(tmp_path, monkeypatch):
    """A database written before the rename has `memberships.notebook_id`; the schema's index on
    `orbit_id` would fail against it, taking every Horizon request down with it."""
    db = tmp_path / "index.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE memberships (node_id TEXT NOT NULL, notebook_id TEXT NOT NULL,
            source_id TEXT NOT NULL, promoted_at REAL NOT NULL, PRIMARY KEY (node_id, notebook_id));
        CREATE INDEX memberships_notebook ON memberships(notebook_id);
        INSERT INTO memberships VALUES ('nd-1', 'reading', 's1', 1.0);
        """
    )
    conn.commit()
    conn.close()

    horizon._INITIALIZED.discard(str(db.resolve()))
    horizon._initialize(db)

    conn = sqlite3.connect(db)
    columns = [row[1] for row in conn.execute("PRAGMA table_info(memberships)")]
    assert "orbit_id" in columns and "notebook_id" not in columns
    assert conn.execute("SELECT orbit_id FROM memberships").fetchall() == [("reading",)]
    conn.close()
