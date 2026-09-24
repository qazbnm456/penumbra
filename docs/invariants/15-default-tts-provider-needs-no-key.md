# Invariant 15: The default TTS provider needs no key

**The default TTS provider (`PN_TTS_PROVIDER=edge-tts`) needs no API key or paid account, so `penumbra audio` works out of the box.**

This is the same reasoning as shipping OCR on by default (invariant 7): ship a working default, not just an interface. The list of known providers lives in one place, `_PROVIDERS` in `tts.py`, and `get_tts_provider` refuses an unknown name loudly. `config.py` deliberately keeps no second copy to validate against, because a second list drifts.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
