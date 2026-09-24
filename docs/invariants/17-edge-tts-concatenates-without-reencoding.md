# Invariant 17: edge-tts output is concatenated without re-encoding

**`EdgeTTSProvider` synthesises one utterance at a time (one voice per `edge-tts` call) and concatenates the raw MP3 streams without re-encoding.**

This deliberately avoids an `ffmpeg` or `pydub` dependency (`ffmpeg` is a system binary, not installable with pip) for what would only be gapless playback. Weigh that dependency cost before "fixing" it.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
