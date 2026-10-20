# Invariant 82: Local relations are downloaded on a press, pinned, and treated as a weak signal

**The embedding model behind local relations (`vectors.py`) is downloaded only when the reader presses Download, from one pinned revision checked against its SHA-256 before use, and similarity is drawn only above a high threshold between mutual near neighbours, never as a substitute for relations a summary names.**

## Why a download and not a dependency

The model is about 130 MB. Bundling it would make every install carry it, including every reader who never turns relations on, so the feature costs nothing until it is asked for. The settings page states the size beside the button, the download shows progress and can be stopped, and removing the feature deletes the model and every stored vector. It is not a model call and costs no money, so invariant 80's spend rules do not apply, but invariant 47's do: it is a long action the reader started and can see and stop.

The files come from a fixed address on the host, like a package, never from anything a capture or a model supplied. That is why this fetch is outside invariants 1 and 2, which are about fetches a source can steer. The model is the kit's pinned `DEFAULT_MODEL` (`vectors.MODEL`), fetched by its `download_model`: each file is verified against its published size and SHA-256, and a file that fails is deleted and nothing is installed. A new revision is a deliberate change in the kit, with new hashes. A download made before relations moved to the kit stays valid, because it is in the same folder and its marker names the same revision.

## Why the signal is kept weak

Measured on `multilingual-e5-small`, cosine similarity sits in a narrow band, roughly 0.75 to 0.95, and leans towards text in the same language: a Chinese note on coffee scored closer to a Chinese note on sleep (0.854) than to an English one on coffee (0.817). Unrelated Chinese pairs averaged 0.856 and reached 0.892, above the 0.86 that separates English, so in a Chinese Horizon one 0.86 threshold drew 14 wrong links beside 8 right ones, while 0.90 drew 7 right and none wrong. An eleven-character note scored 0.875 against an unrelated paper, because a vector of almost nothing sits near everything. So:

- A link is drawn only at 0.90 or above when both captures are mostly Chinese, Japanese or Korean, and at 0.86 or above for every other pair, a Chinese and an English capture included. Do not fold the two back into one number: 0.86 was that number, and it is what drew the wrong links.
- A link needs each capture to be among the other's four nearest, counted among the captures being compared (an orbit's graph, or the filed captures a suggestion looks at), and computed exactly. The `sqlite-vec` index this replaced searched the whole Horizon and then kept the captures in play, so a crowd outside an orbit could take a neighbour's place; a small orbit now draws the links its own captures support.
- Text that weighs under 40 characters is not compared at all, each Chinese, Japanese or Korean character counting three, since one carries about as much as a short English word.
- A similar pair is a dashed line between two captures, visibly different from an entity relation, and a similarity-based filing suggestion ranks below any suggestion by shared entities.
- A missing link means nothing.

## The index is derived, and it is the kit's

The vectors are the kit's `MemoryVectors` over the Horizon's memory store, in its own file beside it (`memory.db.vectors.db`): plain float32 rows compared with numpy, each keeping the hash of the exact text it embedded (title, summary and the head of the capture's text), so a rename or a new summary re-embeds that capture at the next sync, and a text too short to compare is remembered as skipped until it changes. A capture's purge erases its vector, and clearing the Horizon deletes the file with the store. Everything can be rebuilt from the captures, which is why the first start after this moved re-embeds every capture once, in the background.

The worker writes a batch only after embedding it, so turning relations off and clearing everything first wait for its thread to end (`api._halt_vector_worker`), keep it in its place until it has, so a retry waits for the same thread, let no new worker start until the file is gone, and answer 409 if a batch is still running after the wait: a write into a file being deleted fails, and after a clear it would put a vanished capture's vector into the new file. The lazy-numpy trap that once made every embedding in the server fail (dspy's proxy reaching `onnxruntime` through the C API) is handled where the model is loaded, in the kit.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
