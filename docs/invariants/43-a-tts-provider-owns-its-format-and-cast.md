# Invariant 43: A TTS provider owns its format and cast

**A `TTSProvider` owns its output format and its cast, and since it may be cross-lingual it receives the language as a separate input. None of the three belongs to the caller.**

Voice names are provider-specific (edge-tts wants `zh-TW-YunJheNeural`, Chatterbox wants one of its shipped clip names), so `default_voices` and `fallback_voices` live on the protocol; a shared map would leak one provider's names into another's request. The format is the provider's for the same reason: Chatterbox emits 24kHz WAV, and forcing it through an MP3 encoder would bring in the `ffmpeg` dependency invariant 17 refused.

`synthesize` takes `language` because a cross-lingual provider treats voice and language as independent. `EdgeTTSProvider` ignores it, because an edge-tts voice id already carries its locale. For the same reason `ChatterboxProvider.default_voices` returns `None` for every language, which routes the default to `fallback_voices` as invariant 40 intends. An unknown language raises instead of falling back to `"en"`, because Korean synthesised with an English language id is confident nonsense.

`validate(language, voice_map)` runs before script generation, not inside `synthesize`, which is invariant 19 applied to the provider's inputs. A language Chatterbox has no id for (Thai and Vietnamese are in edge-tts's map but not in `_CHATTERBOX_LANGUAGES`) would otherwise waste a model call on every attempt. `EdgeTTSProvider.validate` is an explicit no-op, and a source-tree test pins the ordering at both call sites.

## Chatterbox is the local option, not the default

`ChatterboxProvider` (`RN_TTS_PROVIDER=chatterbox`, the `chatterbox` extra) needs no network and no key, and it sounds better. That is the right trade for a reader who cannot send sources to a cloud service, and the wrong one to impose by default: on the same input it took 33 times the wall-clock time and produced 9 times the bytes, and a 3.4-minute episode took 16.1 minutes, 15.0 of them synthesis, during which the run cannot be stopped.

Because the configured provider may not be the one that generated an episode, `notebook.find_audio` looks for whichever format is present, `clear_audio` removes every format before a regenerate, and `GET .../audio/file` takes its media type from the file.

Chatterbox's output length is unstable (the same sentence measured 34.80s, 5.48s and 11.68s against about 7s expected), so `_generate_one` re-rolls against `expected_seconds` and keeps the shortest take if it never converges, because losing a paid episode is worse than one clipped line. `expected_seconds` is calibrated against measured utterances and pinned by a test; a moderate 1.7 times overshoot is deliberately allowed, because a tighter bound would reject correct takes.

Two hosts need two reference clips, because the checkpoint carries a single built-in voice and giving it to both hosts turns a conversation into a monologue. `rlm_notebook/voices/host_a.wav` and `host_b.wav` are ten-second clips synthesised with Kokoro (Apache-2.0); no person was recorded, because cloning a real voice raises a consent question a licence does not answer. `rlm_notebook/voices/README.md` states the provenance, including that Kokoro's training data includes synthetic audio from closed models, and the escape hatch: `RN_TTS_VOICE_HOST_A` and `RN_TTS_VOICE_HOST_B` accept an absolute path to your own clip. The built-in voice is captured before the preparation loop, because it exists only as `model.conds` and the first `prepare_conditionals` overwrites it; otherwise a mixed cast (one built-in, one clip) would come out in a single voice after fifteen minutes of synthesis.

A clip path is accepted from the environment only, never from the settings file. `_VOICE_PATTERN` excludes `.` and `/`, so a page any token holder can write cannot become a file-read surface (invariant 26's reasoning on a second channel).

## Packaging

The extra is marked `python_full_version >= '3.13'`. `chatterbox-tts` pins `numpy<2.0.0` below 3.13, and uv's lock is universal, so an unmarked extra pulled numpy back to 1.x for every 3.11 and 3.12 install. numpy 1.x breaks with the required dspy: dspy's lazy numpy import re-runs numpy's `__init__` while it is partly imported, so `import dspy; import cv2` fails and takes the OCR path with it. That is why `numpy>=2` is a core dependency. Below 3.13 the extra resolves to nothing, and `ChatterboxProvider`'s import guard reports a `TTSError`.

It is an extra, never a core dependency, and its two unusual pins matter. `numba>=0.61` stops the resolver from backtracking to an `llvmlite` that fails to install on 3.13. `setuptools<82` is needed because `perth` and `librosa` import `pkg_resources`, which setuptools 82.0.0 removed, and `perth` swallows that error and fails later with an unhelpful `TypeError`. The imperceptible watermark is kept, because a provenance marker on synthetic speech is a feature.

Nothing is adopted here until it has been installed and run; earlier recommendations taken from unverified sources were wrong.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
