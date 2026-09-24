# Invariant 14: TTS is host-side, never a tool

**TTS synthesis (`tts.py`) runs on the host, on an already generated and validated `PodcastScript`. It is never a tool the model can call, and `GeneratePodcastScript` (`audio.py`) does not depend on `tts.py`.**

The reasoning is the same as for invariants 1 and 3: synthesis is a real network call, and the model's job, writing a grounded script, is finished long before any audio exists.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
