"""`DistillLongDocument`: the summary of a document too long to read in one model call.

A short document is summarised by one `dspy.Predict` call that reads all of it (`distill.py`). A
long one used to be summarised from its first few thousand characters, which named the subject of
the introduction and nothing else. This task gives the model the whole document as a REPL variable
and, in the prompt, a map of its sections with their sizes and opening lines, the way a planner is
given a compact summary of a tree rather than the tree: the map says where to look, the REPL is
where it reads.

It is an `RLMTask`, so it runs only in `worker.py`, in a subprocess and the Pyodide sandbox
(invariants 9 and 21), and it is grounded: every entity carries the coordinate of a block that
names it, checked before SUBMIT by the shared validator (invariant 67) and again by the host, which
drops a mention whose coordinate is not a real block.
"""

from __future__ import annotations

from .instructions import GroundedTask, artifact_language_rule, validate_before_submit_rule, with_step_budget
from .schema import LongDistillation

__all__ = ["DistillLongDocument"]

_INSTRUCTIONS = f"""\
Summarise ONE long captured document so its owner can find it again months later, when they have
forgotten the words it used.

`sources` is the whole document as a REPL variable. Each block is preceded by a marker line of the
exact form `[[SRC:<source_id>|<locator>]]`. `section_map` lists every block's locator, its size in
characters and its opening words, in order. Use the map to decide where to read, then read those
parts of `sources` with Python (`.find()`, slicing); do not try to print the whole document.

Write:
- title: a short, specific label. Name the actual subject, not the document type.
- summary: two or three sentences on what the whole document says and why someone kept it, not
  only its opening. No preamble.
- tags: up to 6 lowercase broad subjects a person would search by (sleep, memory, coffee).
- entities: up to 6 specific things the document is ABOUT: people, organisations, products,
  places, and named concepts such as a theory, a method, a condition, a stage or a part of the body.
  For each, give `name` and the `source_id` and `locator` COPIED VERBATIM from the marker of a block
  that names it. Never compose a coordinate; an entity you cannot find a marker for is left out.

Rules:
- Say only what the text supports. If it is too garbled to summarise, give an empty summary.
- A marker is a coordinate, not content. Never copy one into the title, summary, tags or a name.

{artifact_language_rule("the language named by the `output_language` variable")}

{validate_before_submit_rule("validate_longdistillation")}
"""


class DistillLongDocument(GroundedTask):
    """Summarise one long document from a section map plus the whole text in the REPL."""

    #: A real run on a 230,000-character document took 9 turns; 15 leaves room without handing a
    #: one-document summary the budget of an orbit-wide guide.
    STEPS = 15

    def __init__(self, **kw) -> None:
        super().__init__(**with_step_budget(kw, self.STEPS))

    signature = "sources: str, section_map: str, output_language: str -> distillation: LongDistillation"
    output_field = "distillation"
    output_model = LongDistillation
    instructions = _INSTRUCTIONS
