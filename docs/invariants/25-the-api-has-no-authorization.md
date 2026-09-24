# Invariant 25: The API has no authorization

**The API has no authorization of any kind, so `rlm-notebook serve` binds 127.0.0.1 and a non-loopback `--host` warns.**

Authentication is invariant 77: every request needs a token. That answers who may call the API, not what a caller may do. The token authenticates the application, not a person, so anyone who holds it is fully privileged over every notebook and over global settings. They can create, extend, query, rename and delete any notebook; delete a source, a note or the whole conversation; cancel any run; and change global state through `PUT /settings` (invariant 41). There is no notion of an owner. The API is meant for local or fully trusted networks, and it must not be exposed to an untrusted network without real per-user auth. `api.py`'s module docstring and `README.md` both say so; keep that warning.

## The binding is part of the access control

Because there is no authorization, the network binding is one of the two layers of access control, and it lives in code. `rlm-notebook serve` (`cli._cmd_serve`) binds `127.0.0.1` by default. That layer decides who can even try; the token (invariant 77) is the second layer, not a licence to drop the first.

A non-loopback `--host` is allowed, because a trusted network is a legitimate use and the CLI should not overrule an operator who knows their network. It is not allowed to be quiet: it prints what any reachable caller could do. This is invariant 9's reasoning applied to a setting whose consequences stay invisible until someone else finds the port.

`cli._is_loopback` treats the empty string as exposed. `bind("")` means `INADDR_ANY`, so `--host ""` is the most exposed value there is, and listing it as local would silence the warning exactly where it matters most. A hostname that cannot be classified without DNS is also treated as exposed: resolving it would make the warning depend on the resolver, and over-warning costs one line while under-warning costs this invariant.

The container binds `0.0.0.0` on purpose. Inside a container that is the only useful binding, and the container boundary makes it safe, which is why the `Dockerfile`'s documented run command publishes to `127.0.0.1:8000:8000` rather than `8000:8000`. The warning still prints on every start, and correctly so: a bare `-p 8000:8000` does expose the API on every host interface.

`GET /notebooks` makes every notebook enumerable, and `NotebookSummary.title` is a model-written summary of each notebook's subject (invariant 37). A token holder therefore sees a one-line summary of every notebook. That fits the accepted posture, but it is more than metadata.

---

Index: [`AGENTS.md`](../../AGENTS.md) · Current behaviour: [`CHANGELOG.md`](../../CHANGELOG.md)
