"""Orbit persistence: sources + chat history that survive across `ask` invocations.

An orbit is one JSON file, `<orbits_dir>/<slug(id)>.json`, holding a `schema.Orbit` — the
sources ingested so far and every prior (question, answer) turn. One file, no database.

**Every mutation goes through `mutate_orbit`, which re-loads from disk inside a per-orbit
lock.** This module used to say "no locking, no concurrent-writer story — there is exactly one
writer at a time," which was true when `cli.py` was the only entry point and has been false since
`api.py` started serving concurrent HTTP requests. A whole-file `save_orbit` of an object read
minutes earlier silently destroys everything written in between — reproduced live over real HTTP
(a source and a note added while an `ask` was running, both returning 200, both gone afterwards);
see AGENTS.md's orbit-durability invariant. Read the `mutate_orbit`/`orbit_lock`
docstrings before adding a new write path.
"""

from __future__ import annotations

import hashlib
import re
import threading
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import ValidationError

from .atomic import atomic_write_text
from .corpus import Corpus
from .ingest import ingest_new, ingest_pasted_text, with_injection_flags
from .schema import Note, Orbit, Source

try:
    import fcntl
except ImportError:  # pragma: no cover — POSIX only; see `orbit_lock` for the fallback
    fcntl = None  # type: ignore[assignment]

DEFAULT_ORBITS_DIR = "orbits"

#: Orbit id used when the caller (CLI/API) doesn't ask for persistence — never actually
#: persisted, so it never collides with a real orbit file on disk regardless of this string.
EPHEMERAL_ID = "_ephemeral"

#: Cap on a slugged orbit id, matching ctx-distillery's `cli._slug`/`_RUN_ID_MAX` reasoning: the
#: id becomes a filename, and most filesystems cap one path component at 255 bytes.
_SLUG_MAX = 120


