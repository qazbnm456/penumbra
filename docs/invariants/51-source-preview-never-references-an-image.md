# Invariant 51: Source previews never reference an image

**`Source.preview` is display-only page metadata, scraped from HTML already in hand, and it never references an image.**

`parsers/web.extract_preview` reads Open Graph, Twitter, `description` and `<title>` tags from the same HTML `parse_web` already fetched, so there is still one host-side request per source (invariant 1). The corpus is built from `blocks` alone, so a page's own `<meta>` tags affect only how its row looks in the Sources list, never what the model reads, the same trust level as `origin`, and it is rendered with `textContent` for the same reason.

`og:image` is deliberately absent, although adding it looks like an obvious improvement. Rendering it would make the reader's browser fetch a URL chosen by the page author, handing that third party the reader's IP address and a request to log, so every pasted link would become a beacon in exchange for a thumbnail. A test pins its absence. Parsing uses regular expressions rather than an HTML parser to add no dependency to an ingestion path where `trafilatura` does the real work; a malformed match is a cosmetic miss, never a hazard.

Every quantifier in those patterns is bounded, and the input is limited to the `<head>`. With an unbounded `[^>]*?`, a page full of unclosed `<meta` tags backtracks catastrophically, and `re` does not release the GIL, so running it on a thread does not protect the event loop. On an API where any token holder can paste any URL, that would freeze the whole server with one request.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
