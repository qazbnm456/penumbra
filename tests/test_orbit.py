from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from penumbra.orbit import (
    _SLUG_MAX,
    EPHEMERAL_ID,
    add_note,
    append_sources,
    corpus_of,
    delete_note,
    existing_origins,
    history_text,
    ingest_sources_for,
    list_orbit_summaries,
    load_or_create,
    load_orbit,
    mutate_orbit,
    orbit_lock,
    orbit_path,
    promote_note,
    save_orbit,
    slug,
)
from penumbra.schema import Answer, ChatTurn, Note, Orbit, Source, SourceBlock


def _source(id_: str, origin: str = "x") -> Source:
    return Source(id=id_, kind="text", origin=origin, blocks=[SourceBlock(locator="whole", text="hi")])


def test_slug_keeps_safe_characters():
    assert slug("my orbit 1") == "my-orbit-1"


@pytest.mark.parametrize(
    "raw",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "..",
        "....",
        "////",
        "a/../../b",
        "..\\..\\windows",
    ],
)
def test_slug_never_produces_a_path_separator(raw):
    """The whitelist (`[A-Za-z0-9._-]`, everything else folds to `-`) makes a path SEPARATOR
    structurally impossible in the output, regardless of how the input tries to sneak one in — a
    single-example test can't demonstrate that, so this parametrizes over the payloads an
    independent review tried by hand when auditing this function. Note this does NOT assert `".."`
    is absent from the output: a slug like `"a-..-..-b"` is safe precisely because it has no
    separator to make those dots mean anything — `orbit_path()` always treats the whole slug as
    ONE path component (`Path(base_dir) / f"{safe}.json"`), never multiple segments."""
    result = slug(raw)
    assert "/" not in result
    assert "\\" not in result
    # The real safety property: joining `result` onto base_dir can never escape it. An
    # all-separator/all-dot input reduces to an empty slug, which `orbit_path` refuses outright
    # rather than silently writing to `base_dir` itself.
    # Since the non-Latin fix, an all-separator/all-dot input no longer reduces to an empty slug —
    # it falls back to `nb-<hash>`, which is hex and therefore even further from a traversal token
    # than the folded form was. Either way the join stays inside base_dir, which is the property.
    assert orbit_path(raw, base_dir="orbits").parent == Path("orbits")


def test_slug_caps_length():
    assert len(slug("x" * 500)) <= 120


def test_a_punctuation_only_id_is_now_a_hashed_filename_not_an_error(tmp_path):
    """A DELIBERATE change of behavior, not a relaxed test. Invariant 27 made `"!!!"` a clean 400
    instead of a raw 500, and that crash is still gone — but once a non-Latin name had to stop
    being an error (a user hit `400 … reduces to an empty token` naming an orbit in Chinese),
    there was no principled line left between "punctuation only" and "Chinese only": both are just
    strings outside `[A-Za-z0-9._-]` that a user typed on purpose. Both now hash. The traversal
    property is strictly BETTER than before, since `".."` becomes `nb-<hash>` rather than being
    rejected — see `test_slug_never_produces_a_path_separator`."""
    assert slug("...").startswith("nb-")
    assert orbit_path("...", base_dir=tmp_path).parent == Path(tmp_path)


def test_load_orbit_returns_none_when_missing(tmp_path):
    assert load_orbit("nope", base_dir=tmp_path) is None


def test_save_then_load_round_trips(tmp_path):
    orbit = Orbit(
        id="mynb",
        sources=[_source("s1", "a.txt")],
        turns=[ChatTurn(question="what?", answer=Answer(text="this.", citations=[]))],
    )
    save_orbit(orbit, base_dir=tmp_path)
    loaded = load_orbit("mynb", base_dir=tmp_path)

    assert loaded is not None
    assert loaded.id == "mynb"
    assert loaded.sources[0].origin == "a.txt"
    assert loaded.turns[0].question == "what?"


def test_save_orbit_creates_base_dir(tmp_path):
    base = tmp_path / "does" / "not" / "exist"
    orbit = Orbit(id="mynb")
    save_orbit(orbit, base_dir=base)
    assert orbit_path("mynb", base_dir=base).exists()


def test_save_orbit_leaves_no_tmp_file_behind_on_success(tmp_path):
    save_orbit(Orbit(id="mynb"), base_dir=tmp_path)
    assert list(tmp_path.iterdir()) == [orbit_path("mynb", base_dir=tmp_path)]


