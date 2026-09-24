# Invariant 27: Orbit lookup catches both error types

**Every endpoint that resolves an orbit by id catches both `pydantic.ValidationError` (a corrupted orbit file, 409) and `ValueError` (an id `orbit.slug` reduces to nothing, 400).**

Without the second handler, an unhandled `ValueError` escapes as a raw 500. Since invariant 10, an id such as `"!!!"` is an ordinary orbit, so only an empty or whitespace-only id still takes this path. `cancel` never loads an orbit and is unaffected.

Path-traversal payloads do not reach this code, because Starlette's default path converter will not match a literal `/` inside one `{orbit_id}` segment. That is a framework default, not this project's code, so re-check it if the route ever changes shape.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
