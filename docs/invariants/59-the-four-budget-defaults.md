# Invariant 59: The four budget defaults

**The four budget defaults are each a decision, and `max_tokens` is the one that silently kills a run.**

`RLMConfig`'s own defaults are 10, 8192, 10,000 and 1. This project ships `max_iterations=25`, `max_tokens=32768`, `max_output_chars=40000` and `max_retries=1`.

## max_tokens: 32768

`max_tokens` caps each call's generation, and it is a trap for a reasoning model: the reasoning is billed against a cap it never appears in, so an undersized cap returns a reply cut off mid-JSON that fails to parse, and `max_retries=1` makes that final because a second attempt hits the same ceiling. It applies to the sub-model too, because `runtime.configure` builds one `lm_kwargs` for both `dspy.LM(cfg.main_model)` and `dspy.LM(cfg.sub_model)`. On the `claude-agent-sdk/` subscription path (invariant 35) it does nothing, because `ClaudeAgentLM` ignores sampling arguments.

It was raised from 16384 against a distribution, not against one truncation. A live podcast call hit 16384 exactly and came back cut off mid-code. That was a sizing problem rather than invariant 64's structure problem, because the model was already building the script in batches. The size came from a sibling project's 3,683 calls on the same model under a 32768 cap: median 1,621 tokens, p90 6,993, p99 15,030, 0.71% at the cap, and nothing between 60% and 90% of the cap. Legitimate long turns end below about 16k, which is exactly what the old cap cut, and whatever reaches the cap is a runaway no cap would save. Do not raise it again without a distribution.

The budgets multiply: with 25 iterations, `run_timeout_seconds` (scaled per podcast tier, invariant 68) is the only bound on a looping runaway.

The number is a request, and the provider has the last word. Many models have a lower completion ceiling (`openai/gpt-4o` stops at 16384, `gemini-2.0-flash` at 8192), and OpenAI rejects an oversized `max_tokens` before it even checks the key, so every run failed with `max_tokens is too large: 32768` for an operator following this repository's own example configuration. `config._max_tokens_for` clamps to `litellm.get_model_info(model)["max_output_tokens"]` when that is lower and logs both numbers once per model, because a silent override would make the operator's belief about their run false (invariant 9). A model litellm does not know keeps the configured value, because refusing to run without a table entry would break every self-hosted or proxied setup. Lowering the default instead would give every large model a cap chosen for the smallest one.

## The other three

`max_output_chars: 40000` bounds how much of a REPL output reaches the planner's prompt. Every task explores the corpus by searching and slicing and prints the spans, so a truncated output means fetching the span again and wasting an iteration.

`max_iterations: 25`, because 10 was about to be reached: an 8-source orbit's summary took nine main steps. Running out loses a run already paid for, while unused headroom costs nothing because the loop ends when the model submits, and `run_timeout_seconds` bounds a runaway in wall-clock time.

`max_retries: 1` stays. A whole-run retry rarely fixes a persistent failure, burns the budget again and writes a second copy of the same failure into the trace, and a turn-zero parse failure is not transient, because the retry hits the same token ceiling. Unlike its siblings, this project reads `PN_MAX_RETRIES`, but the default does not move, and raising it multiplies the budget: `PN_MAX_RETRIES=5` with 25 iterations is up to 125 iterations. The API has `run_timeout_seconds` as a backstop; the CLI has none.

`worker._describe` carries the root cause across the process boundary. "Failed to produce a valid 'script' after 1 attempts" names the symptom; the exception chain names the cause, which used to be discarded exactly where a person starts reading.

**A thinking budget, not a bigger cap, is what stops a reasoning runaway.** `PN_MAIN_LM_KWARGS` and `PN_SUB_LM_KWARGS` pass extra `dspy.LM` kwargs to one role each (rlm-harness 1.12+), merged over what `configure` builds from the shared `max_tokens`. A concept alignment on a self-hosted Qwen spent 32768 of 32768 tokens reasoning on its retry; on vLLM, `{"extra_body": {"thinking_token_budget": 16384}}`, about half the cap, was measured to end that, and `reasoning_effort` moved reasoning the wrong way. Unset sends nothing, so the four defaults above still hold as written.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
