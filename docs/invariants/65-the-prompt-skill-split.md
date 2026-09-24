# Invariant 65: The prompt and skill split

**Every RLM task here carries `rlm_harness.skills` with `discovery="inject"`, and the split between prompt and skill is a rule, not a preference.**

These are `rlm-harness`'s skills for the task's model, not the Claude Code skills a coding agent reads.

A skill is read only if the model chooses to read it, so anything that corrupts the output when skipped stays in the prompt: grounding, citations, the marker rule, language, the output shape and the length target. Craft and measured technique belong in a skill, because work done without them is duller or more expensive, not wrong. A no-disfluencies rule and a good-close rule appear in both on purpose: they must always apply, so they stay in the prompt, and the skill holds the reasoning.

`instructions.ACCUMULATE_LARGE_OUTPUTS` is where the split had to be corrected. The build-across-turns mechanic (invariant 64) must always apply, because skipping it loses the run, yet it once lived only in the podcast prompt and reached the other five tasks only through an optional skill. It is now a shared constant in all six, worded as a condition, because a short answer built across turns wastes steps just as a long one written in one reply loses the run. A tripwire asserts that all six carry it and that the podcast has exactly one copy.

`instructions.apply_skills` is the one copy of the wiring, for the same reason as `CITATION_RULES`: six tasks each calling `load_skills_as_tools` would each own a catalog header, and the headers would drift. A test forbids `load_skills_as_tools` in `audio.py`, `guide.py` and `task.py`.

The catalog is closed with `</available_skills>`, and the manifest decides whether anything is wired at all. Without the closing tag, every rule after it reads as if it were inside the skills element. Gating on the manifest rather than on the directory's existence stops an empty directory from adding `read_skill`, whose description tells the model to choose from a manifest that would not exist. Both directions are pinned.

`skills_dir` is a constructor argument that defaults on. A test points it at a fixture and `None` turns it off, which a caller needs because a stale skill is worse than none; it defaults on because a planner that has to be told to consult its own notes will not. `read_skill` resolves a name against the skills found at construction, so it cannot read an arbitrary path and never uses the network, which keeps invariants 1 and 14 intact.

There is one directory for every task, because `discover_skills` reads a single directory without recursing and a catalog line per skill is cheap. Split it when a chat turn is measurably paying to hear about podcast craft, not before. The files ship inside the wheel, for invariant 29's packaging reason.

Provenance is part of the craft. A skill is a lasting claim about how to work, and an unchecked quote in one is worse than no skill, because a later reader has no reason to doubt it. Every technique in `podcast-craft` must trace to a source someone actually opened, or to this project's own measurement.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
