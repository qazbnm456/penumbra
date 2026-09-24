# Invariant 48: The interface language is separate from the output language

**The interface language (`web/i18n.js`) is a browser preference, kept separate from the output language (invariant 39), which is a server setting.**

One decides what the buttons say, the other what the model writes. A reader in Taiwan may want a Chinese interface over English papers, and merging the two would make that impossible to express. The interface language lives in `localStorage`, and the settings page shows both on separate rows.

They are separate but not isolated: the interface language is sent with every request and is one of the signals used to choose the output language (invariant 69). An explicit output language still wins outright.

`STRINGS.en` is empty on purpose. English is whatever `index.html` and `app.js` already say: static markup carries `data-i18n`, `-title`, `-placeholder` and `-tip` attributes with its own text as the fallback, and every `t(key, fallback)` call passes its English at the call site. There is no English table to drift out of sync. One tripwire fails the build on a bare `t("key")`, which would show the key to an English reader, and another on a key that is used but not translated, because `t()` falls back silently and the interface would stay half-English.

`zh-CN` and `zh-Hans` deliberately do not resolve to the Traditional table, because Traditional text is worse for a Simplified reader than English. Detection runs from `localStorage` to `navigator.languages` to English.

A language change re-renders instead of threading a language argument through every renderer: `setUiLang` re-applies the static markup and dispatches `ui-lang-changed`, so a renderer added later is translated without anyone remembering to subscribe. The re-render changes labels only. It is flagged as a relabel, so the Studio does not treat it as a change of sources and discard the generated guides.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
