"""`AlignConcepts`: which newly written entity names are the same thing as one already known.

The known names are a REPL variable, because a Horizon's entity list can run to thousands and the
model needs to search it rather than read it; the few new names are in the prompt. The answer is a
list of `alias -> canonical` pairs that `concepts.apply_merges` checks and records. Nothing a
summary wrote is changed.

An `RLMTask`, so it runs in `worker.py` (invariant 21), carries the skills (65) and validates
before SUBMIT (66). It cites nothing, so its validator checks shape and markers only.
"""

from __future__ import annotations

from typing import Any

from rlm_harness import RLMTask

from .instructions import SKILLS_DIR, apply_skills, make_grounded_validator, validate_before_submit_rule
from .schema import ConceptMerges

__all__ = ["AlignConcepts"]

_INSTRUCTIONS = f"""\
Decide which of the NEW entity names are the same entity as one already KNOWN, or as another new
name.

`known` is a REPL variable: every entity name already in use, one per line, with how many captures
name it. Search it with Python (`.find()`, splitting lines); do not print all of it. `new_names` is
a JSON list of names written by recent summaries.

Merge two names ONLY when they name the same thing: a spelling or capitalisation variant, a
translation or transliteration (Matthew Walker and 馬修·沃克), an abbreviation and its expansion
(REM and REM sleep only if both clearly mean the same stage), or a name with and without a title.
Never merge things that are merely related (sleep and REM sleep, coffee and caffeine), a part and
its whole, or a person and their work. When unsure, do not merge; an unmerged pair costs nothing,
a wrong merge hides a real distinction.

For each merge give `alias` (the new name) and `canonical` (the name to keep, usually the known one,
or the more common spelling), each copied EXACTLY as written in `known` or `new_names`. Return an
empty list when nothing should be merged.

{validate_before_submit_rule("validate_conceptmerges")}
"""


class AlignConcepts(RLMTask):
    """Merge newly written entity names into the ones already known."""

    signature = "known: str, new_names: str -> merges: ConceptMerges"
    output_field = "merges"
    output_model = ConceptMerges
    instructions = _INSTRUCTIONS

    def __init__(self, *, skills_dir: str | None = SKILLS_DIR, **kw: Any) -> None:
        self.tools = [make_grounded_validator(ConceptMerges)]
        apply_skills(self, skills_dir)
        super().__init__(**kw)