def test_save_orbit_is_atomic_an_interrupted_write_never_corrupts_the_real_file(tmp_path, monkeypatch):
    """A crash/Ctrl+C during `save_orbit` must never leave a truncated, unparseable file at the
    real path — found by an independent review: the first version wrote directly to the real path
    with no temp file, so an interruption mid-write corrupted it with no recovery. Simulates the
    interruption by making `os.fsync` raise partway through a save that is EXTENDING an existing,
    previously-saved orbit, and confirms the original file is untouched and no `.tmp` litter is
    left in the directory."""
    original = Orbit(id="mynb", sources=[_source("s1", "a.txt")])
    save_orbit(original, base_dir=tmp_path)
    before = orbit_path("mynb", base_dir=tmp_path).read_bytes()

    def _boom(_fd):
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(os, "fsync", _boom)
    updated = original.model_copy(update={"sources": [*original.sources, _source("s2", "b.txt")]})
    with pytest.raises(OSError, match="simulated crash"):
        save_orbit(updated, base_dir=tmp_path)

    assert orbit_path("mynb", base_dir=tmp_path).read_bytes() == before
    assert list(tmp_path.iterdir()) == [orbit_path("mynb", base_dir=tmp_path)]  # no .tmp litter


def test_load_orbit_raises_a_clear_error_on_a_corrupted_file(tmp_path):
    """Not this project's own writer (which is atomic — see the test above), but a hand-edited or
    otherwise externally-corrupted file must still fail with a specific, catchable error rather
    than an assertion or a silent wrong answer. `cli._cmd_ask` catches exactly this (`ValidationError`)
    to print a clear message instead of a raw traceback."""
    path = orbit_path("mynb", base_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id": "mynb", "sources": [}', encoding="utf-8")  # truncated JSON

    with pytest.raises(ValidationError):
        load_orbit("mynb", base_dir=tmp_path)


def test_corpus_of_reflects_orbit_sources():
    orbit = Orbit(id="mynb", sources=[_source("s1", "a.txt"), _source("s2", "b.txt")])
    corpus = corpus_of(orbit)
    assert [s.id for s in corpus.sources] == ["s1", "s2"]


def test_existing_origins():
    orbit = Orbit(id="mynb", sources=[_source("s1", "a.txt"), _source("s2", "b.txt")])
    assert existing_origins(orbit) == {"a.txt", "b.txt"}


def test_history_text_empty_conversation():
    orbit = Orbit(id="mynb")
    assert "no prior turns" in history_text(orbit)


def test_history_text_includes_prior_turns_in_order():
    orbit = Orbit(
        id="mynb",
        turns=[
            ChatTurn(question="first?", answer=Answer(text="first answer.")),
            ChatTurn(question="second?", answer=Answer(text="second answer.")),
        ],
    )
    text = history_text(orbit)
    assert text.index("first?") < text.index("second?")
    assert "first answer." in text
    assert "second answer." in text


def test_load_or_create_loads_an_existing_orbit(tmp_path):
    save_orbit(Orbit(id="mynb", sources=[_source("s1", "a.txt")]), base_dir=tmp_path)
    orbit = load_or_create("mynb", base_dir=tmp_path)
    assert orbit.id == "mynb"
    assert orbit.sources[0].origin == "a.txt"


def test_load_or_create_returns_a_fresh_orbit_when_id_is_missing(tmp_path):
    orbit = load_or_create("does-not-exist-yet", base_dir=tmp_path)
    assert orbit.id == "does-not-exist-yet"
    assert orbit.sources == []
    assert not orbit_path("does-not-exist-yet", base_dir=tmp_path).exists()  # not persisted


def test_load_or_create_returns_an_ephemeral_orbit_when_no_id_given(tmp_path):
    orbit = load_or_create(None, base_dir=tmp_path)
    assert orbit.id == EPHEMERAL_ID


def test_load_or_create_raises_on_a_corrupted_file(tmp_path):
    path = orbit_path("mynb", base_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id": "mynb", "sources": [}', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_or_create("mynb", base_dir=tmp_path)


def test_ingest_then_append_adds_the_source(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("hello a", encoding="utf-8")
    orbit = Orbit(id="mynb")

    new_sources = append_sources(orbit, ingest_sources_for(orbit, [str(a)]))

    assert orbit.sources == new_sources
    assert orbit.sources[0].origin == str(a)
    assert orbit.sources[0].id == "s1"


def test_ingest_sources_for_does_not_touch_the_orbit(tmp_path):
    """The split's whole point: ingestion (slow — network/OCR) must be runnable OUTSIDE the lock,
    which means it cannot be the thing that mutates the orbit."""
    a = tmp_path / "a.txt"
    a.write_text("hello a", encoding="utf-8")
    orbit = Orbit(id="mynb")

    ingested = ingest_sources_for(orbit, [str(a)])

    assert len(ingested) == 1
    assert orbit.sources == []


def test_append_sources_skips_already_present_origins(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("hello a", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("hello b", encoding="utf-8")
    orbit = Orbit(id="mynb", sources=[_source("s1", str(a))])

    new_sources = append_sources(orbit, ingest_sources_for(orbit, [str(a), str(b)]))

    assert [s.origin for s in new_sources] == [str(b)]
    assert [s.origin for s in orbit.sources] == [str(a), str(b)]
    assert orbit.sources[1].id == "s2"  # continues numbering from the existing source, not s1


def test_ingest_sources_for_appends_nothing_when_ingestion_fails(tmp_path):
    orbit = Orbit(id="mynb", sources=[_source("s1", "a.txt")])
    with pytest.raises(OSError):
        ingest_sources_for(orbit, [str(tmp_path / "does-not-exist.txt")])
    assert len(orbit.sources) == 1  # unchanged


def test_append_sources_renumbers_against_the_orbit_it_is_given(tmp_path):
    """A source ingested against a snapshot carries an id derived from THAT snapshot's length. If a
    concurrent write landed in between, reusing it would duplicate an id already in use — so
    `append_sources` renumbers against the orbit it's actually appending to."""
    a = tmp_path / "a.txt"
    a.write_text("hello a", encoding="utf-8")
    snapshot = Orbit(id="mynb")
    ingested = ingest_sources_for(snapshot, [str(a)])
    assert ingested[0].id == "s1"  # numbered against the (empty) snapshot

    fresh = Orbit(id="mynb", sources=[_source("s1", "added-by-someone-else")])
    appended = append_sources(fresh, ingested)

    assert appended[0].id == "s2"
    assert [s.id for s in fresh.sources] == ["s1", "s2"]


# --- mutate_orbit / orbit_lock ------------------------------------------------------------


def _turn(question: str = "q?") -> ChatTurn:
    return ChatTurn(question=question, answer=Answer(text="an answer"))


def test_mutate_orbit_applies_to_a_freshly_loaded_orbit_not_the_callers_snapshot(tmp_path):
    """THE regression test for this slice. A handler holds a snapshot across slow work (an RLM run,
    an OCR pass); something else writes in the meantime; the handler then persists its own delta.
    Before `mutate_orbit`, saving the snapshot destroyed the concurrent write outright —
    reproduced live over HTTP against a real server, not hypothesised."""
    save_orbit(Orbit(id="mynb", sources=[_source("s1")]), base_dir=tmp_path)
    stale = load_orbit("mynb", base_dir=tmp_path)  # what a slow handler is holding

    concurrent = load_orbit("mynb", base_dir=tmp_path)
    concurrent.notes.append(Note(id="n1", text="written while the handler was busy"))
    save_orbit(concurrent, base_dir=tmp_path)

    result = mutate_orbit("mynb", lambda nb: nb.turns.append(_turn()), base_dir=tmp_path)

    assert [n.id for n in result.notes] == ["n1"]  # the concurrent write survived
    assert len(result.turns) == 1  # and so did this one's own delta
    assert load_orbit("mynb", base_dir=tmp_path).notes[0].text.startswith("written while")
    assert stale.turns == []  # the snapshot was never written back


def test_mutate_orbit_writes_nothing_when_the_closure_raises(tmp_path):
    save_orbit(Orbit(id="mynb", sources=[_source("s1")]), base_dir=tmp_path)

    def _explode(nb):
        nb.turns.append(_turn())  # a mutation that must NOT reach disk
        raise ValueError("no such note")

    with pytest.raises(ValueError, match="no such note"):
        mutate_orbit("mynb", _explode, base_dir=tmp_path)

    assert load_orbit("mynb", base_dir=tmp_path).turns == []


def test_mutate_orbit_raises_file_not_found_without_create(tmp_path):
    with pytest.raises(FileNotFoundError):
        mutate_orbit("nope", lambda nb: None, base_dir=tmp_path)


def test_mutate_orbit_creates_when_asked(tmp_path):
    result = mutate_orbit(
        "fresh", lambda nb: nb.notes.append(Note(id="n1", text="hi")), base_dir=tmp_path, create=True
    )

    assert result.id == "fresh"
    assert load_orbit("fresh", base_dir=tmp_path).notes[0].id == "n1"


def test_mutate_orbit_still_rejects_an_id_that_slugs_to_nothing(tmp_path):
    """Invariant 27's 400s must survive the rewrite: an id that reduces to nothing has to fail the
    same way through the locked write path as it does through every unlocked reader. Since the
    non-Latin fix, only a genuinely EMPTY id reduces to nothing — `"!!!"` now hashes."""
    with pytest.raises(ValueError):
        mutate_orbit("   ", lambda nb: None, base_dir=tmp_path, create=True)


def test_the_orbit_lock_does_not_leave_a_json_file_the_listing_would_pick_up(tmp_path):
    with orbit_lock("mynb", base_dir=tmp_path):
        pass
    assert list_orbit_summaries(base_dir=tmp_path) == ([], [])
    assert (tmp_path / ".mynb.json.lock").exists()


_HOLDS_THE_LOCK = """
import sys, time
from penumbra.orbit import orbit_lock
with orbit_lock("mynb", base_dir=sys.argv[1]):
    open(sys.argv[2], "w").write("held")
    time.sleep(1.0)
"""


def test_the_orbit_lock_serializes_two_real_processes(tmp_path):
    """Spawns a REAL second process holding the lock, rather than asserting on two threads — the
    cross-process guarantee is the whole reason `cli.py` and a running `api.py` can write the same
    orbit file safely, and only `flock` (not `fcntl.lockf`, which is per-process) provides it.
    Same "verify it against a real process" discipline `test_runner.py`'s grandchild-cancellation
    test already applies."""
    pytest.importorskip("fcntl")
    signal_path = tmp_path / "held.txt"
    child = subprocess.Popen(
        [sys.executable, "-c", _HOLDS_THE_LOCK, str(tmp_path), str(signal_path)]
    )
    try:
        deadline = time.monotonic() + 10
        while not signal_path.exists():
            assert time.monotonic() < deadline, "child never acquired the lock"
            assert child.poll() is None, "child exited before acquiring the lock"
            time.sleep(0.02)

        started = time.monotonic()
        with orbit_lock("mynb", base_dir=tmp_path):
            waited = time.monotonic() - started
    finally:
        child.wait(timeout=10)

    assert waited > 0.3, f"acquired the lock in {waited:.3f}s — it was not actually held"


def test_list_orbit_summaries_empty_dir_that_does_not_exist_yet(tmp_path):
    assert list_orbit_summaries(base_dir=tmp_path / "does-not-exist") == ([], [])


def test_list_orbit_summaries_reports_the_stored_id_not_the_slugged_filename(tmp_path):
    """An orbit id with characters outside the slug whitelist is folded before becoming a
    filename — the listing must report the `id` stored INSIDE the file, not derive one from the
    filename stem, or the two could read back differently for the same file."""
    save_orbit(Orbit(id="My Orbit!", sources=[_source("s1", "a.txt")]), base_dir=tmp_path)

    orbits, unreadable = list_orbit_summaries(base_dir=tmp_path)

    assert unreadable == []
    assert [nb.id for nb in orbits] == ["My Orbit!"]


def test_list_orbit_summaries_flags_a_corrupted_file_without_breaking_the_rest(tmp_path):
    save_orbit(Orbit(id="good"), base_dir=tmp_path)
    (tmp_path / "broken.json").write_text('{"id": "broken", "sources": [}', encoding="utf-8")

    orbits, unreadable = list_orbit_summaries(base_dir=tmp_path)

    assert [nb.id for nb in orbits] == ["good"]
    assert unreadable == ["broken"]


# --- Notes ----------------------------------------------------------------------------------------


def test_add_note_appends_and_numbers_sequentially():
    orbit = Orbit(id="mynb")
    n1 = add_note(orbit, "first note")
    n2 = add_note(orbit, "second note")
    assert (n1.id, n1.text) == ("n1", "first note")
    assert (n2.id, n2.text) == ("n2", "second note")
    assert [n.id for n in orbit.notes] == ["n1", "n2"]


def test_add_note_rejects_blank_text():
    orbit = Orbit(id="mynb")
    with pytest.raises(ValueError, match="empty"):
        add_note(orbit, "   ")
    assert orbit.notes == []


def test_delete_note_removes_by_id():
    orbit = Orbit(id="mynb")
    add_note(orbit, "keep me")
    add_note(orbit, "delete me")
    delete_note(orbit, "n2")
    assert [n.id for n in orbit.notes] == ["n1"]


def test_delete_note_raises_on_unknown_id():
    orbit = Orbit(id="mynb")
    add_note(orbit, "a note")
    with pytest.raises(ValueError, match="no note 'does-not-exist'"):
        delete_note(orbit, "does-not-exist")
    assert len(orbit.notes) == 1  # unchanged


def test_promote_note_turns_it_into_a_source_and_removes_it_from_notes():
    orbit = Orbit(id="mynb")
    add_note(orbit, "promote this text")

    source = promote_note(orbit, "n1")

    assert orbit.notes == []
    assert source is not None
    assert source.id == "s1"
    assert source.blocks[0].text == "promote this text"
    assert orbit.sources == [source]


def test_promote_note_numbers_the_new_source_after_existing_sources():
    orbit = Orbit(id="mynb", sources=[_source("s1", "a.txt")])
    add_note(orbit, "promote this text")

    source = promote_note(orbit, "n1")

    assert source.id == "s2"
    assert [s.id for s in orbit.sources] == ["s1", "s2"]


def test_promote_note_dedupes_against_an_identical_existing_source_and_returns_none():
    """Same content-hash-based dedup `add_sources`'s pasted-text loop already applies — promoting a
    note whose text is byte-identical to text already pasted as a source appends nothing new, but
    the note is still removed from `notes` either way (promotion is a completed action). Adds a
    SECOND, pre-existing source first so the reused note id (see `add_note`'s own docstring: an id
    can be reused after a delete/promote shrinks `notes`) isn't what this test is actually about."""
    orbit = Orbit(id="mynb", sources=[_source("s1", "a.txt")])
    add_note(orbit, "duplicate text")
    promote_note(orbit, "n1")  # creates s2
    add_note(orbit, "duplicate text")  # same text again, a new note (id reused: also "n1")

    result = promote_note(orbit, "n1")

    assert result is None
    assert orbit.notes == []
    assert len(orbit.sources) == 2  # no third source appended


def test_promote_note_raises_on_unknown_id():
    orbit = Orbit(id="mynb")
    with pytest.raises(ValueError, match="no note 'does-not-exist'"):
        promote_note(orbit, "does-not-exist")


def test_add_note_can_reuse_an_id_once_no_live_note_holds_it():
    """Safe id reuse: deleting the note that WAS `"n2"` frees that id for reuse, since no other
    live note holds it afterward."""
    orbit = Orbit(id="mynb")
    add_note(orbit, "first")
    add_note(orbit, "second")  # id "n2"
    delete_note(orbit, "n2")
    reused = add_note(orbit, "third")
    assert reused.id == "n2"


def test_add_note_never_collides_with_a_still_live_note_after_deleting_an_earlier_one():
    """The real bug an independent review found in the original `len(notes) + 1` id scheme: adding
    notes n1/n2, deleting the EARLIER one (n1, not the most recent), then adding a third used to
    reuse "n2" — colliding with the note that was still alive under that exact id. Confirms the fix
    (`_next_note_id` deriving from the max id actually in use, not the count) never lets that
    happen, regardless of which note gets deleted."""
    orbit = Orbit(id="mynb")
    add_note(orbit, "first")  # n1
    add_note(orbit, "second")  # n2
    delete_note(orbit, "n1")  # n2 is still alive
    third = add_note(orbit, "third")
    assert third.id != "n2"  # must not collide with the still-live note
    assert [n.id for n in orbit.notes] == ["n2", third.id]
    assert len({n.id for n in orbit.notes}) == 2  # no duplicate ids


def test_delete_note_removes_only_the_first_matching_note_by_index():
    """Defense in depth, verified directly: even if two notes somehow shared an id (bypassing
    `add_note`'s own now-collision-free scheme), `delete_note` removes exactly one, not both."""
    orbit = Orbit(id="mynb")
    orbit.notes = [Note(id="n2", text="first"), Note(id="n2", text="second")]
    delete_note(orbit, "n2")
    assert [n.text for n in orbit.notes] == ["second"]


def test_promote_note_promotes_only_the_first_matching_note_by_index():
    """Same defense-in-depth guarantee as `delete_note`, for `promote_note`."""
    orbit = Orbit(id="mynb")
    orbit.notes = [Note(id="n2", text="first"), Note(id="n2", text="second")]
    source = promote_note(orbit, "n2")
    assert source.blocks[0].text == "first"
    assert [n.text for n in orbit.notes] == ["second"]


def test_a_non_latin_id_gets_a_stable_hashed_filename_instead_of_failing(tmp_path):
    """Reported by a user: naming an orbit in Chinese returned `400 invalid orbit id
    '模型要睡覺': … reduces to an empty token`. The whitelist strips every non-Latin character, so
    ANY Chinese/Japanese/Korean/Arabic/emoji-only name reduced to nothing and was rejected as
    malformed — with nothing to suggest the NAME was the problem rather than the request."""
    assert slug("模型要睡覺").startswith("nb-")
    assert slug("模型要睡覺") == slug("模型要睡覺")  # deterministic: same name, same file
    assert slug("模型要睡覺") != slug("模型要吃飯")  # and distinct names don't collide
    assert orbit_path("模型要睡覺", base_dir=tmp_path).parent == Path(tmp_path)


def test_a_non_latin_id_round_trips_through_save_and_load(tmp_path):
    """The hash is only ever the FILENAME. `Orbit.id` keeps what the user typed, and
    `list_orbit_summaries` reports that stored value rather than the filename stem — the
    property that makes non-Latin names display correctly with no further change."""
    save_orbit(Orbit(id="模型要睡覺", sources=[_source("s1")]), base_dir=tmp_path)

    loaded = load_orbit("模型要睡覺", base_dir=tmp_path)
    assert loaded is not None
    assert loaded.id == "模型要睡覺"

    orbits, unreadable = list_orbit_summaries(base_dir=tmp_path)
    assert unreadable == []
    assert [nb.id for nb in orbits] == ["模型要睡覺"]


def test_a_hashed_id_is_still_filesystem_safe(tmp_path):
    """The fallback must not reopen what the whitelist closed: no traversal, no separators, and a
    bounded length (AGENTS.md's orbit-id invariant)."""
    for raw in ["../../etc/passwd", "。。/。。", "🐝" * 500, "\n\t"]:
        token = slug(raw)
        if not token:
            continue
        assert re.fullmatch(r"[A-Za-z0-9._-]+", token), token
        assert "/" not in token and not token.startswith((".", "-"))
        assert len(token) <= _SLUG_MAX


def test_a_genuinely_empty_id_still_fails_loudly(tmp_path):
    """"You gave me nothing" stays a real error — only "you gave me a name in your own language"
    stopped being one."""
    for raw in ["", "   ", "\n"]:
        assert slug(raw) == ""
        with pytest.raises(ValueError):
            orbit_path(raw, base_dir=tmp_path)


def test_slug_never_raises_for_any_string():
    """Totality is a REQUIREMENT, not an accident: `api._derive_run_id` calls `slug()` directly,
    outside every error wrapper that turns a bad id into a 4xx, so anything `slug` raises becomes
    an unauthenticated 500. It was total until the hash fallback introduced `raw.encode("utf-8")`,
    which an independent review showed raises `UnicodeEncodeError` on a lone surrogate — reachable
    from a JSON body field and from argv's `surrogateescape` decoding."""
    for raw in ["\ud800", "\udfff", "a\ud800b", "\x00", "\U0010ffff", "\u202e", "\u200b" * 50]:
        assert isinstance(slug(raw), str)


def test_the_same_visible_name_in_nfc_and_nfd_is_one_orbit():
    """A browser submits NFC; text pasted from a macOS filename is NFD. Without normalization the
    two byte strings hash differently, so one user gets two orbits with identical-looking names
    and no way to tell them apart — found by an independent review of the hash fallback."""
    import unicodedata

    for name in ["한글", "café", "Việt"]:
        nfc, nfd = unicodedata.normalize("NFC", name), unicodedata.normalize("NFD", name)
        if slug(nfc).startswith("nb-") or slug(nfd).startswith("nb-"):
            assert slug(nfc) == slug(nfd), name


def test_a_new_source_never_reuses_a_removed_sources_id():
    """Reproduced before `next_source_id` existed, and it is invariant 12's exact failure: source
    ids were `s{len(sources) + 1}`, which is safe only while sources are append-only. Delete `s2`
    from `s1,s2,s3` and append, and the new source is numbered `s3` — TWO live sources under one
    id, with a stored citation for `s3` resolving to whichever one `Corpus.get` reaches first.

    Same shape as the note-id collision invariant 32 documents, one field over.
    """
    from penumbra.orbit import append_sources, remove_source
    from penumbra.schema import Orbit, Source, SourceBlock

    def src(index: int, text: str) -> Source:
        return Source(
            id=f"s{index}",
            kind="text",
            origin=f"origin-{index}",
            blocks=[SourceBlock(locator="whole", text=text)],
        )

    orbit = Orbit(id="x")
    append_sources(orbit, [src(1, "one"), src(2, "two"), src(3, "three")])
    assert [s.id for s in orbit.sources] == ["s1", "s2", "s3"]
    remove_source(orbit, "s2")
    assert [s.id for s in orbit.sources] == ["s1", "s3"]

    append_sources(orbit, [src(99, "brand new")])
    ids = [s.id for s in orbit.sources]
    assert len(ids) == len(set(ids)), ids
    assert ids == ["s1", "s3", "s4"]
    # ...and the surviving source still resolves to its OWN text.
    assert next(s for s in orbit.sources if s.id == "s3").blocks[0].text == "three"

    # Removing something that is not there RAISES, exactly like `delete_note`. Not symmetry:
    # `mutate_orbit` writes the file unless the delta raises, so a returned `False` meant a
    # 404-ing DELETE still did a full save and bumped the mtime the picker now sorts by.
    with pytest.raises(ValueError, match="no source 's99'"):
        remove_source(orbit, "s99")
    # Remaining ids are never renumbered by a removal (invariant 12).
    assert [s.id for s in orbit.sources] == ["s1", "s3", "s4"]


def test_removing_the_HIGHEST_source_does_not_free_its_id():
    """The half `max(live ids) + 1` never covered, and the reason `source_seq` is persisted.

    Both tests written for invariant 12 removed a MIDDLE source, where the max is unchanged and the
    old rule happens to be right. Remove the TOP one and its id is free again — the next source
    takes it, and a citation saved against the old `s3` verifies TRUE (invariant 5 checks that a
    coordinate exists, never that it still means the same thing) while opening text that never
    contained the quote. `api.py` also drops the Horizon membership rows for a removed source on the
    stated promise that its id "will never come back".
    """
    from penumbra.orbit import append_sources, next_source_id, remove_source
    from penumbra.schema import Orbit, Source, SourceBlock

    def src(origin: str, text: str) -> Source:
        return Source(
            id="s0", kind="text", origin=origin, blocks=[SourceBlock(locator="whole", text=text)]
        )

    orbit = Orbit(id="x")
    append_sources(orbit, [src("a", "one"), src("b", "two"), src("c", "three")])
    remove_source(orbit, "s3")
    appended = append_sources(orbit, [src("d", "brand new")])
    assert appended[0].id == "s4", "s3 was allocated once and must never be allocated again"
    assert [s.id for s in orbit.sources] == ["s1", "s2", "s4"]

    # The mark only ever RISES, so it survives emptying the orbit completely.
    for source_id in ["s1", "s2", "s4"]:
        remove_source(orbit, source_id)
    assert next_source_id(orbit) == "s5"


def test_a_orbit_saved_before_source_seq_recovers_its_mark_from_what_it_cites():
    """No migration step: `source_seq` defaults to None on every orbit already on disk, and the
    first allocation recovers a mark from the ids the FILE still references — which is where the
    damage would land, since an id nothing points at is harmless to reuse.

    Deliberately weaker than the counter (it cannot see the Horizon's membership rows, which live in
    another store), which is why it is only the fallback for a file written before the field.
    """
    from penumbra.orbit import append_sources, next_source_id
    from penumbra.schema import (
        Answer,
        ChatTurn,
        Citation,
        Orbit,
        Overview,
        Podcast,
        Source,
        SourceBlock,
    )

    def src(source_id: str) -> Source:
        return Source(
            id=source_id, kind="text", origin=source_id, blocks=[SourceBlock(locator="w", text="t")]
        )

    def loaded(**kwargs) -> Orbit:
        orbit = Orbit(id="x", sources=[src("s1")], **kwargs)
        assert orbit.source_seq is None, "the point of the fallback"
        return orbit

    cited = loaded(
        turns=[
            ChatTurn(
                question="q",
                answer=Answer(
                    text="t", citations=[Citation(source_id="s7", locator="w", quote="gone")]
                ),
            )
        ]
    )
    assert next_source_id(cited) == "s8"

    assert next_source_id(loaded(overview=Overview(text="o", source_ids=["s4"]))) == "s5"
    assert (
        next_source_id(
            loaded(overview=Overview(text="o", citations=[Citation(source_id="s6", locator="w", quote="q")]))
        )
        == "s7"
    )
    assert next_source_id(loaded(podcast=Podcast(source_ids=["s9"]))) == "s10"

    # Nothing referenced: the old behaviour, and correct — an id no saved artifact points at cannot
    # be silently repointed by being reused.
    plain = loaded()
    assert next_source_id(plain) == "s2"
    # And once recovered, the mark is authoritative: a second allocation never repeats the first.
    assert next_source_id(plain) == "s3"
    append_sources(plain, [src("new")])
    assert [s.id for s in plain.sources] == ["s1", "s4"]


def test_every_persisted_source_id_field_is_covered_by_the_recovery_scan():
    """A tripwire, for the one way the fallback above rots: a new artifact that stores a source id.

    `_ever_referenced` walks a hand-written list of paths. Add `Orbit.digest.source_ids` and the
    scan keeps passing while quietly covering less, which is worse than not having it — so this
    walks the schema instead and fails if it finds a source-id field the list does not name.
    """
    from pydantic import BaseModel

    from penumbra.orbit import _SOURCE_ID_FIELDS
    from penumbra.schema import Orbit

    found: set[tuple[str, ...]] = set()

    def walk(model: type[BaseModel], path: tuple[str, ...], seen: frozenset) -> None:
        if model in seen:
            return
        seen = seen | {model}
        for name, field in model.model_fields.items():
            here = (*path, name)
            if name in ("source_id", "source_ids"):
                found.add(here)
            for candidate in _models_in(field.annotation):
                walk(candidate, here, seen)

    def _models_in(annotation) -> list[type[BaseModel]]:
        import typing

        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return [annotation]
        return [
            inner
            for arg in typing.get_args(annotation) or ()
            for inner in _models_in(arg)
        ]

    walk(Orbit, (), frozenset())
    assert found, "the walk found nothing — it has stopped testing anything"
    assert found == set(_SOURCE_ID_FIELDS), (
        "a source-id field the recovery scan does not read:\n"
        f"  schema has:  {sorted(found)}\n"
        f"  scan covers: {sorted(_SOURCE_ID_FIELDS)}"
    )



def test_promoting_a_note_never_reuses_a_removed_sources_id():
    """The SECOND append site, and the one an independent review found still numbering by length
    after `append_sources` had been fixed. It matters more than the first: promotion is the ONLY
    path that makes a note citable (invariant 32), and the duplicate id made a citation naming the
    promoted note verify TRUE against a DIFFERENT source's text — invariant 5's coordinate
    guarantee broken silently.

    NOTE on what is asserted: the review's phrasing was that the citation "verifies TRUE against a
    different source's text". It does — but so would ANY quote, because `verify_citations` checks
    coordinate existence and never the quote (invariant 5). The harm the collision actually does is
    that the promoted note becomes UNADDRESSABLE: two blocks answer to `s3`, `Corpus.get` returns
    the older one, and no citation can ever reach the note that promotion existed to make citable.
    """
    from penumbra.corpus import Corpus
    from penumbra.orbit import add_note, promote_note, remove_source
    from penumbra.schema import Orbit, Source, SourceBlock

    orbit = Orbit(
        id="x",
        sources=[
            Source(id=f"s{i}", kind="text", origin=f"o{i}",
                   blocks=[SourceBlock(locator="whole", text=text)])
            for i, text in ((1, "ONE"), (2, "TWO"), (3, "THREE"))
        ],
    )
    remove_source(orbit, "s2")
    add_note(orbit, "promoted note text")
    promoted = promote_note(orbit, "n1")

    ids = [s.id for s in orbit.sources]
    assert ids == ["s1", "s3", "s4"], ids
    assert promoted is not None and promoted.id == "s4"

    corpus = Corpus(orbit.sources)
    blob = corpus.blob()
    assert blob.count("[[SRC:s3|") == 1  # not twice
    # The decisive pair: the survivor still means itself, and the promoted note is reachable at all.
    assert corpus.get("s3").blocks[0].text == "THREE"
    assert "promoted note text" in corpus.get("s4").blocks[0].text
