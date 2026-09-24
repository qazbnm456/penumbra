"""Tripwires under `AGENTS.md`'s Scope note.

Every other claim in the rulebook has something under it: an invariant's rule is pinned by a test
of the code it governs, and `docs/invariants/` argues for a behaviour the suite already exercises.
The **Scope note** is the exception. It is prose about what exists and what does not, and prose
about existence is exactly the thing a test suite never notices going stale.

It did go stale. The note was written while the Inbox was library-plus-HTTP, and said in two
places - once in the paragraph, once in the "Still unbuilt" list - that there is no UI for any of
it. That survived the entire stage that BUILT the UI, with 869 green tests the whole way, because
nothing in the suite reads a sentence.

So the mechanically checkable halves get checked here. Not the prose: the SHAPE of the claim,
BOTH WAYS. A test that only fires when a claim becomes too modest would have caught this one and
nothing else; the same drift runs the other way the moment someone writes a `rlm-notebook inbox`
subcommand and leaves the note saying the command line cannot reach it.

These are deliberately narrow. The Scope note will always carry claims no assertion can reach
("Word/Slides/Docs native-format parsing ... undone" is a claim about the absence of code, which
has no symbol to look for). The rule this file follows: assert a claim only where a concrete
symbol, route or filename decides it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def scope_note() -> str:
    """The Scope note alone. The invariant index below it narrates history, so a phrase like "no
    UI" can legitimately appear there describing how something USED to be; this test must only read
    the section that speaks in the present tense about what exists today."""
    start = AGENTS.index("## Scope note")
    return AGENTS[start : AGENTS.index("## Invariants", start)]


def test_the_scope_note_agrees_with_the_web_ui_about_the_inbox():
    """The claim that went stale, pinned in both directions."""
    note = scope_note()
    app = (ROOT / "rlm_notebook" / "web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "rlm_notebook" / "web" / "index.html").read_text(encoding="utf-8")

    # A UI for the Inbox means two things, and either alone would be a half-built claim: the markup
    # declares the surface, and the script talks to the `/inbox` routes.
    ui_exists = 'id="view-inbox"' in html and "/inbox" in app

    denials = [
        phrase
        for phrase in ("there is no UI", "has NO UI", "has no UI", "no UI for any of it")
        if phrase.lower() in note.lower()
    ]
    if ui_exists:
        assert not denials, (
            "the web UI renders the Inbox, but the Scope note still denies it: "
            f"{denials}. Fix the note, not this test."
        )
        # And it must positively say so - deleting the false sentence without replacing it leaves a
        # reader of the rulebook with no idea the default screen changed.
        assert "web UI" in note and "Inbox" in note, (
            "the Scope note has to SAY the Inbox has a UI, not merely stop denying it"
        )
    else:
        assert denials, (
            "nothing renders the Inbox, so the Scope note must say so - a reader who assumes a UI "
            "exists because a design discussion mentioned it is exactly what that list is for"
        )


def test_the_scope_note_agrees_with_cli_py_about_the_inbox():
    """The half that is still TRUE, pinned so it stays honest when someone builds the other half.

    This is the direction the first test could not cover: a claim of absence that becomes false
    when code is ADDED. `cli.py` gaining an inbox subcommand is a perfectly good change; shipping it
    while the rulebook still tells the next reader the command line cannot reach the Inbox is not.
    """
    note = scope_note()
    cli = (ROOT / "rlm_notebook" / "cli.py").read_text(encoding="utf-8")

    # A SURFACE, not a mention: an `add_parser("inbox")` or an import of the module. A stray word
    # "inbox" inside a docstring is not a command, and matching on it would make this test fire on
    # a comment.
    surface = bool(
        re.search(r"add_parser\(\s*[\"']inbox", cli)
        or re.search(r"^from rlm_notebook import .*\binbox\b", cli, re.MULTILINE)
        or re.search(r"^from \.? ?inbox import|^from rlm_notebook\.inbox import", cli, re.MULTILINE)
    )
    phrases = ("no `cli.py` surface", "command line cannot reach it", "`cli.py` cannot reach the Inbox")
    denies = any(phrase in note for phrase in phrases)

    if surface:
        assert not denies, (
            "cli.py has an inbox surface now; the Scope note still says it cannot reach the Inbox"
        )
    else:
        assert denies, (
            "cli.py cannot reach the Inbox, and the Scope note has to keep saying so - it is the "
            "asymmetry between the two entry points that invariant 20 is about"
        )


def test_every_indexed_invariant_has_the_file_it_points_at():
    """A cheaper drift than the Scope note's, and one that has a symbol to check: the index links
    each rule to `docs/invariants/<n>-<slug>.md`, and a renamed file leaves a dead link behind. The
    rename of 25 in this very changeset is the case - `25-the-api-has-no-authentication.md` became
    `25-the-api-has-no-authorization.md`, and the index entry had to move with it."""
    links = re.findall(r"\]\(docs/invariants/([^)]+)\)", AGENTS)
    # 1 through 80, plus the half-numbered 48.5.
    assert len(links) >= 81, f"only {len(links)} invariant links found; the index cannot have shrunk"
    missing = [name for name in links if not (ROOT / "docs" / "invariants" / name).exists()]
    assert not missing, f"the index links to files that do not exist: {missing}"

    # And the other way: a file nobody links to is an argument the index forgot to carry.
    linked = set(links)
    on_disk = {p.name for p in (ROOT / "docs" / "invariants").glob("*.md")} - {"README.md"}
    orphans = sorted(on_disk - linked)
    assert not orphans, f"docs/invariants files no entry in the index points at: {orphans}"
