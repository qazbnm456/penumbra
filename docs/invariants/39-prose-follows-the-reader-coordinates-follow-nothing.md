# Invariant 39: Prose follows the reader; coordinates follow nothing

**Model-written prose follows the reader's language, not the documents'. Citation coordinates follow nothing, and naming a language guarantees neither its script nor its idiom.**

## Coordinates stay verbatim

This is the half everything else rests on, and it covers coordinates as well as quotes. `citations.verify_citations` compares `locator` with an exact `==` and never inspects `quote` (invariant 5). A model told to write everything in Chinese that helpfully turns `page:1` into `第1頁` makes every citation unverifiable, and one that translates a `quote` produces a citation that still shows as verified while no longer quoting the source. `instructions.VERBATIM_COORDINATES` names `source_id`, `locator`, the marker syntax and `quote` together, and is composed before `CITATION_RULES`.

## What a language name does not settle

Script has its own rule, `instructions.SCRIPT_PINNED`. A language with more than one script is underspecified by its name, and a model treats the scripts as interchangeable; a sibling project shipped Traditional Chinese pages whose titles came back in Simplified. The rule names characters (`概览` must be `概覽`) because that cannot be read as a loose preference.

The rule is written as a condition the model evaluates, and it ships in every task unconditionally. An earlier version picked the rule at import time from the language name, but the language reaches a task as a signature field, so every task composed its rule against a placeholder that matched nothing and the rule was silently empty everywhere. `tests/test_instructions.py` therefore asserts on the six shipped task classes rather than on a helper called with a literal language, a call shape the product never uses.

A converter such as `zhconv` stays refused, because it rewrites `干`, `台`, `群` and `里`, which are ordinary Traditional characters this project's notebooks use correctly. Instead, invariant 66's validator rejects Simplified characters in Traditional output and asks the model to look again. That works because the model knows the correct form: asked directly, it writes `霍爾木茲海峽` correctly, and the drift appears only while composing thousands of characters. It is a compliance problem, not a knowledge one.

A proper noun outranks the script rule in both directions, and the rule says so once. The two collide whenever the sources spell a name in the other script. The failure to watch for is a partial conversion, such as `霍爾木茲海峡`, which is neither spelling and cannot be found by searching for either. Whether the rule must forbid partial conversion in so many words is still open.

Register has its own rule, `NATURAL_REGISTER`. A Traditional Chinese answer once wrote `源文` for "the source text" where a reader expects `原文`, a word-for-word rendering of the English. Both are ordinary Traditional characters, so no script rule can catch it; this is about wording and applies to single-script languages too.

## Choosing the output language

`Accept-Language` answers which language an app's interface should use, not which language a person reads research in, so it is not ranked first. Resolution is one cheap `dspy.Predict` (`naming.SuggestLanguage`, not an `RLMTask`, for invariant 37's reason) that weighs the interface language (invariant 69), the header, the sources' language and any questions already asked. Questions weigh most, because they are the one place the reader chose a language instead of inheriting one.

Precedence runs from `RN_OUTPUT_LANGUAGE`, a hard override that applies to chat too, to the settings file (invariant 41), to `Notebook.output_language` (resolved once and stored), to a literal default. The settings file ranks above the stored value because the first two are stated preferences while the stored value is a cached guess, kept only so resolution is not paid for on every artifact.

The language reaches a task as a signature field and is never empty. A class-level `instructions` string is composed at import time and cannot know a per-request language, so the default is a phrase such as "the language the sources are written in". Precedence is resolved in `api.py` or `cli.py` and passed down; `worker.py` must never re-read the environment, or precedence would be applied twice and the stored value would be invisible to the subprocess.

`_resolve_language` runs at most once per request, with its own `-lang` run-id suffix added after derivation. Sharing the artifact's run id would trip the exclusive-create gate, and `/overview` resolves before its `asyncio.gather`, or its two branches would resolve twice under the same id. A failed resolution returns `None` and the caller uses its default, so a language guess never costs the reader the artifact they asked for.

`tests/test_api.py` asserts that every grounded task declares the field. A missing required input surfaces only as an opaque `RLMTaskError`, and an undeclared extra argument is silently accepted, so a partial rollout would fail silently in both directions.

The model's behaviour described here was verified live, because the offline scripted LM cannot show any of it. Forced Chinese against English sources returned Chinese prose with `s1` and `whole` untouched, English quotes verbatim and every citation verified.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
