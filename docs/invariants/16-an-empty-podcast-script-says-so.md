# Invariant 16: An empty podcast script says so

**`PodcastScript.utterances` may legitimately be empty, and `cli._cmd_audio` says so explicitly instead of printing nothing.**

`Timeline.events` and `FAQ.items` have the same allowance and the same fix, because silently printing nothing was a real bug there first.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
