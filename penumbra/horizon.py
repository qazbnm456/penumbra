"""Tier 0 — the Horizon: everything captured, before any of it belongs to an orbit.

    A node is a parsed `Source` that is not bound to an orbit yet, plus the metadata distilled
    from it. Promotion is re-id + append, not re-fetch.

Two rules, both load-bearing, and both ARGUED in
`docs/invariants/78-the-horizon-is-an-index-not-a-corpus.md` rather than restated here: **nothing at
Tier 0 ever assembles a corpus blob** — which is how this coexists with invariant 8's
8,000,000-character cap while holding thousands of nodes — and **every write to the index is a SQL
DELTA** (`update_node`; there is deliberately no `save_node`, and `promote_node`'s
`INSERT OR REPLACE` into `memberships` is the one stated exception). The incidents behind both, and
the WAL race that cost a debugging session, are in `CHANGELOG.md`. Three places, one each; see
AGENTS.md's table.

## Storage

    horizon/index.db               SQLite index — one row per node, WAL
    horizon/nodes/<node_id>.json   the parsed Source's blocks, verbatim

Blocks on disk rather than in the database: the index is what a listing renders, and a listing of a
thousand nodes must not carry a thousand corpora. Both paths are relative to the process's working
directory, exactly like `orbits/`, `traces/` and `audio/` — invariant 34's "where you START this
decides where your data lives", applied to a fourth thing rather than given a fifth rule.

## What a reader of THIS file needs, that the invariant does not carry

- **Connections are opened per operation and closed, never pooled or cached at module scope.**
  SQLite connections are cheap, are bound to the thread that created them, and FastAPI runs sync
  handlers on a threadpool — a module-level connection is a `ProgrammingError` waiting for the
  second request.
- **`journal_mode` belongs in `_initialize`, never in `_connect`**, and `busy_timeout` and
  `foreign_keys` belong in `_connect`, every time. Each of those three has its measurement in the
  function that owns it.
- **A caller-supplied node id is validated before it becomes a path** (`node_blocks_path`). Hex ids
  are filename-safe only when this module MINTED them.
- **Import cost, since it is not obvious:** importing this reaches `rlm_harness` transitively —
  `orbit.py` -> `ingest.py` -> `parsers/web.py`, whose SSRF guard is `rlm_harness.tools.fetch`.
  It needs neither the `api` nor the `chatterbox` extra, and `rlm-harness` is a core dependency, so
  a bare `uv sync` is enough. Found by `test_horizon.py`'s subprocess blocker contradicting an earlier
  draft of this paragraph, which claimed stdlib only.
- **WAL needs a real local filesystem** and degrades or fails outright on a network share. The same
  is already true of the orbit JSON files; it just fails more quietly there.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from .atomic import atomic_write_text
from .ingest import is_url
from .orbit import (
    DEFAULT_ORBITS_DIR,
    append_sources,
    load_orbit,
    mutate_orbit,
    orbit_path,
    remove_source,
    slug,
)
from .schema import Node, NodeMembership, Source

_log = logging.getLogger(__name__)

#: Relative to the working directory, same as `orbit.DEFAULT_ORBITS_DIR` and for the same
#: reason (invariant 34).
DEFAULT_HORIZON_DIR = "horizon"

#: How long a writer waits for another writer's transaction before giving up. Seconds here, converted
#: to milliseconds for the pragma. Generous on purpose: the alternative to waiting is an
#: `OperationalError: database is locked` surfacing as a failed capture, and a capture that failed
#: because something else was being written is the least acceptable failure this feature can have.
_BUSY_TIMEOUT_SECONDS = 15.0

#: Columns stored as JSON text. Named once so `_row_to_node` and `update_node` cannot disagree about
#: which ones need encoding — two lists that must match are two lists that will drift.
_JSON_COLUMNS = ("tags", "entities", "preview", "flags")

#: Every column `update_node` will write. A field not in here is rejected rather than silently
#: ignored: a typo'd keyword that quietly does nothing is the failure mode this is guarding, and it
#: also keeps `id`/`created_at` out of reach, which are the two things that must never change.
_UPDATABLE = frozenset(
    {"kind", "origin", "state", "error", "title", "summary", "tags", "entities", "preview", "flags", "chars"}
)

#: One validator per `Node` field, built once. `_UPDATABLE` checks the column NAME; this checks the
#: VALUE, and without it `update_node(id, state="bogus")` committed happily and then every later
#: `get_node`/`list_nodes` raised `ValidationError` on the read-back — one bad write making the whole
#: LISTING unreadable, not just its own row. Rejecting on the way in matches the discipline
#: `orbit.list_orbit_summaries` already applies on the way out (invariants 5/6: flag, never
#: silently drop). `pydantic.ValidationError` subclasses `ValueError`, so callers already catching
#: `ValueError` are unaffected.
_FIELD_ADAPTERS = {name: TypeAdapter(field.annotation) for name, field in Node.model_fields.items()}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id         TEXT PRIMARY KEY,
    kind       TEXT    NOT NULL,
    origin     TEXT    NOT NULL,
    state      TEXT    NOT NULL,
    error      TEXT,
    title      TEXT,
    summary    TEXT,
    tags       TEXT    NOT NULL DEFAULT '[]',
    entities   TEXT    NOT NULL DEFAULT '[]',
    preview    TEXT    NOT NULL DEFAULT '{}',
    flags      TEXT    NOT NULL DEFAULT '[]',
    chars      INTEGER NOT NULL DEFAULT 0,
    created_at REAL    NOT NULL,
    updated_at REAL    NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
    node_id     TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    orbit_id TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    promoted_at REAL NOT NULL,
    PRIMARY KEY (node_id, orbit_id)
);
CREATE INDEX IF NOT EXISTS nodes_state_created ON nodes(state, created_at DESC);
CREATE INDEX IF NOT EXISTS nodes_created ON nodes(created_at DESC);
CREATE INDEX IF NOT EXISTS memberships_orbit ON memberships(orbit_id);
"""


