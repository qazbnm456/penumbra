# Invariant 71: A repaint may not delete a run

**A repaint may not delete a run, and `#chat-overview` belongs to its generation while one is in flight (`overviewRunning`).**

Invariant 60 fixed this for the pending chat question; the overview's own run had the mirror-image hole. `renderChatOverview` clears the element that holds the run's pulsing dot, elapsed time and only Stop, and several callers invoke it for reasons unrelated to the run. The guard sits at the top of `renderChatOverview`, so every caller is covered without a list to maintain. It matters more because of a deliberate decision nearby: a source change does not bump `overviewToken`, because stranding a generation the server has already paid for would be worse, so the run stays live and must stay visible.

A notebook switch must release the flag, not just bump the token, or the new notebook's panel keeps the old run's status. `!live()` covers two cases and only one belongs to this panel: a second press of Generate is a supersede and must say so (invariant 47), while after a notebook switch `#chat-overview` belongs to another notebook and a "superseded" note would overwrite its overview. Both call sites check `generation === notebookGeneration`. The overview releases the panel and the composer only while its run still owns them (`releaseIfMine()`), so an overview ending in one notebook never unlocks another. A failed regeneration keeps the existing overview and shows the failure above it.

Regenerate is always available once an overview exists; `offerRegenerate` chooses its label and weight, not its presence. Gating it on stale or incomplete left a current, complete but wrong overview, the state a reader most wants to escape, with no control at all. It is quiet when nothing is wrong, because regenerating costs two runs, and louder when the overview is stale or incomplete, the same three states invariant 42 gives the podcast.

`/overview` runs two tasks and its ticker follows one, so forwarding the summary run's end made the status say "Finished" beside a live Stop while the FAQ half still ran. It stays stoppable, because `runIds` carries both ids.

## The composer during an overview

The chat composer is frozen while an overview generates. That is a product decision, not a race fix, and it covers the composer only, never the thread. Nothing would be lost either way, but a question asked into a thread whose overview is being rewritten reads as two things fighting. Clearing the conversation was suggested as an alternative and is the one thing not to do, because it would destroy history to signal a temporary state.

The composer has two owners, the overview and a question, and it is held while either runs: `pending || overviewRunning || pendingTurn.pending`. One answer to "may a new question start now", `composerLocked()`, which also covers a recovered run, is asked by Send, by the submit handler that Enter goes through, by ↻ Regenerate, by the suggestion chips and by Clear. Each used to decide on its own, and a repaint re-enabled Send mid-run.

## Regenerating and clearing chat

Only the last chat answer can be regenerated. Every later answer was produced with this one in its `history` (invariant 11), so redoing one in the middle would leave later answers derived from a conversation that no longer exists. A stylesheet rule hides the control on any turn followed by a later turn (`.turn:has(~ .turn:not(.is-stopped))`), because turns reach the DOM through two paths and a rule that reads the DOM is right for both. It is keyed on later turns rather than on being the last child, so a recovered run's status line or a stopped question does not hide the newest answer's control. The server checks independently: `AskRequest.regenerate` replaces `turns[-1]` only if its question still matches, inside the lock, and otherwise appends. It replaces rather than appends because the reader regenerates when an answer was wrong, and keeping it would keep it in `history`. Both paths share one flow, `askQuestion`.

A conversation can be cleared (`DELETE /notebooks/{id}/turns`). Regenerate reaches only the last answer, so clearing is the honest way to undo a turn in the middle. Sources, notes, the overview and the podcast are untouched and nothing is marked stale, because the corpus has not moved. The confirmation names what survives as well as what goes.

The Clear control hides when there is no conversation and appears after a fresh notebook's first answer. It is kept in sync from the existing `chat:turnAdded`, `chat:rerender` and `notebook:switched` handlers and from the question's success path, never from new subscriptions: `test_no_event_is_subscribed_twice_inside_one_init_function` forbids a second handler for one event inside one init.

Clear is disabled whenever the composer is locked. While a question runs, the server would delete the turns and then `ask` would append its answer to the empty list, bringing the cleared conversation back with one entry. The handler also passes the pending turn to `rebuildHistory`, keeps `pendingTurn`, and captures `notebookGeneration`, so a notebook switch during the delete never clears the new notebook's conversation.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
