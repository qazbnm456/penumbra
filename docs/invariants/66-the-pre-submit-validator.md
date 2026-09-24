# Invariant 66: The pre-SUBMIT validator

**Every task's pre-SUBMIT validator is `instructions.make_grounded_validator` (schema plus "no `[[SRC:...]]` marker in the model's own prose"), and SUBMIT belongs on a later REPL turn than the call that validated.**

"Only submit after it reports success" was read as an order within one cell: a real run wrote `print(validate_podcastscript(json_str))` followed by `SUBMIT(final_output)`. That validates nothing, because the verdict is printed where the model cannot act on it; the submit beside it has already run. The rule now names that pattern with the task's own tool name and offers a guarded single cell as the alternative. Together with a higher rejection limit, it was confirmed live, in a single run (so invariant 4's caveat applies).

The marker check started on the podcast, where the failure was loud (the voices read markers aloud), but `GenerateSummary` produced the same defect silently. Six tasks with six validators is how one of them had a check the other five lacked, so there is one validator factory for all six.

It is not a schema-level rejection. Nothing rewrites stored artifacts (invariant 62 strips on the way out), so orbits written before this validator hold whatever the model produced, and a field validator would make those files fail to load. The check belongs where the model can still act on it.

`Citation.quote` is exempt, because a quote is copied from a source and a source containing the literal text `[[SRC:` would make an honest quote look like a violation. Every other string in every output model is the model's own prose, where a marker is always wrong.

`_marker_offenders` reads `model_fields` from `type(value)`, walks dicts and sets as well as lists, and words its rejection differently depending on where the marker is. Each of these closes a way to fail open: reading `model_fields` from the instance is deprecated in pydantic 2.11 and removed in 3.0, a skipped dict would hide markers, and telling a model to move a coordinate into its `citations` entry when the offender is a citation field is advice it cannot follow. A guard that fails open is worse than none, because the prompt still promises it.

## The script check for Chinese output

A fourth check, the only one allowed to be wrong, applies when the run's resolved `output_language` names a Chinese variety (`script_family`, from the `arun` argument; matching on the language name is right here, although it was wrong in the prompt, which only sees a placeholder). Every character of the model's own prose is tested against the other script's inventory.

- The membership test is Big5 encodability, not `zhconv`'s `SIMPONLY` set, which contains `干`, `台`, `群` and `里`, ordinary Traditional characters this project's orbits use correctly (`干預`, `一台`, `里程碑`). Big5 answers the question that matters: does the glyph exist in the Traditional inventory at all. `zhconv` still supplies the suggestion and limits the set to known Simplified forms, so a rare Traditional character outside Big5 is not flagged.
- The 131 characters Big5 lets through are enumerated: 52 are listed as shared in `_BIG5_SHARED` and the other 79 are flagged anyway. `test_the_big5_letthrough_is_fully_classified` asserts the two halves cover the let-through exactly, so a `zhconv` upgrade fails the build instead of quietly adding an unread character. A character counts as shared only where it has a live Traditional use the phrase table does not already protect. Proper nouns keep a character shared even where the Simplified form is commoner (`范` in 范仲淹, `余`, `涌` in 東涌, `涂`, `朴`, `杰`, `岳`, `郁`), because invariant 39 forbids changing a name and a model told `范 -> 範` would write `範仲淹`. A sibling project ranks these the other way because its corpora are technical; both choices are defensible.
- The suggestion is computed in context, because a character table cannot answer it: `历` is `歷` in `历史` but `曆` in `日历`, and `发` is `發` in `发现` but `髮` in `头发`. The whole string is converted with the phrase-aware `zh-hant` mapping, and each offender takes the character at its own position, falling back to the table if the conversion changes the length.
- The suggestion follows Taiwan's standard where the phrase-aware pass made no choice of its own, never over one; otherwise `日历` would lose `曆` again. `zh-hant` maps `为` to `爲` where Taiwan writes `為`, and likewise `众`, `启`, `账` and `伪`. Each is mapped through `zh-tw` from the source character, and only character by character, because `zh-tw` also rewrites vocabulary (`鼠标` to `滑鼠`) and would misalign the positions.
- Precision is bought, not free. `_actionable` drops any offender whose suggested fix is the character it already has, which is what happens wherever the phrase-aware pass confirms the character is right in that word; without it the check rejected `拮据` with `据 -> 据`. It does not replace the shared list, because it rescues only four of 27 ordinary Traditional words. A missed character is one wrong glyph on screen; a false rejection is one the model cannot satisfy.
- It rejects at most three times per run (`_SCRIPT_REPORT_LIMIT`), and the bound is the design. Every other check rejects something wrong, while a Simplified character is cosmetic, and the detector cannot tell it from a Japanese character quoted inline (`学`, `会`, `国` and `峡` are also Japanese forms). A limit of one meant a model that fixed its text and validated again was told "success" whether or not it had fixed anything; three allows a fix, a check and one more fix, at a worst case of three turns out of 25. `quote` is exempt, as for the marker walk.
- The reverse direction, Simplified output, is not enumerated and still uses the GBK codec. Merging the two branches once left the Simplified direction with no gate at all.

Measured live across three episodes, the check reduced flagged characters, but most flags in the control group were `峡`, which the rejection message allows the model to keep, so the evidence is weaker than the count suggests. The accepted recall loss showed up once: `厘清` survived, because `厘` is valid Big5.

A sibling project handles the same problem differently: on the host, after generation, strict per character on page titles and tolerant (majority-based) on page bodies, and it rewrites titles it finds wrong. Splitting strictness by field (strict where text is short and entirely the model's own, tolerant where it quotes sources) is a better principle than a single strictness level. Its membership test does not transfer: it flags any character the `zhconv` table would rewrite, so on correct Traditional prose it reports `干`, `里` and `群` and would store `幹預`, `裏程碑` and `一羣` in a title.

## Three layers

The validator runs before SUBMIT, `citations.strip_markers` runs at the display boundary (invariant 62), and `tts.spoken_script` runs before synthesis. None is sufficient alone, and all are cheap.

A safety net must not destroy what it protects. A line that is nothing but a coordinate strips to an empty string or a lone punctuation mark, and `EdgeTTSProvider` raises `NoAudioReceived` for punctuation-only text, which would turn a garbled line into a lost episode and a discarded paid run. `tts.spoken_script` therefore falls back to the original text when nothing alphanumeric survives. That is measured for the default provider; Chatterbox's behaviour on an emptied line is untested.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
