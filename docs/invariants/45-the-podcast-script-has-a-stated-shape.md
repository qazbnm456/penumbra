# Invariant 45: The podcast script has a stated shape

**The podcast script has a stated shape and is written to be spoken in one language.**

Asking only for "a natural conversation" gave episodes no opening, no plan and no close; they stopped when the model ran out of facts. The instructions ask for an opening that frames the sources, a body that follows the most interesting thread rather than the sources' order, and a close that ties the threads together. Any reflection must stay grounded: "what this makes me wonder" is honest, an invented finding is not.

There is exactly one close, written last, after every source the model means to use has been covered. The shape rule asks for a close and invariant 64 asks for long scripts to be built across REPL turns, and neither said where the close goes. A model that finished a batch wrote a closing exchange, then found unused material and kept going. On a real 70-utterance episode, "thanks for listening" and "goodbye" came at utterances 48 and 49, followed by twenty more turns and a second close, so the listener heard the episode end and start again.

Foreign proper nouns stay as the source wrote them. `Utterance.text` is both the transcript and what the voice reads, and the transcript is what a listener falls back on when a word does not come through, so a transliterated name is exactly the word they cannot then look up. edge-tts, the shipped default, reads mixed Chinese and English acceptably; an earlier transliteration rule existed only for a provider that is gone. Acronyms are named explicitly in the rule, and adding the original in parentheses is forbidden, because a listener has no reader-only channel for it. Numbers, dates and units are still written in spoken form. A `Citation.quote` is exempt and stays verbatim, because it is evidence a reader checks against the source (invariant 39).

A provider that mangles Latin names would now mispronounce them; that is a provider problem to fix in the provider, not by degrading every transcript in advance. As with invariants 4 and 11, these are claims about prompt compliance, which the offline suite cannot demonstrate.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