def slug(raw: str) -> str:
    """A filesystem-safe FILENAME for an orbit id: keep `[A-Za-z0-9._-]`, fold the rest to `-`,
    strip leading and trailing `.`/`-` so it can never become a traversal segment (`..`, an absolute
    path, a nested directory), and cap at `_SLUG_MAX` characters — re-stripping after the cut so a
    truncation landing on a `-`/`.` never leaves a trailing separator. `--orbit` and the API's
    `{orbit_id}` are user input that becomes a path component; see AGENTS.md's orbit-id
    invariant.

    **An id with no Latin characters at all falls back to a content hash rather than failing.** The
    whitelist reduces `"模型要睡覺"` — or any Chinese/Japanese/Korean/Arabic/emoji-only name — to
    the empty string, which `orbit_path` then rejects as an invalid id. A user reported exactly
    that: naming an orbit in Chinese returned `400 invalid orbit id … reduces to an empty
    token`, with nothing to suggest the name was the problem rather than the request. The hash is
    deterministic (same name, same file), collision-resistant across different names, and stays
    inside the same whitelist, so none of the traversal or length reasoning above changes.

    This only ever affects the FILENAME. `Orbit.id` stores the id the user actually typed, and
    `list_orbit_summaries` already reports that stored value rather than the filename stem — a
    property it was given for this exact reason (`slug` being lossy), which is why non-Latin names
    now round-trip through the UI with no further change.

    A genuinely empty or whitespace-only id still returns `""`, and still fails loudly: "you gave me
    nothing" is a real error, unlike "you gave me a name in your own language".
    """
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", raw or "").strip("-.")
    token = token[:_SLUG_MAX].rstrip("-.")
    if token:
        return token
    if not (raw or "").strip():
        return ""
    # NFC first: the same visible name typed in a browser (NFC) and pasted from a macOS filename
    # (NFD) are different byte strings, so an un-normalized hash would silently give one user two
    # orbits with identical-looking names and no way to tell them apart.
    #
    # `surrogatepass`, not plain `encode()`: this function MUST be total. An unpaired surrogate
    # (well-formed JSON per RFC 8259, accepted by `json.loads`, and produced by argv's
    # `surrogateescape` decoding) otherwise raises `UnicodeEncodeError` here — and `api._derive_run_id`
    # calls `slug()` DIRECTLY, outside every `orbit_path` error wrapper, so that surfaced as an
    # unauthenticated 500 on `ask`/`guide`/`audio` via the `run_id` body field. Found and reproduced
    # by an independent review of this very fallback; `slug` never raised before it existed.
    normalized = unicodedata.normalize("NFC", raw)
    return "orbit-" + hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def orbit_path(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> Path:
    return Path(base_dir) / f"{slug_or_raise(orbit_id)}.json"


#: Every audio format a provider may write. A reader has to find whichever one is actually there,
#: because the provider that produced it may not be the one currently configured — `edge-tts` writes
#: `.mp3` and the local provider writes `.wav`, and switching `PN_TTS_PROVIDER` must not make an
#: already-generated episode unreachable.
AUDIO_SUFFIXES = (".mp3", ".wav")


def find_audio(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> Path | None:
    """The orbit's generated audio, whatever format wrote it, or `None`."""
    for suffix in AUDIO_SUFFIXES:
        candidate = audio_path(orbit_id, base_dir=base_dir, suffix=suffix)
        if candidate.exists():
            return candidate
    return None


def clear_audio(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """Remove every format's file, so regenerating with a DIFFERENT provider can't leave the old
    one behind for `find_audio` to serve instead of the new one."""
    for suffix in AUDIO_SUFFIXES:
        audio_path(orbit_id, base_dir=base_dir, suffix=suffix).unlink(missing_ok=True)


def audio_path(
    orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR, suffix: str = ".mp3"
) -> Path:
    """Where an orbit's generated Audio Overview lives: `<base_dir>/audio/<slug>.mp3`.

    A subdirectory, so `list_orbit_summaries`' `*.json` glob never sees it, and ONE file per
    orbit — regenerating replaces it rather than accumulating, so the disk cost is bounded by how
    many orbits exist. Derives from the same validated `slug` every other path here does, so an
    id that reduces to nothing raises before any file is touched."""
    return Path(base_dir) / "audio" / f"{slug_or_raise(orbit_id)}{suffix}"


def slug_or_raise(orbit_id: str) -> str:
    safe = slug(orbit_id)
    if not safe:
        raise ValueError(f"orbit id {orbit_id!r} reduces to an empty token")
    return safe


def load_orbit(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> Orbit | None:
    """Load an orbit by id, or `None` if it doesn't exist yet — the caller decides whether that
    means "create a new one" or "error: no such orbit"."""
    path = orbit_path(orbit_id, base_dir=base_dir)
    if not path.exists():
        return None
    return Orbit.model_validate_json(path.read_text(encoding="utf-8"))


def save_orbit(orbit: Orbit, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> None:
    """Write `orbit` atomically: a same-directory temp file, `fsync`ed, then `os.replace`d onto
    the real path. Found by an independent review that a plain `path.write_text(...)` left a
    truncated, unparseable JSON file behind if the process was interrupted mid-write (Ctrl+C,
    crash, power loss) — the NEXT `load_orbit` call for that id would then raise an uncaught
    `pydantic.ValidationError` with no recovery but deleting the file, silently losing the whole
    conversation. `os.replace` is atomic on both POSIX and Windows, so a reader only ever sees the
    fully-old or fully-new file, never a partial one — which is also why READS need no lock.

    **Application code must not call this directly — use `mutate_orbit`.** It writes the WHOLE
    orbit, so writing an object read any earlier than "just now, under the lock" silently
    destroys whatever else was written in between. `mutate_orbit` is the only caller inside this
    package for exactly that reason; tests building fixtures on disk are the legitimate exception."""
    atomic_write_text(orbit_path(orbit.id, base_dir=base_dir), orbit.model_dump_json(indent=2))


#: Per-lock-path `threading.Lock`s, used ONLY on a platform without `fcntl` (see `orbit_lock`).
#: Never consulted on POSIX, where `flock` already serializes threads as well as processes.
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(key: str) -> threading.Lock:
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.Lock())


@contextmanager
def orbit_lock(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> Iterator[None]:
    """Exclusive advisory lock on one orbit, held across a read-modify-write cycle.

    `fcntl.flock` on a sidecar `<base_dir>/.<slug>.json.lock`. Two properties this design leans on,
    both verified empirically rather than assumed:

    - **One mechanism covers threads AND processes.** `flock` locks attach to the *open file
      description*, so a separate `open()` per acquirer serializes two threads of one process just
      as it does two processes. Do NOT swap this for `fcntl.lockf` (POSIX record locks): those are
      per-PROCESS, so two threads of one `uvicorn` server would pass straight through each other.
    - **It releases the GIL while blocked**, so a waiting thread doesn't stall the interpreter.

    A SIDECAR file rather than the orbit itself: `load_or_create` legitimately runs for a
    orbit that doesn't exist yet, and pre-creating the real path would break `load_orbit`'s
    `path.exists()` contract. The lock file is never unlinked — deleting it would race with an
    acquirer that already opened it — so one zero-byte file per orbit accumulates;
    `list_orbit_summaries` globs `*.json`, so these stay invisible to it.

    **NOT reentrant.** A second acquisition from the same thread blocks forever (a different open
    file description, so `flock` sees a genuine second acquirer). Nothing passed to
    `mutate_orbit` may itself call `mutate_orbit`/`orbit_lock`.

    **POSIX only, stated rather than papered over.** Without `fcntl` (Windows), this degrades to a
    process-local `threading.Lock`: still correct for the single-process `uvicorn` deployment
    invariant 23 already describes as the only supported one, with no cross-process guarantee. A
    portable create-exclusive lockfile protocol would need stale-lock recovery after a crash — more
    failure modes than this buys.

    Raises `ValueError` for an id that slugs to nothing, from `orbit_path` — same as every other
    function here, so an invalid id fails identically whether or not it reaches a lock.
    """
    path = orbit_path(orbit_id, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")

    if fcntl is None:  # pragma: no cover — POSIX-only fallback
        with _thread_lock_for(str(lock_path)):
            yield
        return

    with open(lock_path, "a+") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def delete_orbit(orbit_id: str, *, base_dir: str | Path = DEFAULT_ORBITS_DIR) -> bool:
    """Remove an orbit and everything stored beside it. Returns whether it was there.

    **A product that offers Forget for a node and ✕ for a source could not delete a ORBIT — from
    anywhere.** No endpoint, no CLI verb, no control: once one existed it was permanent, and
    emptying it left "Untitled orbit · 0" in the facet rail forever. `app.js` even ships the
    string "a deleted orbit" for a state nothing could produce. The CHANGELOG already treats one
    stray empty orbit as worth a compensating write; a reader who made one by hand had no
    recourse at all. Curation without deletion is not curation.

    Taken under `orbit_lock`, like every other write, so a `mutate_orbit` in flight finishes
    first rather than re-creating the file behind this. The audio goes with it (`clear_audio`) —
    one file per orbit is what made retention a non-question (invariant 42), and orphaning it
    would make it one.

    Deliberately NOT this function's job: the Horizon's membership rows. They live in another store
    and the caller drops them best-effort AFTER the file is gone, exactly as source removal already
    does — an index write must never undo a completed orbit write.
    """
    path = orbit_path(orbit_id, base_dir=base_dir)
    with orbit_lock(orbit_id, base_dir=base_dir):
        existed = path.exists()
        path.unlink(missing_ok=True)
        clear_audio(orbit_id, base_dir=base_dir)
    #: The picker sorts by this and `last_modified` reads it, so a stale entry for an orbit that
    #: no longer exists would keep sorting a ghost. Cheap to drop, and nothing else reaps it.
    _MTIMES.pop(orbit_id, None)
    return existed


def mutate_orbit(
    orbit_id: str,
    apply: Callable[[Orbit], None],
    *,
    base_dir: str | Path = DEFAULT_ORBITS_DIR,
    create: bool = False,
) -> Orbit:
    """Apply a mutation to an orbit under `orbit_lock`, and return the orbit as saved.

    **`apply` receives an orbit re-loaded from disk INSIDE the lock — never a snapshot the caller
    read earlier.** That is the whole point: it makes it impossible to express "write back the
    object I built minutes ago," which is the defect this exists to close (see the module
    docstring). A caller does its expensive work — ingestion, a model run — unlocked, against a
    snapshot, then passes a closure applying only the resulting DELTA. Critical sections stay
    bounded by a JSON load plus a JSON write.

    `apply` must therefore not assume ids/indices it computed against its own snapshot are still
    right (`append_sources` exists for exactly that re-derivation), and must not call
    `mutate_orbit`/`save_orbit` itself (`orbit_lock` is not reentrant).

    Nothing is written if `apply` raises — the exception propagates with the on-disk file untouched.
    `create=False` raises `FileNotFoundError` for an orbit that doesn't exist; `create=True`
    starts a fresh one, matching `load_or_create`. Raises `ValueError` (invalid id) /
    `pydantic.ValidationError` (corrupted file) exactly where the unlocked readers do.

    The `create=False` miss is checked BEFORE taking the lock as well as inside it. Not an
    optimisation: `orbit_lock` creates its sidecar file just by being entered, so without this
    every 404-ing request (`DELETE /orbits/<anything>/notes/n1`, which any token holder can send
    — invariant 25)
    left a permanent zero-byte file behind, invisible to `list_orbit_summaries`' `*.json` glob.
    Found by an independent security review, which reproduced 503 files from 503 requests against
    orbits that never existed. The check inside the lock is what makes it correct; this one only
    keeps the miss from writing anything.
    """
    if not create and not orbit_path(orbit_id, base_dir=base_dir).exists():
        raise FileNotFoundError(f"no orbit {orbit_id!r}")

    with orbit_lock(orbit_id, base_dir=base_dir):
        orbit = load_orbit(orbit_id, base_dir=base_dir)
        if orbit is None:
            if not create:
                raise FileNotFoundError(f"no orbit {orbit_id!r}")
            orbit = Orbit(id=orbit_id)
        apply(orbit)
        save_orbit(orbit, base_dir=base_dir)
        return orbit


def corpus_of(orbit: Orbit) -> Corpus:
    """A `Corpus` view over an orbit's accumulated sources, for `Corpus.blob()`/citation
    verification — a plain read, no persistence side effect."""
    return Corpus(sources=list(orbit.sources))


def existing_origins(orbit: Orbit) -> set[str]:
    """Origins (file paths/URLs) already ingested into `orbit` — the caller (`cli.py`) skips any
    `--source` value already in this set BEFORE parsing it, so re-passing the same source on a
    later `ask` against the same orbit is a cheap no-op rather than a duplicate re-ingestion."""
    return {s.origin for s in orbit.sources}


def load_or_create(
    orbit_id: str | None, *, base_dir: str | Path = DEFAULT_ORBITS_DIR
) -> Orbit:
    """Load an orbit by id, or return a fresh, unpersisted one if it doesn't exist yet (or no id
    was given at all — an ephemeral orbit). Shared by `cli._prepare` and `api.py`'s endpoints,
    which both need the identical "get me an orbit to work with" step. Raises
    `pydantic.ValidationError` on a corrupted file, same as `load_orbit` — the caller decides
    how to report that (a CLI stderr message vs. an HTTP error response)."""
    orbit = load_orbit(orbit_id, base_dir=base_dir) if orbit_id else None
    if orbit is None:
        orbit = Orbit(id=orbit_id or EPHEMERAL_ID)
    return orbit


def ingest_sources_for(orbit: Orbit, new_values: list[str]) -> list[Source]:
    """Ingest the `new_values` not already present in `orbit` (by origin) and return them —
    WITHOUT touching `orbit`. The expensive half: a network fetch, a PDF parse plus OCR, a
    YouTube caption download. Runs UNLOCKED, against a snapshot; `append_sources` then merges the
    result under `mutate_orbit`'s lock.

    Raises `parsers.web.FetchError`/`ValueError`/`OSError` on an ingestion failure, same as
    `ingest.ingest_new` (which this wraps).

    This and `append_sources` replace the former single `extend_with_sources`, which ingested and
    appended in one breath and so forced its caller to hold a snapshot across ingestion — the exact
    shape of the lost-update defect (module docstring). Deleted rather than kept alongside these
    two, so a later caller can't silently reintroduce it.

    `orbit` is used only to pre-filter already-present origins and to pick starting ids, both of
    which `append_sources` re-derives authoritatively. A stale snapshot therefore costs at worst a
    wasted re-fetch of something a concurrent request added in the meantime, never a wrong result.
    """
    return ingest_new(
        new_values, start_index=len(orbit.sources) + 1, skip_origins=existing_origins(orbit)
    )


#: Every field, anywhere under an `Orbit`, that stores a source id. `_ever_referenced` walks
#: exactly these, and `test_orbit.py`'s tripwire fails if the schema grows another one — the
#: scan is a backstop for orbits written before `source_seq` existed, and a backstop that
#: silently stops covering a new artifact is worse than none.
_SOURCE_ID_FIELDS = (
    ("turns", "answer", "citations", "source_id"),
    ("overview", "citations", "source_id"),
    ("overview", "source_ids"),
    ("podcast", "source_ids"),
    ("podcast", "utterances", "citations", "source_id"),
)


def _ever_referenced(orbit: Orbit) -> set[int]:
    """Source numbers this orbit FILE still points at, including ones whose source is gone.

    Only consulted for an orbit saved before `source_seq` existed, where there is no recorded
    high-water mark to read. It cannot see the Horizon's `NodeMembership` rows — those live in a
    different store — which is exactly why it is the fallback and the counter is the rule.

    Walks `_SOURCE_ID_FIELDS` rather than naming the artifacts inline, so the tripwire that checks
    that list against the schema is checking what this actually reads. Written by hand first, and
    the tripwire immediately found a fifth field missing from it: a podcast utterance carries
    citations of its own.
    """
    numbers: set[int] = set()

    def visit(value: object, path: tuple[str, ...]) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for item in value:
                visit(item, path)
        elif path:
            visit(getattr(value, path[0], None), path[1:])
        elif isinstance(value, str) and value.startswith("s") and value[1:].isdigit():
            numbers.add(int(value[1:]))

    for field_path in _SOURCE_ID_FIELDS:
        visit(orbit, field_path)
    return numbers


def next_source_id(orbit: Orbit) -> str:
    """ALLOCATE the next `s<n>` — never `len(sources) + 1`, and never an id already handed out.

    **This mutates `orbit.source_seq`, and that is the point.** It is the one allocator both
    append sites go through, so making the bump part of the allocation is what stops a third site
    from getting the numbering right and the bookkeeping wrong — the exact split that left
    `promote_note` reproducing this bug after `append_sources` had been fixed.

    Length-based numbering is safe only while sources are append-only, which stopped being true the
    moment a source could be REMOVED. Reproduced before this existed: delete `s2` from `s1,s2,s3`
    and append, and the new source is numbered `s3` — TWO live sources under one id, with `s3`
    resolving to whichever `Corpus.get` reaches first. A stored citation pointing at `s3` then reads
    the wrong text, which is precisely what invariant 12 forbids, and it is the same bug
    `_next_note_id` was written for (invariant 32) one field over.

    **`max(live ids) + 1` fixed only the MIDDLE of that range.** Remove the HIGHEST source and its
    id is free again: `s1,s2,s3` minus `s3` allocates `s3` to the next source added, and a citation
    saved against the old `s3` then verifies TRUE — `citations.py` checks that a coordinate exists,
    never that it still means what it meant (invariant 5) — while opening text that never contained
    the quote. Both tests written for this property removed a middle source, so both stayed green.
    A high-water mark that only ever increases is the property invariant 12 actually asks for, and
    it has to be PERSISTED: `api.py` drops the Horizon membership rows for a removed source on the
    promise that its id "will never come back", and those rows are in a store this file cannot read.

    Ids are therefore allowed to have HOLES. Nothing reads them as a count or an index.
    """
    used = [int(s.id[1:]) for s in orbit.sources if s.id.startswith("s") and s.id[1:].isdigit()]
    if orbit.source_seq is None:
        # No recorded mark: recover one from what the file still references, so an orbit already
        # on disk that lost its highest source is safe on the next append without a migration step.
        orbit.source_seq = max(used + list(_ever_referenced(orbit)), default=0)
    allocated = max([orbit.source_seq, *used]) + 1
    orbit.source_seq = allocated
    return f"s{allocated}"


def remove_source(orbit: Orbit, source_id: str) -> None:
    """Drop one source IN PLACE. RAISES `ValueError` if no such source exists — exactly what
    `delete_note` does, and not merely for symmetry: `mutate_orbit` writes the file unless the
    delta raises, so returning `False` on a miss meant an unauthenticated
    `DELETE .../sources/s99` did a full `save_orbit` and only then 404'd. Harmless in content,
    but it bumps the file's mtime — which invariant 53 made the picker's sort key, so a miss
    reordered the list. Found by an independent audit.

    Removes exactly the FIRST match by index rather than filtering every id-equal entry — defence in
    depth on top of `next_source_id`, the same pairing `delete_note` already has.

    **A citation in a saved turn that pointed at this source becomes UNVERIFIED, not wrong.**
    `citations.py` re-verifies every citation against the current corpus on every read (invariants 5
    and 11), so a removed source's citations lose their ✓ and say why. That is the correct outcome
    and the reason removal is safe to offer at all: nothing silently re-points.
    """
    for index, source in enumerate(orbit.sources):
        if source.id == source_id:
            del orbit.sources[index]
            return
    raise ValueError(f"no source {source_id!r} in this orbit")


def append_sources(orbit: Orbit, sources: list[Source]) -> list[Source]:
    """Append already-ingested, already-injection-scanned `sources` to `orbit.sources` IN PLACE,
    deduped by origin and RENUMBERED against THIS orbit. Returns just what was actually appended
    (so a caller can report which, if any, are flagged).

    The cheap half, meant to run inside `mutate_orbit`'s lock. Both re-derivations matter: a
    source ingested against a snapshot was numbered from *its* `len(sources) + 1` and deduped
    against *its* origins, and a concurrent write may have invalidated both.

    Renumbering an as-yet-unpersisted source does NOT touch invariant 12 (which forbids reassigning
    an id a SAVED orbit already uses): `Source.marker()` derives the citation marker from `.id`
    at `Corpus.blob()` time, so no id is ever baked into stored block text. Callers that hand the
    result to a model must use the RETURNED objects, not the ones they passed in.

    Ids come from `next_source_id` (max in use), NOT from `len(sources) + 1` — see its docstring for
    the collision that made the difference matter.
    """
    seen = existing_origins(orbit)
    appended: list[Source] = []
    for source in sources:
        if source.origin in seen:
            continue
        seen.add(source.origin)
        renumbered = source.model_copy(update={"id": next_source_id(orbit)})
        orbit.sources.append(renumbered)
        appended.append(renumbered)
    return appended


def list_orbit_summaries(
    *, base_dir: str | Path = DEFAULT_ORBITS_DIR
) -> tuple[list[Orbit], list[str]]:
    """Every orbit file under `base_dir`, for the web UI's orbit switcher — there is no other
    way to discover what orbits exist than listing the directory, since an orbit's `id` (what a
    caller would look it up by) is only known once its file has already been parsed. Returns
    `(orbits, unreadable)`: `unreadable` holds the filename STEM of any file that fails to parse
    as an `Orbit`, so one corrupted file is flagged rather than either silently dropped or breaking
    every other orbit's listing (the same "flag, never silently drop" discipline invariants 5/6
    already use elsewhere). Each returned `Orbit.id` is the value stored INSIDE the file, never
    the slugged filename stem — `slug()` is lossy, so the two can read back differently for the same
    file (see `orbit_path`'s docstring)."""
    base = Path(base_dir)
    if not base.exists():
        return [], []
    orbits: list[Orbit] = []
    unreadable: list[str] = []
    stamps: dict[int, float] = {}
    for path in sorted(base.glob("*.json")):
        try:
            orbit = Orbit.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            unreadable.append(path.stem)
            continue
        # The file's mtime, carried out-of-band rather than added to the model: it is a property of
        # the FILE, not of the orbit, and putting it in the schema would mean writing a timestamp
        # nobody reads on every mutation. The picker needs it because model-authored titles are not
        # unique — a user hit three orbits called variations of one topic and asked, reasonably,
        # whether names can collide. They can, so "which did I touch last" has to be answerable.
        stamps[id(orbit)] = path.stat().st_mtime
        orbits.append(orbit)
    orbits.sort(key=lambda orb: stamps.get(id(orb), 0.0), reverse=True)
    for orbit in orbits:
        _MTIMES[orbit.id] = stamps.get(id(orbit), 0.0)
    return orbits, unreadable


#: Last-modified time per orbit id, populated by `list_orbit_summaries`. A module-level cache
#: rather than a schema field for the reason in that function; read only by the listing endpoint,
#: which always repopulates it first.
_MTIMES: dict[str, float] = {}


def last_modified(orbit_id: str) -> float:
    return _MTIMES.get(orbit_id, 0.0)


def history_text(orbit: Orbit) -> str:
    """Every prior turn as plain text, oldest first, for the RLM task's `history` field. Context
    only — the task must still ground every citation in `sources` fresh each turn (`citations.py`
    verifies regardless of what a prior turn cited), never treat a past answer as its own source of
    truth. See AGENTS.md's history invariant."""
    if not orbit.turns:
        return "(no prior turns in this conversation)"
    parts = [
        f"Q{i}: {turn.question}\nA{i}: {turn.answer.text}"
        for i, turn in enumerate(orbit.turns, start=1)
    ]
    return "\n\n".join(parts)


def _next_note_id(orbit: Orbit) -> str:
    """`n{max existing numeric suffix among CURRENTLY LIVE notes + 1}` — NOT `n{len(notes) + 1}`.
    Found by an independent review: `len(notes) + 1` reuses an id that's still held by ANOTHER
    live note the moment a non-last note is deleted (e.g. notes `[n1, n2]`, delete `n1` — the list
    is now length 1, so the next add computes `n2` again, colliding with the surviving note that's
    STILL called `n2`). Two live notes sharing one id is a real, silent-data-loss bug, not a
    cosmetic one: `delete_note`/`promote_note` filter/match BY id, so a collision makes either one
    act on both notes at once — reproduced live, promoting one of a colliding pair silently
    discarded the other with no source ever created for it and no error raised. Deriving the next
    id from the MAX id actually in use (not the count) guarantees no new id can ever collide with
    a note that's still alive, regardless of which note got deleted. An id CAN still be reused
    once NO live note holds it anymore (e.g. every note is deleted, then a new one is added) — that
    case is genuinely safe, unlike the one this function fixes."""
    if not orbit.notes:
        return "n1"
    return f"n{max(int(n.id[1:]) for n in orbit.notes) + 1}"


def add_note(orbit: Orbit, text: str) -> Note:
    """Create and append a new `Note` to `orbit.notes` IN PLACE (see `_next_note_id` for the id
    scheme). Raises `ValueError` on blank text, same discipline `parsers.text.parse_text` already
    applies to a blank text SOURCE. Deliberately does NOT call `save_orbit` itself — same
    convention every other mutator in this module follows (`append_sources` doesn't save either);
    persistence is `mutate_orbit`'s job, and a mutator that saved would deadlock inside it."""
    if not text.strip():
        raise ValueError("note text is empty")
    note = Note(id=_next_note_id(orbit), text=text)
    orbit.notes.append(note)
    return note


def delete_note(orbit: Orbit, note_id: str) -> None:
    """Removes the note with id `note_id` from `orbit.notes` IN PLACE. Raises `ValueError` if no
    such note exists, rather than a silent no-op on a typo'd id — the same "raise on a request that
    named something that doesn't exist" discipline `corpus.Corpus.filtered` already applies to an
    unknown source id. Removes exactly the FIRST matching note by index, not every id-equal match —
    defense in depth alongside `_next_note_id`'s own collision fix, in case a duplicate id is ever
    produced by a future code path this function doesn't control."""
    for index, note in enumerate(orbit.notes):
        if note.id == note_id:
            del orbit.notes[index]
            return
    raise ValueError(f"no note {note_id!r} in this orbit")


def promote_note(orbit: Orbit, note_id: str) -> Source | None:
    """Turns a note into a real, independently-citable `Source`, reusing `ingest_pasted_text`
    UNCHANGED — the exact function pasted-text sources already go through — rather than a parallel
    code path, so a promoted note gets the IDENTICAL content-derived-origin, dedup, and
    injection-scan treatment `add_sources`'s pasted-text branch already gives any other pasted
    text (as far as ingestion is concerned, a note's text IS pasted text).

    Removes the note from `orbit.notes` REGARDLESS of outcome — promotion is a completed user
    action either way — then checks the candidate source's origin against
    `existing_origins(orbit)` (the same dedup-by-content-hash check `add_sources`'s pasted-text
    loop already performs): if identical text is already a source in this orbit, returns `None`
    and appends nothing new; otherwise appends the new (injection-scanned) `Source` and returns it.
    Raises `ValueError` if `note_id` doesn't exist, same as `delete_note`. Pops exactly the FIRST
    matching note by index (same defense-in-depth reasoning as `delete_note`), not every id-equal
    match.

    **Ids come from `next_source_id`, and this is the SECOND append site — missing it left the
    collision invariant 50 claims to have fixed fully alive on the one path invariant 32 says makes
    a note citable at all.** It appends to `orbit.sources` directly rather than through
    `append_sources`, so moving that function onto `next_source_id` did not cover it. Reproduced by
    an independent review over real HTTP: delete `s2` from `s1,s2,s3`, promote a note, and the new
    source is `s3` — a duplicate. `Corpus.blob()` then emits `[[SRC:s3|whole]]` twice, `Corpus.get`
    returns the OLDER source, and a citation naming the promoted note verifies TRUE against a
    different source's text. That is invariant 5's coordinate guarantee broken silently."""
    index = next((i for i, n in enumerate(orbit.notes) if n.id == note_id), None)
    if index is None:
        raise ValueError(f"no note {note_id!r} in this orbit")
    note = orbit.notes.pop(index)
    candidate = ingest_pasted_text(note.text, source_id=next_source_id(orbit))
    if candidate.origin in existing_origins(orbit):
        return None
    source = with_injection_flags(candidate)
    orbit.sources.append(source)
    return source
