# Invariant 69: The interface language signals the output language

**The interface language is one of the signals for choosing the output language, a fourth one ranked above `Accept-Language`. This narrows invariant 48 without merging the two.**

A user with a Chinese interface got an English notebook title, because the one place they had actually said which language they read was invisible to `naming.SuggestLanguage`.

A chosen preference outranks an inherited one. `Accept-Language` comes from the operating system, while the interface language was picked in this app; that is the whole justification, and it is the same reasoning invariant 39 uses to weight typed questions highest. Invariant 48's separation survives: the settings page keeps two rows, and an explicit output language still wins outright.

The value travels in a header, `X-RLM-Interface-Language`, added once in `api()` in `app.js`. `_resolve_language` is reached from every run-taking endpoint, so a body field would mean five schema changes and one forgotten. The value sent is the language's English name, not `zh-Hant`, because the model answers in English language names, and a code or a word in the language being identified makes it parse instead of weigh.

A proper noun is never translated (`instructions.PROPER_NOUNS`), because translating it hands the reader a term they cannot search for. The rule is composed into both `chat_language_rule` and `artifact_language_rule` from one constant (invariant 13), and into the title prompt, which is a plain `dspy.Predict` and shares nothing else. It extends invariant 45's rule from the podcast to every artifact a reader might search from.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
