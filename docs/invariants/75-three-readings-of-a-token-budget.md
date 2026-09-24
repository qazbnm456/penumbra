# Invariant 75: Three readings of a token budget

**A trace's token budget has three readings, and the third is the one that matters (`trajectory.budget_summary`, the Trajectory drawer's budget note).**

`run_end.budgets` and `usage` arrived with rlm-harness 1.10.0, so a trace written before the upgrade has neither. `budget_summary` returns `None` for those, and the drawer says "not recorded", never zero and never a clean result. Reading an absent field as "nothing was truncated" would turn a corpus boundary into a property of the code; the same rule applies to any later analysis, which should split on `run_start.rlm_harness` and treat absent values as unmeasured.

Truncation means `completion_tokens` reached the applied cap. That is rlm-harness's recommended reading, not what dspy's `_check_truncation` does (it looks at `finish_reason == "length"` and never compares token counts). The cap is read from the LM the run actually used rather than from `NotebookConfig`, because an injected `main_lm` is used as is and the configured cap may be one no call ever saw. With no cap reported, `truncated` stays false instead of being guessed from the size of the number. `usage` is per attempt, so the peak is taken across retries, because a retry is the run whose fatal call matters most.

Three different kinds of exhaustion are reported separately: the token cap, the iteration caps (`max_iterations`, `max_llm_calls`) and `max_output_chars`. A reader diagnosing "it stopped early" has to tell them apart. `iterations.dropped` says dspy rejected the budget arguments and every cap reverted to its default; without it, the three numbers beside it would read as applied when they were not.

The ratio of used to cap is shown as a number, with an honest status: a shape to expect, not a figure confirmed on this project's runs. The rlm-harness maintainer measured no early-warning gradient in that ratio at a 32768 cap, the cap this project now uses (invariant 59), and this project's own sample at 32768 is small: two capped calls in 54, at ratios 1.0 and 0.275. What carries to any cap is the mechanism: a truncated code cell is a `SyntaxError` the planner's next turn usually repairs, while a truncated final answer ends the run.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
