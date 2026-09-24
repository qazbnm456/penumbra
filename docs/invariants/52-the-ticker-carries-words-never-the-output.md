# Invariant 52: The ticker carries words, never output

**The live ticker's event shape is `{kind, primary, detail, meta}`, and it carries the model's own words but never a step's output.**

`_translate_trace_event` used to emit one fixed sentence per event type and discard the payload. `summary` is kept as `primary` plus `detail` so older consumers of the one-line shape keep working, and the synthesised terminal event for an orphaned run comes from `_orphaned_run_event` rather than a hand-written literal.

A `tool_call` names the tool and says what it did: the tool name is `primary`, the first sentence of the verdict (or the named argument) is `detail`, and a rejection sets `meta`. It used to say only "Tool", so while the validator was rejecting a draft the status line showed "4 tools, 18 steps" and nothing more. Only the first sentence is used because a verdict is written for the model: it names the offending characters and then tells the model what to do, and streaming it whole filled the live line with advice addressed to someone else. The full text stays in the trace and the Trajectory drawer. A rejection keeps the kind `tool`, because `failed` is terminal and would close the live log while the run continues.

`detail` is usually the model's own prose, but a `main_step` without `reasoning` falls back to the step's code, and a `result` event carries the key names of its output. `detail` can therefore quote ingested source text, since prose and code both repeat what the model just read; that is the same exposure invariant 29 records for the trace endpoints, on an API with no authorization (invariant 25). What is never streamed is the step's `output`, where whole corpus spans land; its size is reported instead. `_DETAIL_CHARS` bounds the rest, because this goes down an SSE stream once per step.

`run_end` with `ok=False` has `kind: "failed"`, not `"done"`, so any client's terminal check must accept both, or a failed run's ticker never closes.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
