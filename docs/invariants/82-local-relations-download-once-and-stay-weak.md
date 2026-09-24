# Invariant 82: Local relations are downloaded on a press, pinned, and treated as a weak signal

**The embedding model behind local relations (`vectors.py`) is downloaded only when the reader presses Download, from one pinned revision checked against its SHA-256 before use, and similarity is drawn only above a high threshold between mutual near neighbours, never as a substitute for relations a summary names.**

## Why a download and not a dependency

The model is about 130 MB. Bundling it would make every install carry it, including every reader who never turns relations on, so the feature costs nothing until it is asked for. The settings page states the size beside the button, the download shows progress and can be stopped, and removing the feature deletes the model and every stored vector. It is not a model call and costs no money, so invariant 80's spend rules do not apply, but invariant 47's do: it is a long action the reader started and can see and stop.

The files come from a fixed address on the host, like a package, never from anything a capture or a model supplied. That is why this fetch is outside invariants 1 and 2, which are about fetches a source can steer. Each file is pinned to one upstream revision and verified against its published SHA-256; a file that fails is deleted and nothing is installed. A new revision is a deliberate change to `vectors.MODEL_FILES`, with new hashes.

## Why the signal is kept weak

Measured on `multilingual-e5-small`, cosine similarity sits in a narrow band, roughly 0.75 to 0.92, and leans towards text in the same language: a Chinese note on coffee scored closer to a Chinese note on sleep (0.854) than to an English one on coffee (0.817). An eleven-character note scored 0.875 against an unrelated paper, because a vector of almost nothing sits near everything. So:

- A link is drawn only at 0.86 or above, and only when each capture is among the other's four nearest.
- Text shorter than 40 characters is not compared at all.
- A similar pair is a dashed line between two captures, visibly different from an entity relation, and a similarity-based filing suggestion ranks below any suggestion by shared entities.
- A missing link means nothing.

## The index is derived, and it has no trigger

Vectors live in the Horizon's own database as a `sqlite-vec` table beside a `vector_rows` mapping that cascades on node deletion. The vector table is readable only by a connection that loads the extension, which is why it carries no trigger: a trigger on it would make every node deletion through an ordinary connection fail with "no such module". `sync` sweeps vectors whose mapping row is gone instead. Everything can be rebuilt from the captures.

## A trap worth knowing

dspy, which the API imports, replaces `numpy` in `sys.modules` with a lazy proxy. `onnxruntime`'s compiled module imports numpy through the C API, receives the proxy and fails with "import numpy failed", which made every embedding in the server fail while every test passed. `vectors._real_numpy` touches one attribute to swap the real module in before `onnxruntime` is imported.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
