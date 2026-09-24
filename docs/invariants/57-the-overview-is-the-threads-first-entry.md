# Invariant 57: The overview is the thread's first entry

**The chat overview is the thread's first entry, inside the scroller, not a panel pinned above it.**

As a sibling of `.chat-history` with `flex: 0 0 auto` and `max-height: 45%`, it permanently took up to half the chat column; inside the scroller it scrolls away as the conversation grows. The `max-height` had a real reason: as a sibling it was a flex item whose minimum size is its content, which would have squeezed `.chat-history`. Inside the scroller there is no competing flex item, so the reason is gone.

Opening an orbit starts at the top of the thread, with the overview in view. Only a new turn scrolls to the bottom; replaying a saved conversation used to scroll once per turn and landed the reader far below the overview.

Every path that redraws the thread goes through `rebuildHistory`, which re-appends the overview node; a `history.innerHTML = ""` that forgot it would silently delete the overview.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
