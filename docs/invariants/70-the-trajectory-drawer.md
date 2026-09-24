# Invariant 70: The Trajectory drawer

**The Trajectory drawer (`trajectory.py` plus `GET .../runs/{run_id}/trajectory`) is where a run's reasoning lives, not the chat bubble.**

The inline step log put the planner's prose inside the answer. The drawer has turn navigation, a tool timeline whose segment widths follow real elapsed time, a detail pane, search, and a replay that dwells on each turn for the time it really took divided by the playback speed.

## What the server computes

The decomposition happens on the server, and the two clocks are kept apart. Planner turns (`iterations`) carry per-turn timing only when the trace was stamped live; an older trace flushed every step at the end, so its timestamps cluster and durations are omitted rather than invented. Tool and sub-LM calls (`timeline`) always have real timing.

It is server-side because a trace can hold full source text (invariant 29), and per-field caps keep a multi-megabyte REPL output from reaching a page that only shows a preview. It is one of the full-exposure surfaces under invariant 25's posture.

It reads traces that are still being written, which matters for a run lasting minutes: a torn final line means the writer is mid-flush and is skipped, not raised on. The read runs in a thread.

A `validate_*` call shows its verdict, because on a failed run that is the most useful fact in the trace: what the model was told to fix, and how many rounds it took. It reaches the trace only because the validator records it. `rlm_harness.record_tool_call` is opt-in, and the validator did not call it for a long time, so the timeline was empty on every run while the drawer claimed "this run called no tools". The validator input is the whole artifact, so its length is recorded and its text is not (invariant 52's rule); the verdict is the model's own rejection message and contains paths, coordinates and character names, never source text.

A duration measured by the tool beats the gap on the strip, and a turn's first call gets no gap at all. Sizing each segment by the distance from the previous event charges the tool with everything since, and a call measured at 1.9ms was drawn as 3.3 seconds. The gap remains the fallback, except for the first call of a turn, where it would reach back through the model writing the code cell and be mostly model time under a tool's name; a sibling project found that a third of its displayed durations were such first calls. `duration_measured` keeps a self-timed call out of that rule.

## Cache and Regenerate

A run can legitimately make no model calls. `dspy.LM` caches by default, so a run with an unchanged corpus, language and tier replays the previous one: same turns, same reasoning, zero calls, 3.4 seconds instead of 263.6. The drawer then reports a cap with no usage and omits per-turn timing, both correctly.

Regenerate bypasses that cache (`RunOptions.fresh`); a first generate does not, because there a cache hit is a free correct answer. The flag follows whether the artifact exists (`Boolean(state.overview)`, `Boolean(state.podcast)`, `AskRequest.regenerate` for chat), never a constant. It travels alongside the task arguments, never inside them, because anything in the arguments reaches the model as a signature field (invariant 39). The worker switches the cache globally with `dspy.configure_cache(...)` before `setup`, which is correct because a worker handles exactly one run, and rebuilding the LMs instead would duplicate `runtime.configure`'s `lm_kwargs`.

Four of the five run-taking handlers accept it. `/title` is exempt because a title is never overwritten, so there is nothing to regenerate. `guide` accepts it although no client sends it today, because a handler that ignored a shared field would be a silent exception. The CLI cannot bypass the cache at all; that is a gap, not a decision.

## The drawer in the page

The replay draws its progress through the stop it is dwelling on, and names the stop, because without a bar a long dwell looks like a frozen panel. The transition restarts at each stop (cleared, reset to zero, forced reflow, then run); without the reflow the browser merges the writes and the bar jumps to full.

The timing note and the budget note share one row but stay two elements, because the budget note turns red on truncation and the timing note never does. The row pairs its `display: flex` with a `[hidden]` rule (invariant 36) and a `:has()` rule that removes it when both notes are hidden, so no empty margin remains.

Interface text is built from the server's boolean, not its sentence. `timing_note` is English prose from Python, and showing it verbatim put English in the middle of a Chinese drawer; the server says which case holds and the interface says it in the reader's language (invariant 48).

There are two "⌁ N steps" affordances: `runStatus` owns the live log during a run, and `renderTickerAffordance` owns the pill under a finished artifact, which readers press most. Both open the drawer.

A tool segment offers a way back to the turn that called it, whenever the segment is attributed to a turn; a button reading "open turn null" would be worse than none.

A segment is sized `flex: <normalised duration> 0 <floor>px`. Growth against the strip's total alone produced unreadable slivers, a fixed width stranded a one-call run beside empty space, and the floor keeps a fast call legible while the strip scrolls. Normalising the weights so they sum to 1 matters: CSS stops distributing space at the sum of the grow values, so a run of millisecond calls summing to 0.06 left 94% of the strip empty.

A turn mark reads `T<index + 1>`, because the data is 0-indexed and every other surface counts from one. A segment's label is its target; the family, offset and owning turn are in the detail pane. A `data-tip` on a segment cannot work, because the segment clips itself and `.traj-timeline` scrolls horizontally (invariant 54). A fixed-height box with `overflow: hidden` needs declared line heights, or a 72px segment stacking three lines at the default line height clips the middle one; a test recomputes the sum from the stylesheet.

`traces.run_meta` records what the run was configured with and what it was asked to do, for both entry points: model names, budgets, the corpus size and every short scalar input (the question, the resolved language, the podcast tier). None of that can be recovered later from an orbit that has moved on. The corpus text never goes in, only its size, and neither do `api_key` or `base_url`. It lives in `traces.py`, which stays free of `dspy` and `rlm_harness`, so the CLI pays nothing to import it.

An empty panel looks broken, so the empty state says which kind of empty it is. The exclusive trace reservation (invariant 29) means a run opened in its first moments, one whose spawn failed or one killed instantly has a real file with no events, and that state stays reachable.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