def horizon_dir(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Path:
    return Path(base_dir)


def index_path(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Path:
    return horizon_dir(base_dir) / "index.db"


#: The exact shape `node_id_for` mints. A WHITELIST, deliberately coupled to the minting format:
#: changing one without the other should fail loudly here rather than widen a path.
_NODE_ID_RE = re.compile(r"^nd-[0-9a-f]{16}$")


def is_node_id(value: str) -> bool:
    """Whether `value` is the shape `node_id_for` mints.

    Public because a caller needs to tell "not an id" from "no such node" WITHOUT reaching for the
    pattern itself — the HTTP layer maps the first to 400 and the second to 404 (invariant 27), and
    `get_node` cannot make that distinction on its own: it is a SQL lookup, so a malformed id simply
    misses and looks identical to a missing one.
    """
    return bool(_NODE_ID_RE.match(value))


def node_blocks_path(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Path:
    """The file holding one node's blocks — and the ONLY place a caller-supplied id becomes a path.

    **Validated, because "the id is hex so it is filename-safe" is true of ids this module MINTS and
    false of ids it RECEIVES.** That is precisely the distinction invariant 10 exists to make, and an
    earlier draft of invariant 78 asserted the opposite — which would have told whoever writes
    `DELETE /horizon/{node_id}` that no guard was needed. It was not theoretical: `remove_node` then
    unlinked `f"{node_id}.json"` with no check, so `remove_node("../../orbits/mynb")` deleted a
    live orbit file and returned `False`, and an absolute id discarded the directory entirely
    (`Path("horizon/nodes") / "/etc/x"` is `/etc/x`). Both reproduced before this was written.

    Two checks, not one. The pattern is the real guard; the containment assertion below is
    format-independent depth, so a later change to the minting format cannot quietly reopen this.
    """
    if not _NODE_ID_RE.match(node_id):
        raise ValueError(f"not a node id: {node_id!r} (expected {_NODE_ID_RE.pattern})")
    root = (horizon_dir(base_dir) / "nodes").resolve()
    path = (root / f"{node_id}.json").resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"node id escapes the horizon: {node_id!r}")
    return path


def node_id_for(origin: str, text: str = "", *, origin_is_the_identity: bool | None = None) -> str:
    """A node's stable handle.

    Hashed from the ORIGIN for a URL, so **dedupe is free and automatic**: the same URL captured
    twice is the same row, which is the property invariant 12 already requires of `--source`. It has
    to be the origin alone there, and only there: a queued capture gets its node id from
    `add_pending_node` BEFORE anything is fetched (invariant 79), so for the one kind of origin that
    can be queued the id must be mintable with no content in hand. `capture_into_horizon` refuses
    anything that is not `is_url` before it reaches the queue, so that set is exactly the URLs.

    **Every other origin folds in the TEXT, because a filename is not an identity.** Two different
    files both called `notes.txt` hashed to one node: `add_node` found the row already there,
    returned it untouched, and the second file's content was discarded — while the batch answered
    `{"nodes": [A, A], "refused": []}`, reporting both as landed. That is invariant 79's promise
    ("a capture always lands") broken in the one way it cannot be seen, since nothing failed.

    Pasted text already carried its own content hash (`ingest.ingest_pasted_text` builds
    `f"pasted:{snippet} #{hash}"`), so folding the text in changes nothing about ITS behaviour —
    same text is still one node, one character of difference is still two. It does change the id
    VALUE for both paste and upload, so a paste captured before this lands and re-pasted after it
    makes a second node instead of deduping. Stored rows keep the id they were written with; the
    cost is one duplicate for one re-paste, against silently dropping an uploaded file.

    NFC-normalized before hashing, for invariant 10's reason: two Unicode spellings of the same name
    must not become two nodes. And the result is hex, so it is filename-safe by construction —
    invariant 10's traversal problem cannot arise here at all, and there is no `slug()` step to get
    wrong.

    This is NOT the source id it eventually gets. That is assigned at promotion, by
    `orbit.append_sources`, from the max id in use (invariant 50).
    """
    stable = origin.strip()
    #: **The CAPTURE PATH decides this, not a `startswith` test on an arbitrary string.** An
    #: upload's origin is the caller-supplied multipart filename, so a file NAMED
    #: `https://example.com/paper.md` took the origin-only branch: two different files with that
    #: name collapsed to one node and the second was discarded under `refused: []` — verbatim the
    #: failure this function's docstring says it closed — and the same id then collided with a real
    #: capture of that URL, showing the reader other bytes under its name. Not reachable from the
    #: UI (a `File`'s `.name` cannot contain `/`) and fully reachable by any token holder crafting
    #: the multipart body.
    #:
    #: `add_pending_node` is the one caller that genuinely has no content yet (invariant 79: the
    #: node exists before the fetch), and it says so. Everything else has the bytes in hand.
    if origin_is_the_identity is None:
        origin_is_the_identity = is_url(stable)
    if not stable:
        material = text
    elif origin_is_the_identity:
        material = stable
    else:
        # NUL separator: it cannot occur in a filename, so no (origin, text) pair can be spelled
        # two ways. The id is a sha256 input, never a DOM string — invariant 58's `CSS.escape`
        # problem with U+0000 is a different layer.
        material = f"{stable}\x00{text}"
    digest = hashlib.sha256(unicodedata.normalize("NFC", material).encode("utf-8")).hexdigest()
    return f"nd-{digest[:16]}"


#: Serialises the read-then-insert in `add_node`. See that function for why a lock is needed at all
#: when the table already has a `PRIMARY KEY`.
_CAPTURE_LOCK = threading.Lock()

#: Databases this PROCESS has already put into WAL and created the schema in, keyed by resolved
#: path. Holds strings, never connections — see the module docstring on why nothing is pooled.
_INITIALIZED: set[str] = set()
_INIT_LOCK = threading.Lock()


def _migrate_legacy_schema(conn: sqlite3.Connection) -> None:
    """The one column the rename to Penumbra changed on disk: `memberships.notebook_id` is
    `orbit_id` now. A database written before the rename is renamed in place, once, before the
    schema's `CREATE INDEX ... (orbit_id)` would fail against the old column. Everything else in
    the file (the node rows, their JSON columns) was never named after a notebook."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(memberships)")]
    if "notebook_id" in columns and "orbit_id" not in columns:
        conn.execute("ALTER TABLE memberships RENAME COLUMN notebook_id TO orbit_id")
        conn.execute("DROP INDEX IF EXISTS memberships_notebook")
        conn.commit()


def _initialize(path: Path) -> None:
    """Set WAL and create the schema ONCE per process, not once per connection.

    **`PRAGMA journal_mode=WAL` is the one statement here that a `busy_timeout` does not protect.**
    Changing the journal mode needs an exclusive lock, and SQLite does NOT invoke the busy handler
    for it — it returns `SQLITE_BUSY` immediately while any other connection is active. An earlier
    draft ran the pragma on every connection, which read as harmless ("WAL is a property of the
    file, so re-setting it is a no-op"). It is a no-op only once the mode is ALREADY WAL; while a
    brand-new database is being created, ten concurrent writers race on the change itself.

    MEASURED, not reasoned about: `test_concurrent_writers_all_land` failed roughly one run in six
    with `OperationalError: database is locked`, and a probe that looped on a fresh directory put
    the traceback on this exact pragma. `_INIT_LOCK` removes the in-process race outright; the retry
    covers two PROCESSES creating the same new database at the same moment, which no in-process lock
    can see.
    """
    key = str(path.resolve())
    with _INIT_LOCK:
        # `path.exists()` as well as the cache: a cached key with no file left behind it means the
        # database was removed under a running process (`rm -rf horizon/` is an ordinary thing for a
        # user to do). Without the second half, `_connect` recreates the DIRECTORY, `sqlite3.connect`
        # makes an empty file, and every call afterwards raises `no such table: nodes` for the life
        # of the process. The DDL is all `IF NOT EXISTS`, so re-running it costs one statement.
        if key in _INITIALIZED and path.exists():
            return
        _INITIALIZED.discard(key)
        last: sqlite3.OperationalError | None = None
        for attempt in range(10):
            conn = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_SECONDS)
            try:
                conn.execute(f"PRAGMA busy_timeout={int(_BUSY_TIMEOUT_SECONDS * 1000)}")
                mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if str(mode).lower() != "wal":
                    raise sqlite3.OperationalError(f"journal_mode is {mode!r}, not wal")
                _migrate_legacy_schema(conn)
                conn.executescript(_SCHEMA)
            except sqlite3.OperationalError as exc:
                last = exc
                time.sleep(0.02 * (attempt + 1))
                continue
            else:
                _INITIALIZED.add(key)
                return
            finally:
                conn.close()
        raise last  # every iteration either returns or assigns this, so it is never None here


@contextmanager
def _connect(base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Iterator[sqlite3.Connection]:
    """One connection, one operation, then closed. See the module docstring for why it is not
    pooled. `isolation_level=None` turns OFF the driver's implicit transaction handling so nothing
    hidden wraps the statements below."""
    path = index_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _initialize(path)
    conn = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_SECONDS, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        # Both of these are per-CONNECTION and must be set every time — the half that is easy to
        # assume is sticky and is not. `foreign_keys` is OFF by default in SQLite, so without it the
        # `ON DELETE CASCADE` on `memberships` is decoration and removing a node orphans its rows.
        conn.execute(f"PRAGMA busy_timeout={int(_BUSY_TIMEOUT_SECONDS * 1000)}")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def _row_to_node(row: sqlite3.Row) -> Node:
    data = dict(row)
    for column in _JSON_COLUMNS:
        data[column] = json.loads(data[column])
    return Node.model_validate(data)


def add_node(
    source: Source,
    *,
    origin_is_the_identity: bool = False,
    state: str = "ready_undistilled",
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> Node:
    """Put an already-parsed `Source` into the Horizon, returning the node.

    **Idempotent on the node id, which is idempotent on the origin.** Capturing the same URL twice
    returns the existing node untouched rather than raising or duplicating — this is a bag you throw
    things into, and "you already have that" is not an error a reader should have to handle. The
    blocks file is only written when the row is new, so a re-capture cannot overwrite blocks another
    orbit's promotion already copied from.

    Takes the parsed `Source` rather than a URL on purpose: parsing is invariant 3's host-side,
    SERIAL business and belongs to the caller that owns the queue, not to the storage layer.
    """
    now = time.time()
    #: The content is in hand here, whatever the origin looks like — an upload's origin is a
    #: filename the caller chose and is not an identity, even when it is spelled like a URL.
    node_id = node_id_for(
        source.origin,
        "\n".join(block.text for block in source.blocks),
        origin_is_the_identity=origin_is_the_identity,
    )
    blocks_path = node_blocks_path(node_id, base_dir=base_dir)
    # `_CAPTURE_LOCK` because SELECT-then-INSERT is a check-then-act, and `isolation_level=None`
    # means each statement is its own transaction with nothing spanning the two. MEASURED before it
    # was fixed: eight threads capturing one origin from a barrier produced SEVEN
    # `IntegrityError: UNIQUE constraint failed`, against a docstring promising "rather than
    # raising" — and `IntegrityError` is not an `OperationalError`, so `busy_timeout` never sees it
    # and nothing retries. The same run left `row.chars = 80` against 40 characters of blocks on
    # disk, because every losing thread still wrote the file.
    with _CAPTURE_LOCK, _connect(base_dir) as conn:
        existing = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if existing is not None:
            return _row_to_node(existing)
        if blocks_path.exists():
            # Blocks with no row: a previous capture died between the two writes below. ADOPT them
            # rather than overwrite — the surviving text may already have been read, and adopting is
            # what keeps `chars` agreeing with what is actually on disk.
            stored = json.loads(blocks_path.read_text(encoding="utf-8"))
        else:
            # Blocks BEFORE the row. A row whose blocks file is missing is a node that renders and
            # then fails to open; a blocks file with no row is invisible garbage the branch above
            # adopts on the next capture. Only one of the two orderings can strand a visible node.
            stored = [block.model_dump() for block in source.blocks]
            atomic_write_text(blocks_path, json.dumps(stored, ensure_ascii=False))
        conn.execute(
            "INSERT INTO nodes (id, kind, origin, state, flags, preview, chars, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
            (
                node_id,
                source.kind,
                source.origin,
                state,
                json.dumps(sorted(source.flags)),
                json.dumps(source.preview, ensure_ascii=False),
                sum(len(block["text"]) for block in stored),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row_to_node(row)


def add_pending_node(
    origin: str, kind: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> Node:
    """Record a capture that has not been parsed yet, and return it.

    **A node exists the moment it is enqueued, not when it finishes parsing.** `node_id_for` needs
    only the origin, so the row can be written immediately and the reader sees their capture land
    instantly — which is the product promise. A spinner with nothing behind it is not.

    `kind` comes from `ingest.kind_for`, which decides from the origin without reading anything. It
    is exact for every input `ingest_one` handles today; the worker overwrites it from the parsed
    `Source` as defence, not as a correction of something that happens now.

    There is no blocks file until `store_blocks`, which is exactly the "blocks with no row" state
    `add_node` adopts rather than overwrites, read from the other side.

    An empty origin is refused rather than hashed: queueing "nothing" has no meaning, and
    `node_id_for`'s content fallback needs content, which by definition does not exist yet.
    """
    if not origin.strip():
        raise ValueError("a queued node needs an origin — there is nothing else to identify it by")
    now = time.time()
    #: The ONE place the origin is the whole identity: there is no content yet to fold in, which is
    #: why a queued capture can be given a row before anything is fetched. `capture_into_horizon`
    #: refuses anything that is not `is_url` before it reaches the queue, so this stays the URL set.
    node_id = node_id_for(origin, origin_is_the_identity=True)
    with _CAPTURE_LOCK, _connect(base_dir) as conn:
        existing = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if existing is not None:
            return _row_to_node(existing)
        conn.execute(
            "INSERT INTO nodes (id, kind, origin, state, created_at, updated_at) "
            "VALUES (?, ?, ?, 'queued', ?, ?) ON CONFLICT(id) DO NOTHING",
            (node_id, kind, origin, now, now),
        )
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row_to_node(row)


def store_blocks(
    node_id: str,
    source: Source,
    *,
    state: str = "ready_undistilled",
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> Node | None:
    """Attach a parsed `Source` to a node that was queued, and move it on.

    The blocks file is written FIRST and the row updated after, the same ordering `add_node` uses
    and for the same reason: a row that claims to be ready with no blocks behind it is a node that
    renders and then fails to open.

    Everything the row learns from the parse is applied as ONE delta (invariant 78), including
    `kind`. That last one used to be pure defence against a hypothetical; it is now LOAD-BEARING.
    `parse_web` sniffs content type, so a `.pdf` URL is filed `web` at capture (`kind_for` decides
    without reading anything) and comes back `pdf` from the parse — the row learns what it actually
    is the moment there is something to learn it from. `error` is cleared explicitly, so a node that
    failed and was retried does not keep the old message next to a successful parse.
    """
    path = node_blocks_path(node_id, base_dir=base_dir)
    atomic_write_text(
        path, json.dumps([block.model_dump() for block in source.blocks], ensure_ascii=False)
    )
    node = update_node(
        node_id,
        base_dir=base_dir,
        state=state,
        kind=source.kind,
        chars=sum(len(block.text) for block in source.blocks),
        flags=sorted(source.flags),
        preview=source.preview,
        error=None,
    )
    if node is None:
        # The row was REMOVED while the parse was running, so the blocks just written belong to
        # nothing. Leaving them is not merely untidy: `add_node` ADOPTS an orphan blocks file (that
        # branch exists for a crash between the two writes), so the next capture of this origin
        # would silently get this stale text instead of what it just fetched. Measured before this
        # line existed: a re-capture with 10 characters of fresh text reported `chars=4`, the length
        # of the orphan.
        path.unlink(missing_ok=True)
    return node


def get_node(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Node | None:
    with _connect(base_dir) as conn:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row_to_node(row) if row is not None else None


#: The columns a text query looks in, and the reason the Horizon needs no second store to be
#: searchable. Distillation exists to make a node findable by DESCRIPTION rather than by the exact
#: words you have forgotten (invariant 80), and these four are what it produces — so searching
#: anything else would be searching the wrong thing. `origin` is in there because a URL is often
#: the one word a person does remember.
#:
#: Deliberately NOT the block text. That lives on disk, one file per node (invariant 78), and
#: reading a thousand of them to answer a keystroke is exactly the shape the index exists to avoid.
#: A local substring search over the distilled fields is the honest scope, and it is what the
#: product promises.
_SEARCHABLE = ("title", "summary", "tags", "entities", "origin")


def _search_clause(query: str | None) -> tuple[str, list[object]]:
    """A parameterised `LIKE` over `_SEARCHABLE`, ANDed across whitespace-separated terms.

    `tags` and `entities` are JSON arrays stored as text, so this is a substring match across the
    serialised form: searching `design` finds a node tagged `design` and would also find one tagged
    `redesigned`. That is a real imprecision and the right trade for a box you type into — a token
    search would need a second table and would still be wrong about CJK, which has no word
    boundaries to tokenise on.

    **Each whitespace-separated term is its own condition, and all of them must match.** A single
    `%design Rams%` was one substring against one column, so clicking the `design` tag and then
    typing ` Rams` returned nothing at all — although "Rams" is the first word of that very node's
    summary. That is the product's core promise failing in its most natural gesture: narrow by tag,
    then add the word you remember. Terms may land in DIFFERENT columns (`design` in `tags`, `Rams`
    in `summary`), which a single needle can never express.

    **CJK behaviour is unchanged, and that is the point of splitting on whitespace only.** A Chinese
    query carries no spaces, so it stays exactly one term and exactly one substring match — the
    behaviour a script with no word boundaries needs. A mixed query ("設計 Rams") splits into two,
    which is also right.

    Bounded at eight terms: past that a query is a paste accident, and each term costs five `LIKE`s.

    SQLite's `LIKE` is case-insensitive for ASCII, and case does not exist for Han, so the two
    scripts this interface actually serves both behave.
    """
    terms = (query or "").split()[:8]
    if not terms:
        return "", []
    clauses: list[str] = []
    params: list[object] = []
    for term in terms:
        clauses.append(
            "(" + " OR ".join(f"{column} LIKE ? ESCAPE '!'" for column in _SEARCHABLE) + ")"
        )
        #: **`_` is escaped and `%` deliberately is not**, which is not an inconsistency. `%` is a
        #: recorded decision — typing one is the operator working, and nobody types `%` by accident.
        #: `_` is an ordinary character in exactly the text this searches: `my_notes.txt`,
        #: `design_system`, every snake_case filename and half the URLs. Unescaped it is LIKE's
        #: single-character wildcard, so searching `my_notes` also returned `myXnotes.txt` — a
        #: silently wrong result in the product's one search box, with nothing on screen to explain
        #: it. The escape character is `!` rather than `\` because SQLite gives backslash no special
        #: meaning in a string literal, so `ESCAPE '\'` is a real backslash and a confusing one.
        escaped = term.replace("!", "!!").replace("_", "!_")
        params.extend([f"%{escaped}%"] * len(_SEARCHABLE))
    return "(" + " AND ".join(clauses) + ")", params


#: **Rows whose JSON columns still parse.** `list_nodes` SKIPS an unreadable row so the front page
#: cannot be taken down by one of them; `count_nodes` was a bare `COUNT(*)` over the same WHERE and
#: went on counting it. The two then disagreed in the one place it costs money: a summary pass
#: announced `total: 4` from the count and could only ever reach 3, because the fourth was invisible
#: to the listing — a number on a spend action that can never be reached, which is invariant 60's
#: rule. `Load more` also stayed offered on a page that already held everything.
#:
#: `json_valid()` is SQLite's own (JSON1, built into every build Python ships) — but "one cheap
#: query at thousands of rows", which this used to claim, is not true and the claim was the
#: problem. A function call on four unindexed columns makes `nodes_state_created` unusable BY
#: CONSTRUCTION, so every count is a full scan. Measured by an independent review at 30,000 rows
#: after `ANALYZE`: `count_nodes()` 11.89ms (`SCAN nodes`) against 0.15ms for a plain `COUNT(*)`
#: (`SCAN nodes USING COVERING INDEX nodes_created`), and with a state filter 12.68ms against
#: 2.20ms (`SEARCH ... USING COVERING INDEX`). `GET /horizon` pays it twice and the page polls at
#: ~2.2 requests a second while anything is busy, on the DEFAULT screen, for an index invariant 78
#: aims at thousands of nodes.
#:
#: Kept anyway, because the alternative is the disagreement above — a spend action announcing a
#: total it can never reach. The way out is a persisted `readable` flag maintained on write, which
#: needs a schema migration this database has no mechanism for (`CREATE TABLE IF NOT EXISTS` and no
#: `user_version`); that mechanism is the prerequisite and is recorded as such rather than being
#: bolted on under a performance fix. At the scale the product actually runs at — hundreds to low
#: thousands — 12ms is a cost worth paying for a number that is true.
#:
#: **Stated limit:** this catches a column that is not JSON, which is the reproduced case and the
#: likely one (a hand-edit, a partial restore). A column that is VALID JSON of the wrong shape still
#: counts here and is still skipped by `list_nodes`, so the two can disagree again — `list_nodes`
#: keeps its own guard for that, and the row is reachable and removable either way, which is what
#: the last round's version was not.
_READABLE = " AND ".join(f"json_valid({column})" for column in _JSON_COLUMNS)


def _where(state: str | None, query: str | None) -> tuple[str, list[object]]:
    parts: list[str] = [_READABLE]
    params: list[object] = []
    if state is not None:
        parts.append("state = ?")
        params.append(state)
    clause, extra = _search_clause(query)
    if clause:
        parts.append(clause)
        params.extend(extra)
    return " WHERE " + " AND ".join(parts), params


def list_nodes(
    *,
    state: str | None = None,
    query: str | None = None,
    limit: int = 100,
    offset: int = 0,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> list[Node]:
    """Newest first. Paged rather than "everything", because the whole premise is that this grows
    past what an orbit could hold — a listing that loads all of it has the problem Tier 0 exists
    to avoid, one level up."""
    where, params = _where(state, query)
    sql = f"SELECT * FROM nodes{where} ORDER BY created_at DESC, id ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect(base_dir) as conn:
        rows = conn.execute(sql, params).fetchall()
    #: **ONE UNREADABLE ROW MUST NOT COST THE LISTING.** `_row_to_node` calls `json.loads` and
    #: `Node.model_validate`, and this endpoint is the application's FRONT PAGE — a single row that
    #: a hand-edit, a partial restore or a future required field made unparseable turned it into a
    #: bodyless 500, so nothing rendered at all. `_FIELD_ADAPTERS`' own comment gives this exact
    #: reasoning ("one bad write making the whole listing unreadable"), and the validator it
    #: describes only guards `update_node`, which is the write side.
    #:
    #: SKIPPED AND LOGGED, never silently dropped: the same "flag, never hide" shape
    #: `list_orbit_summaries` uses for an unparseable orbit file.
    out: list[Node] = []
    for row in rows:
        try:
            out.append(_row_to_node(row))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            _log.warning("horizon: skipping unreadable row %r (%s)", dict(row).get("id"), exc)
    return out


def count_nodes(
    *,
    state: str | None = None,
    query: str | None = None,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
) -> int:
    where, params = _where(state, query)
    with _connect(base_dir) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM nodes{where}", params).fetchone()[0])


def update_node(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR, **fields: object) -> Node | None:
    """Apply a DELTA — only the fields named — and return the node as it now is, or `None` if there
    is no such node.

    **This is invariant 34's rule at Tier 0, and the signature is what enforces it.** There is
    deliberately no `save_node(node)`: a whole-object write is precisely the fault invariant 34
    records, where a caller persisted a snapshot it had read before a slow step and destroyed
    everything written meanwhile. Distillation IS that slow step here — a model call between reading
    a node and writing its summary — so the shape is not hypothetical.

    An unknown field raises rather than being ignored, so a typo is a test failure and not a value
    that silently never persisted.
    """
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)} (updatable: {sorted(_UPDATABLE)})")
    assignments = []
    params: list[object] = []
    for column, value in fields.items():
        # The VALUE, not just the column name — see `_FIELD_ADAPTERS`. Raises before anything is
        # written, so a rejected delta leaves the row exactly as it was.
        checked = _FIELD_ADAPTERS[column].validate_python(value)
        assignments.append(f"{column} = ?")
        params.append(json.dumps(checked, ensure_ascii=False) if column in _JSON_COLUMNS else checked)
    assignments.append("updated_at = ?")
    params.extend([time.time(), node_id])
    with _connect(base_dir) as conn:
        conn.execute(f"UPDATE nodes SET {', '.join(assignments)} WHERE id = ?", params)
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row_to_node(row) if row is not None else None


#: The states that mean "a process owns this node RIGHT NOW", and what each one falls back to once
#: that process is gone. ONE map, in the module that owns the states, because they are the same
#: fact — `intake.py` had a reset for `parsing` and `distilling` had none at all, so a crash or a
#: failed write between claiming a node and summarising it stranded it in a state NOTHING selects
#: (`distil_pending` queries `ready_undistilled`), with the model call already paid for.
#:
#: `distilling` falls back to `ready_undistilled`, not to `queued`: the blocks are already on disk,
#: so only the summary is missing, and that is exactly what `ready_undistilled` means.
_OWNED_STATES = {"parsing": "queued", "distilling": "ready_undistilled"}


def reset_interrupted_states(*, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> dict[str, list[str]]:
    """Return every node stuck in a state whose owning process is gone, keyed by the state it was
    stuck in. Call this at startup, before anything else reads the index.

    A state that names a live owner is a LIE once the owner is not there — `intake.py` already
    writes that argument for `parsing`, and this is the same sentence applied to both. Nothing here
    is conditional on how the process died; if a row is in one of these states at boot, no worker
    in THIS process put it there.
    """
    recovered: dict[str, list[str]] = {}
    for stale, fallback in _OWNED_STATES.items():
        ids = [node.id for node in list_nodes(state=stale, limit=100_000, base_dir=base_dir)]
        for node_id in ids:
            claim_node(node_id, expect=stale, to=fallback, base_dir=base_dir)
        if ids:
            recovered[stale] = ids
    return recovered


def claim_node(
    node_id: str, *, expect: str, to: str, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> bool:
    """Move a node from `expect` to `to` ONLY if it is still in `expect`. Returns whether it moved.

    A compare-and-set, because a plain `update_node(state=...)` writes a LABEL, not a claim. Two
    concurrent `distil_pending` passes each snapshotted the same `ready_undistilled` nodes and each
    wrote `state="distilling"` unconditionally — measured: **five model calls for three nodes**, with
    both passes reporting they had distilled the same ids and each overwriting the other's summary.
    The reader pays for that twice.

    One statement, so the check and the write cannot be interleaved — which is the same reasoning
    `add_node`'s `ON CONFLICT` uses, and the reason neither can be expressed as a read followed by an
    `update_node`. Still a DELTA (invariant 78): one column, named explicitly.
    """
    with _connect(base_dir) as conn:
        changed = conn.execute(
            "UPDATE nodes SET state = ?, updated_at = ? WHERE id = ? AND state = ?",
            (to, time.time(), node_id, expect),
        ).rowcount
    return bool(changed)


def remove_node(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> bool:
    """Forget a node. Its memberships go with it (`ON DELETE CASCADE`), but **sources already
    promoted into orbits STAY** — they were copied, and an orbit that silently lost a cited
    source because someone tidied their horizon would break invariant 12's promise that a source
    already cited in a saved turn keeps meaning what it meant."""
    with _connect(base_dir) as conn:
        changed = conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,)).rowcount
    node_blocks_path(node_id, base_dir=base_dir).unlink(missing_ok=True)
    return bool(changed)


def node_source(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> Source | None:
    """The node's parsed `Source`, blocks and all, with the NODE id still in `.id`.

    That id is a placeholder and is meant to be replaced: `append_sources` renumbers whatever it is
    handed against the receiving orbit (invariant 50), and `Source.marker()` derives the citation
    coordinate from `.id` at `Corpus.blob()` time, so nothing stored has the placeholder baked in.
    """
    node = get_node(node_id, base_dir=base_dir)
    if node is None:
        return None
    path = node_blocks_path(node_id, base_dir=base_dir)
    if not path.exists():
        return None
    blocks = json.loads(path.read_text(encoding="utf-8"))
    return Source(
        id=node_id,
        kind=node.kind,
        origin=node.origin,
        blocks=blocks,
        flags=node.flags,
        preview=node.preview,
    )


#: What `node_source` raises when the file is THERE but unreadable, as opposed to absent. Named so
#: every caller catches the same set instead of each guessing: `json.loads` raises
#: `JSONDecodeError` on a truncated or partial file, and `Source(...)` raises pydantic's
#: `ValidationError` on a well-formed file of the wrong shape — which is also what EVERY node
#: already on disk would raise the day `schema.Source` gains a required field. For a product whose
#: premise is "get it back months later", that is not a hypothetical.
#:
#: `OSError` is in here too: a file that exists at `exists()` time can still fail to read.
UNREADABLE_SOURCE = (json.JSONDecodeError, ValidationError, OSError)


class UnreadableNodeText(ValueError):
    """A node's blocks file is present and cannot be read.

    **Raised where the cause is KNOWN, because the caller cannot tell.** `promote_node` reads the
    node's text and then writes an orbit, and `pydantic.ValidationError` comes out of both — so an
    API handler catching it broadly cannot say which file is broken. It tried, and told the operator
    to "fix or remove by hand" an `orbits/<id>.json` that parsed perfectly well: destructive
    advice about an unrelated file. Narrowing the catch to the one call that knows is the fix;
    widening it at the handler just moves the confusion.

    Subclasses `ValueError` so an existing `except ValueError` arm still degrades to a 4xx rather
    than letting this escape as a 500 (invariant 27's reasoning), while a handler that wants to say
    something specific can catch it first.
    """


def memberships_for(node_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[NodeMembership]:
    with _connect(base_dir) as conn:
        rows = conn.execute(
            "SELECT * FROM memberships WHERE node_id = ? ORDER BY promoted_at ASC", (node_id,)
        ).fetchall()
    return [NodeMembership.model_validate(dict(row)) for row in rows]


def forget_membership(
    orbit_id: str, source_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR
) -> int:
    """Drop the membership rows that pointed at a source which no longer exists. Returns how many.

    **A membership outlived its source.** Promoting a node writes `(node_id, orbit_id,
    source_id)`; removing that source from the orbit (invariant 50 — the survivors are never
    renumbered, so the id is simply gone) left the row behind, so `GET /horizon/{node_id}` went on
    reporting the node as filed there and the Horizon row went on saying "already in <orbit>".
    Re-promoting worked, which is why this is a display inaccuracy rather than data loss — but the
    display is the whole point of Tier 0: the one question a capture index has to answer is "where
    did this end up".

    A SQL delta, like every other write here (invariant 78), and keyed on the SOURCE id rather than
    the node: one node can be promoted into several orbits, and only this orbit's copy went
    away.
    """
    with _connect(base_dir) as conn:
        cur = conn.execute(
            # The SLUG on both sides, matching what `promote_node` writes: the caller here is an
            # HTTP path segment, which can be the raw id or the slug, and the file they name is the
            # same file either way.
            "DELETE FROM memberships WHERE orbit_id = ? AND source_id = ?",
            (slug(orbit_id), source_id),
        )
        return cur.rowcount or 0


def forget_orbit(orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> int:
    """Drop every membership row for an orbit that no longer exists. Returns how many.

    The whole-orbit twin of `forget_membership`, for the same reason and with the same shape: an
    index entry pointing at something that is gone is simply wrong, and the one question a capture
    index has to answer is "where did this end up". Without it, deleting an orbit left every node
    it held reporting `In <that orbit>` forever — and the label would resolve, because the
    membership carries the slug and nothing re-checks that the file is still there.

    Nodes themselves are untouched: promotion COPIES (invariant 78), so a node outlives any orbit
    it was filed into, which is the same reasoning `remove_node` uses in the other direction.
    """
    with _connect(base_dir) as conn:
        cur = conn.execute("DELETE FROM memberships WHERE orbit_id = ?", (slug(orbit_id),))
        return cur.rowcount or 0


def nodes_in_orbit(orbit_id: str, *, base_dir: str | Path = DEFAULT_HORIZON_DIR) -> list[NodeMembership]:
    with _connect(base_dir) as conn:
        rows = conn.execute(
            "SELECT * FROM memberships WHERE orbit_id = ? ORDER BY promoted_at ASC",
            (slug(orbit_id),),
        ).fetchall()
    return [NodeMembership.model_validate(dict(row)) for row in rows]


def _unused_origin(orbit, origin: str) -> str:
    """`origin` with a counter inserted until no live source carries it.

    Before the extension rather than after it — `notes (2).txt` reads as a second copy of a text
    file and `notes.txt (2)` reads as a file whose name ends in a number. Only the last dot counts,
    and only when what follows looks like an extension, so `v1.2.tar.gz` does not become
    `v1.2.tar (2).gz`... it becomes `v1.2 (2).tar.gz` only if `tar.gz` were one suffix, which it is
    not: the rule is deliberately the simple one, and a name with no dot just gets ` (2)` appended.
    """
    taken = {s.origin for s in orbit.sources}
    if origin not in taken:
        return origin
    stem, dot, suffix = origin.rpartition(".")
    if not dot or not suffix or len(suffix) > 8 or "/" in suffix:
        stem, suffix = origin, ""
    for n in range(2, 1000):
        candidate = f"{stem} ({n})" + (f".{suffix}" if suffix else "")
        if candidate not in taken:
            return candidate
    #: A thousand same-named files in one orbit is not a case worth a cleverer scheme; the
    #: caller's conflict branch still raises rather than looping forever or shadowing anything.
    return origin


def promote_node(
    node_id: str,
    orbit_id: str,
    *,
    base_dir: str | Path = DEFAULT_HORIZON_DIR,
    orbits_dir: str | Path = DEFAULT_ORBITS_DIR,
    create: bool = True,
) -> NodeMembership:
    """Copy a node into an orbit as a real, citable `Source`, and record that it is there.

    Same verb and the same reasoning as `orbit.promote_note` (invariant 32 — a thing is uncited
    until promoted, and grounded exactly like any other source afterwards). Three properties that
    are each a decision:

    **The node is NOT consumed.** It stays in the Horizon and can be promoted into other orbits.
    That is the "different facets of yourself" premise: the node is what persists, and an orbit is
    a view over a selection of them.

    **The id comes from `append_sources`, never from here.** It renumbers against the receiving
    orbit from the max id in use (invariant 50), inside `mutate_orbit`'s lock and against a
    re-read of the file (invariant 34) — so a concurrent write cannot make two sources share an id.

    **`create` says whether the CALLER meant to make a new orbit**, and defaults True only for
    the library's own callers. The HTTP layer passes what the reader actually chose: the picker in
    the Horizon is built from an orbit list fetched when the page rendered, so an option can name a
    orbit that has since been deleted — no race required. Promoting through that stale option
    re-created it, same handle, same slug, holding one source and none of its title, sources, notes,
    turns or overview, and it reappeared in the facet rail. `DELETE /orbits/{id}` refuses while a
    run is in flight for exactly this reason; a write that started before the delete must not undo
    it either (see `api.add_sources`' `create=not existed`).

    An orbit that does not exist yet is created when `create` is True. Promoting into a new name is
    how a reader starts a facet, so refusing would make "file this somewhere new" a two-step. The
    cost is that a typo'd orbit id silently creates an orbit rather than 404ing; a caller that
    needs the strict behaviour should resolve the orbit first.

    **Promoting something the orbit already has is not an error.** `append_sources` dedupes by
    origin and returns only what it actually appended; when it appends nothing, the orbit already
    holds this origin and the membership is recorded against the source id it already has. The
    alternative — a 409 — would make "add everything from this tag" fail on the one item the reader
    had already added by hand.
    """
    try:
        source = node_source(node_id, base_dir=base_dir)
    except UNREADABLE_SOURCE as exc:
        raise UnreadableNodeText(
            f"node {node_id!r} has a stored text file that cannot be read ({type(exc).__name__})"
        ) from exc
    if source is None:
        raise ValueError(f"no such node, or its blocks are missing: {node_id!r}")

    # THIS node's own prior membership. It is what makes re-promotion idempotent without guessing
    # from the origin — see the conflict branch below for what the guess cost.
    #: **READ INSIDE THE LOCK**, which is why this is a function and not a value. It used to be a
    #: snapshot taken before `mutate_orbit`, and invariant 34 names that fault exactly: a stale
    #: snapshot and interleaved critical sections are two distinct problems, and the lock alone does
    #: not fix the first. Measured with ten concurrent promotions of one node into one orbit:
    #: **8 of 10 answered 400** saying the orbit "already holds a DIFFERENT source with origin
    #: …" — where the different source was the one this call's own sibling had just created a
    #: microsecond earlier. Re-reading inside `apply` sees it and takes the idempotent branch.
    def prior_membership():
        return next(
            (
                m
                for m in memberships_for(node_id, base_dir=base_dir)
                if m.orbit_id == slug(orbit_id)
            ),
            None,
        )

    assigned: list[str] = []
    conflict: list[str] = []
    #: Whether THIS call added a new source, as opposed to finding one already there. Only an
    #: append can be rolled back — see the compensating write below.
    appended_new: list[str] = []

    def apply(orbit):
        appended = append_sources(orbit, [source])
        if appended:
            assigned.append(appended[0].id)
            appended_new.append(appended[0].id)
            return
        # `append_sources` dedupes by ORIGIN, so "appended nothing" means some source here shares
        # this origin — NOT necessarily this node. Matching on origin alone was a real data-loss
        # bug: two distinct nodes that share an origin (the origin-less/pasted path) both recorded a
        # membership pointing at the FIRST node's source, the second node's text never reached the
        # orbit, and `promote_node` returned success. Reproduced before this was written.
        #: **Not subsumed by the blocks comparison below, though it reads as if it were.** An
        #: independent review called this branch a no-op on the grounds that a node's blocks are
        #: immutable, so the equality test further down would reach the same answer — and removing
        #: it fails `test_re_promoting_a_node_whose_text_changed_is_still_idempotent`, every time.
        #: A node's text CAN move (a re-parse calls `store_blocks`), and when it has, the source
        #: copied at promotion no longer matches the node's current blocks: the equality test says
        #: "different" and the promotion is refused as a conflict with itself. The membership row
        #: is the only thing that still knows this node and that source are the same capture.
        prior = prior_membership()
        if prior is not None and any(s.id == prior.source_id for s in orbit.sources):
            assigned.append(prior.source_id)
            return
        other = next((s for s in orbit.sources if s.origin == source.origin), None)
        if other is None:
            return
        #: **Is that source this node's CONTENT, or somebody else's?** The membership table is the
        #: obvious place to ask and it is racy: the row is written after `mutate_orbit` releases
        #: the lock (the two writes are a JSON file under a `flock` and a SQLite row, and the
        #: compensating write below exists because they cannot be one transaction). So a sibling
        #: promotion that has appended the source but not yet recorded its row is invisible here,
        #: and ten concurrent promotions of ONE node produced eight false 400s blaming a source
        #: their own siblings had just created.
        #:
        #: The blocks answer it without a race, and they do so for both kinds of origin. A URL
        #: hashes to ONE node id, so two distinct nodes cannot share a URL origin at all; every
        #: other origin has the text folded INTO the id, so two distinct nodes sharing one
        #: necessarily differ in text. Either way, equal blocks means equal content.
        #:
        #: That second half was only made true by fixing the upload collision this branch was
        #: written to survive: while a filename hashed to one node regardless of content, two
        #: DIFFERENT files called `notes.txt` were one node, and the claim here was simply false.
        if [b.model_dump() for b in other.blocks] == [b.model_dump() for b in source.blocks]:
            assigned.append(other.id)
            return
        #: **A different document with the same name is a second file, not a shadow.** This used to
        #: refuse — "cannot be added without shadowing it" — which was right about shadowing and
        #: wrong about the outcome: nothing in the product can rename a node or a source, so two
        #: `notes.txt` from two folders left one of them permanently unfileable. Invariant 79 got
        #: the capture to land and invariant 78's promotion was then a dead end. Reproduced end to
        #: end by an independent review.
        #:
        #: Disambiguating is neither silent nor shadowing: both sources exist, both are citable, and
        #: the name on screen says which is which. Only the display origin moves — ids come from
        #: `next_source_id` and are never reused (invariant 50).
        renamed = source.model_copy(update={"origin": _unused_origin(orbit, source.origin)})
        again = append_sources(orbit, [renamed])
        if again:
            assigned.append(again[0].id)
            appended_new.append(again[0].id)
            return
        conflict.append(other.id)

    # Whether the orbit EXISTED before this call, so the rollback below knows whether the file
    # itself is ours to undo. `create=True` means a promotion that fails afterwards can otherwise
    # leave an orbit nobody asked for: twelve concurrent promote/delete races all correctly lost
    # the promote and all twelve left `racebook.json` behind, showing in the facet rail as
    # "Untitled orbit · 0".
    existed = orbit_path(orbit_id, base_dir=orbits_dir).exists()
    mutate_orbit(orbit_id, apply, base_dir=orbits_dir, create=create)
    if conflict and not assigned:
        raise ValueError(
            f"{orbit_id!r} already holds a DIFFERENT source ({conflict[0]}) with origin "
            f"{source.origin!r}, so node {node_id!r} cannot be added without shadowing it"
        )
    if not assigned:
        raise ValueError(f"node {node_id!r} was neither appended to nor found in {orbit_id!r}")

    membership = NodeMembership(
        # **KEYED ON THE SLUG, because the slug is what identifies the orbit FILE.** This stored
        # the raw id while `orbit.slug()` decides the filename, so `"Foo Bar"` and `"Foo-Bar"`
        # were one orbit on disk and two rows here: removing the source through the file's id
        # left the other row behind claiming the node was still filed, and the next promotion then
        # handed out the same source id to a different node. Two rows, one `s1`, two different
        # documents. Not reachable through the UI, which mints `nb-<uuid8>` (invariant 37), and
        # fully reachable over HTTP by any token holder.
        node_id=node_id,
        orbit_id=slug(orbit_id),
        source_id=assigned[0],
        promoted_at=time.time(),
    )
    try:
        with _connect(base_dir) as conn:
            # `INSERT OR REPLACE`, because promoting the same node into the same orbit twice is
            # the same "not an error" case as above — the second one just restates where it went.
            conn.execute(
                "INSERT OR REPLACE INTO memberships (node_id, orbit_id, source_id, promoted_at) "
                "VALUES (?, ?, ?, ?)",
                (membership.node_id, membership.orbit_id, membership.source_id, membership.promoted_at),
            )
    except sqlite3.IntegrityError as exc:
        # **The node was REMOVED while this promotion was running.** `memberships.node_id` has a
        # foreign key, so the insert is refused — and by then `mutate_orbit` has already written
        # the source into the orbit file. Measured before this branch existed: two of twelve
        # concurrent promote/delete pairs returned a raw 500 AND left the orbit holding a source
        # no membership row records. The caller saw a failure; the orbit silently grew.
        #
        # The two writes cannot be one transaction — one is a JSON file under a `flock`, the other
        # is SQLite — so the honest repair is a COMPENSATING write: undo the append, and only the
        # append. If this call merely FOUND an existing source, that source belongs to someone else
        # and removing it would be the bug this branch is fixing, inverted.
        if appended_new:
            with contextlib.suppress(ValueError):
                mutate_orbit(
                    orbit_id,
                    lambda nb: remove_source(nb, appended_new[0]),
                    base_dir=orbits_dir,
                    create=False,
                )
        # And the orbit FILE, when this call is what created it and the undo left it empty.
        # Anything else is someone else's orbit: a pre-existing one is never removed, and one
        # that gained content from another writer in the meantime is not ours to judge.
        if not existed:
            path = orbit_path(orbit_id, base_dir=orbits_dir)
            with contextlib.suppress(OSError, ValueError):
                fresh = load_orbit(orbit_id, base_dir=orbits_dir)
                if fresh is not None and not fresh.sources:
                    path.unlink(missing_ok=True)
        raise ValueError(
            f"node {node_id!r} was removed while it was being promoted into {orbit_id!r}; "
            "nothing was added"
        ) from exc
    return membership
