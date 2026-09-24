# Invariant 61: Cheap Predict callers read an excerpt

**The cheap `dspy.Predict` callers read `Corpus.excerpt`, never `blob()[:n]`; a prefix is source one, not the orbit.**

`naming.SuggestTitle` and `naming.SuggestLanguage` cannot read a large corpus (invariant 37), so they get a window. The blob concatenates sources in order, so with a 69,859-character first source and a 4,000-character budget, sources two to four were invisible, and a four-source orbit was titled by translating the first source's title. Language resolution read the same prefix, which is worse: an orbit whose later sources are in another language would resolve the wrong language, and invariant 39 then stores that guess and stops resolving.

`excerpt(n)` gives every source an equal share taken from its start, because a paper, page or report states its subject in its opening lines. The prompt matches: it asks what the whole collection is about, and names "translate the first source's title" as the failure to avoid.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
