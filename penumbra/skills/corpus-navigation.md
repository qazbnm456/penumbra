---
name: corpus-navigation
description: How to read a multi-megabyte corpus blob and build a large answer inside the REPL without exhausting a budget — the measured failure modes, and what each one costs
---

# Working the corpus blob in the REPL

`sources` is ONE string holding every source in the collection, each block preceded by a
`[[SRC:<id>|<locator>]]` marker. When you are answering, guiding or scripting you also get
`source_index`, a table of contents with every block's marker, size and opening words, so the first
`.find()` is a lookup rather than a hunt. There is no search API: you read `sources` with ordinary
Python — `.find()`, slicing, `enumerate`, a regex when it earns its keep. That is the point of this
architecture, and it is why a step per probe is the NORMAL shape of a run here, not a sign of
floundering.

Everything below is a measured failure from this project's own runs, with what it cost.

## Never build a large result in one code block

**Measured.** A podcast script targeting 60-90 turns, written as a single code block, was cut off by
the per-call generation cap mid-structure. The salvaged fragment parsed as an empty object and the
run failed after about two minutes of model time, all of it wasted.

Build it across turns instead: keep a list in the sandbox, append a few items per turn, and SUBMIT
the finished variable at the end. The same collection, the same 131,057-character corpus and the same
cap then produced 80 turns with 44 citations in 166 seconds. **Nothing about the budget changed —
only where the work was accumulated.**

(That comparison was run in-process, one tier against the other, so no trace file records it: a
direct `arun` has no `TraceRecorder`. The evidence is the run's own output, not something `traces/`
can be searched for.)

This generalises to any large output, not just scripts: a long summary, a many-item FAQ, a timeline
with dozens of events. If the finished object will not comfortably fit in one reply, it should not
be written in one reply.

## Never print what you are accumulating

Printing your growing result back to yourself puts the whole thing into the next turn's prompt,
which spends the same budget a second time and brings the ceiling above that much closer. Print its
LENGTH to check progress (`len(utterances)`), never its contents.

## Read a lot before you write; reading too little is the measured failure

**Measured, in a sibling project on the same harness.** Across six real runs over one corpus, the run
that stopped after ten turns had read 2.2% of what it was given and wrote the thinnest result of the
six; the best one had simply looked at the most. Finishing early is not efficiency, it is an answer
with nothing behind it.

Print in LARGE slices, not cautious peeks. Across 253 real turns there, the median turn brought back
about 1,080 characters and only 7% came near the output cap, while whole runs used 5% to 18% of the
model's context window. Here the cap is 40,000 characters a turn: a few thousand characters of a
source costs nothing worth saving, and a peek of two hundred costs a turn to go back for the rest.

What is expensive is re-printing your own growing DRAFT (see above), not reading more of `sources`.

## Know how much you have covered

Nothing tells you what fraction you have read unless you measure it:

```python
import re

MARKER = re.compile(r"^\[\[SRC:([^|\]]+)\|([^\]]+)\]\]$", re.M)
blocks = [(m.group(1), m.group(2), m.start()) for m in MARKER.finditer(sources)]
print(len(sources), len(blocks))   # how much there is, and how many blocks
```

Keep the offsets you have printed and compare them with `len(sources)`. About to write after reading a
small fraction of a large corpus is the signal to spend more turns, not a sign you are ready. A marker
always occupies a whole line, which is why the pattern anchors on `^...$`: a source that mentions the
marker format in its own text would otherwise cut a block short.

## Slice a quote out of `sources`; never retype it

A `Citation`'s `quote` has to be the block's own words. You hold the exact text in a variable, so
take the quote by SLICING it; retyping what you read a few turns ago is where quotes drift, and the
drift is invisible to you at the time. Measured in the same sibling project: nine of nine citations
on one run failed because the model re-wrapped whitespace while transcribing text that was really
there.

```python
def block_text(sources, source_id, locator):
    """The exact text of one block, found by its marker."""
    for m in MARKER.finditer(sources):
        if (m.group(1), m.group(2)) == (source_id, locator):
            start = m.end() + 1                  # past the marker's own newline
            nxt = MARKER.search(sources, start)
            return sources[start:nxt.start() if nxt else len(sources)].rstrip("\n")
    return None

text = block_text(sources, "s1", "page:3")      # COPY both values from a marker
i = text.find("words from the claim")
quote = text[i:i + 200]                          # as much as the claim needs
```

The `source_id` and `locator` are copied from a marker, never typed: a citation whose coordinate is
this snippet's placeholder resolves to nothing.

## The step budget is generous but not unlimited

**Measured.** A Summary took NINE main steps and about three minutes of model time against a budget
of ten. One more probe would have lost the run. It is 25 now, which is headroom rather than an
invitation — a run that ends because it ran out of steps loses work that was already paid for.

Spend steps on reading you actually need. Reading the same block twice because you did not keep what
you found in a variable is the common way to waste them.

## Markers are coordinates, not text you write

A `[[SRC:...]]` marker exists so a citation can point at a passage. It belongs in a `Citation`, never
in your prose.

**Measured.** One run wrote 20 markers across 19 of a podcast's 47 utterances and filled in ZERO
citations.
The episode read them aloud as "S R C S one", the reader saw what looked like a broken template, and
every passage those markers pointed at was lost — a citation the interface can resolve is the whole
point of copying the coordinate in the first place.
