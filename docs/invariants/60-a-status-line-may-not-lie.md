# Invariant 60: A status line may not lie

**A status line may not claim something the page is not doing, and a repaint may not delete a run.**

`runStatus` tracks `awaitingFirstReply` separately from `stepsSeen`. `setPhase` names a stage the trace cannot see, such as the podcast's synthesis, which produces no events, so "waiting for the model's first response" would be false there. The pre-first-step message used to replace the phrase, so a phase set at second 0 was gone by second 20, and with Chatterbox synthesis lasting up to fifteen minutes (invariant 43) the page looked stuck for the whole second half.

`.btn:disabled` is styled for every button, not just the primary one. A disabled Stop used to look identical to a live one, so `stoppable: false` produced a control that looked usable and swallowed the click. Disabling rather than hiding is right, because a control should not vanish from under the pointer, but only if disabled looks disabled.

Only a successful script run leads to the synthesis phase. Switching the phase on any terminal event would announce a stage that never starts and grey out Stop until the HTTP error arrives.

A repaint carries the run in flight with it. Rebuilding the thread from `state.turns` alone would delete a running question, its status and its only Stop, so the pending turn carries its status row and every rebuild puts it back (invariant 47).

Citation numbers and verdicts are re-stamped across the whole page, not only on the surface that changed. The orbit-wide order runs overview, turns, podcast, then guides, so adding a chat turn shifts the numbers of every podcast and guide citation, and removing a source changes which citations verify. Those panels do not re-render, so `renumberStrokes` walks every `.citation[data-ref-key]` and re-stamps its number and its verified state from the current data. Re-rendering the podcast would rebuild its `<audio>` and interrupt playback. The number goes only on a mark's last fragment (`data-stroke-end`), and a number that resolves to nothing leaves the attribute absent rather than `"0"`, because `content: attr(data-reference)` would print the zero.

A substring assertion is not a behavioural one. Assertions in `test_web_assets.py` check a rule's subject (its last compound selector), the order of two branches, the direction of a comparison and the exact mapping expression, because "token appears somewhere" checks let six of twelve mutations through, including `i + 1` becoming `i`. Behaviour itself is tested by running the real functions in the node harness.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
