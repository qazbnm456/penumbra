"""THE entry point for this slice: sources in, a grounded answer, a whole-orbit artifact, or a
podcast-style Audio Overview out — optionally as a multi-turn conversation. `serve` starts the
HTTP API and the web UI instead, which is a different execution model (invariant 21) reached
through the same command.

    penumbra ask "what does it say about X?" --source ./paper.pdf --source https://example.com
    penumbra guide summary --source ./paper.pdf
    penumbra audio --source ./paper.pdf

    # a persistent, continuing conversation / orbit:
    penumbra ask "what does it say about X?" --source ./paper.pdf --orbit mynb
    penumbra ask "and what about Y?" --orbit mynb
    penumbra guide faq --orbit mynb

Needs model credentials (`PN_*`, see `.env.example`) and a sandbox (`brew install deno`). Without
`--orbit`, every invocation ingests its `--source` list from scratch and runs exactly once —
nothing is persisted (the sibling projects' "offline unless you ask" shape). See AGENTS.md's Scope
note for what is not built yet.
"""

from __future__ import annotations

import argparse
import contextlib
import ipaddress
import logging
import os
import re
import signal
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from . import __version__, auth
from .audio import GeneratePodcastScript
from .citations import verify_citations
from .config import PenumbraConfig, output_language, setup, tts_voice_map
from .corpus import Corpus, CorpusTooLargeError
from .guide import GenerateFAQ, GenerateKeyInsight, GenerateSummary, GenerateTimeline
from .orbit import (
    append_sources,
    corpus_of,
    history_text,
    ingest_sources_for,
    load_or_create,
    mutate_orbit,
)
from .parsers.web import FetchError
from .schema import ChatTurn, Citation, Orbit
from .task import AnswerQuestion
from .tts import TTSError, get_tts_provider, spoken_script

_SPEAKER_LABELS = {"host_a": "Host A", "host_b": "Host B"}

#: `--out`'s default. Named so `_cmd_audio` can tell "the user chose this path" from "nobody did",
#: and correct the extension only in the latter case — a provider may emit WAV rather than MP3.
_DEFAULT_AUDIO_OUT = "podcast.mp3"

_CLI_DESCRIPTION = """\
Ask a question grounded in one or more sources, with citations you can verify — generate a
whole-orbit artifact (a summary, an FAQ, a timeline, or a single key insight) — or generate a
two-host podcast script + synthesized Audio Overview.

    penumbra ask "what does it say about X?" --source ./paper.pdf --source ./notes.txt
    penumbra ask "..." --source https://example.com/article
    penumbra guide summary --source ./paper.pdf
    penumbra guide faq --source ./paper.pdf
    penumbra audio --source ./paper.pdf --out episode.mp3

Add --orbit <id> to persist sources (and, for `ask`, history) across invocations:

    penumbra ask "what does it say about X?" --source ./paper.pdf --orbit mynb
    penumbra ask "and what about Y?" --orbit mynb    # no --source needed to continue
    penumbra guide timeline --orbit mynb
    penumbra audio --orbit mynb

`--source` accepts a path to a text file, a path to a PDF (scanned pages are OCR'd automatically),
or an http(s) URL. Needs PN_* model credentials (see .env.example) and a sandbox (brew install
deno) for a live run. `audio` additionally needs network access to the TTS provider (edge-tts by
default — free, no API key).
"""

#: `guide <kind>` -> the RLMTask that produces it. Shared by `build_parser` (as `choices`) and
#: `_cmd_guide` (to look up which task to run) so the two can never drift apart.
_GUIDE_TASKS: dict[str, type] = {
    "summary": GenerateSummary,
    "faq": GenerateFAQ,
    "timeline": GenerateTimeline,
    "insight": GenerateKeyInsight,
}


#: What a task is told when nothing better is known — a literal, never empty (see `api.py`'s copies
#: for why). The CLI has no `Accept-Language` and never runs the resolver, so it uses whatever
#: `PN_OUTPUT_LANGUAGE` says, else the language already resolved and PERSISTED on the orbit by
#: the API (the orbit is the unit both entry points share — invariant 20), else these.
_DEFAULT_ARTIFACT_LANGUAGE = "the language the sources are written in"
_DEFAULT_CHAT_LANGUAGE = "the language the question was asked in"


def _language_for(orbit, default: str) -> str:
    return output_language() or orbit.output_language or default


def _prepare(args) -> tuple[Orbit, Corpus] | None:
    """Load-or-create the orbit named by `args.orbit` (or an ephemeral one — see
    `orbit.load_or_create`), ingest any new `args.source` values, merge and PERSIST them, print
    prompt-injection flag warnings, and return `(orbit, corpus)` — shared by
    `_cmd_ask`/`_cmd_guide`/`_cmd_audio`, which all need identical sources-in-hand setup before
    running their own RLMTask. Returns `None` (an error already printed to stderr) if loading or
    ingestion failed, or if there are no sources at all; the caller should return 1 in that case.
    `api.py` uses the same `orbit.py` functions directly rather than this
    argparse-`Namespace`-shaped wrapper.

    **Ingestion is persisted HERE, before the model runs, rather than in a single save at the end
    of the command.** Two reasons, both consequences of the read-modify-write fix this slice
    landed: an RLM run is a minutes-long window in which another writer (a second CLI invocation,
    the API server) can legitimately touch the same orbit, and holding a snapshot across it is
    the defect itself; and a run that fails or is Ctrl+C'd partway no longer discards ingestion the
    user already paid for in OCR or network time.

    **Returns the orbit `mutate_orbit` produced, NOT the local snapshot** — `append_sources`
    renumbers ids against the freshly-loaded orbit, and handing the model a corpus built from
    the pre-merge objects would make it cite `s2` for a source persisted as `s4`. Every citation in
    the run would silently point at the wrong source."""
    try:
        orbit = load_or_create(args.orbit)
    except ValidationError as exc:
        # `save_orbit` writes atomically (temp file + os.replace), so this should only happen
        # to a file this tool never wrote — hand-edited, or corrupted by something outside this
        # process. Fail with a clear message rather than an uncaught pydantic traceback; there is
        # no automatic recovery (see orbit.save_orbit's docstring).
        print(
            f"orbits/{args.orbit}.json exists but is not a valid orbit file "
            f"({type(exc).__name__}) — fix or remove it by hand before continuing.",
            file=sys.stderr,
        )
        return None

    if not args.source and not orbit.sources:
        print(
            "no sources: pass --source at least once (or point --orbit at one that already "
            "has sources)",
            file=sys.stderr,
        )
        return None

    try:
        ingested = ingest_sources_for(orbit, args.source or [])
    except (FetchError, ValueError, OSError) as exc:
        print(f"could not ingest a source: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    # Nothing new to merge (the common "keep asking an existing orbit" case) takes neither the
    # lock nor a write: the snapshot above is already exactly as fresh as any reader ever gets.
    if ingested and args.orbit:
        orbit = mutate_orbit(
            args.orbit, lambda nb: append_sources(nb, ingested), create=True
        )
    elif ingested:
        # Ephemeral: nothing is persisted, so there's nothing to lock against and no fresh copy to
        # re-read — the same `append_sources` merge, applied to the in-memory orbit directly.
        append_sources(orbit, ingested)

    # Every source currently in the orbit, not just ones just added — a flag stays visible on
    # every subsequent turn, not only the turn that ingested the flagged source (AGENTS.md's
    # injection-flag invariant: additive metadata, surfaced for as long as it's part of the active
    # context, never a one-time notice).
    flagged = [s for s in orbit.sources if s.flags]
    if flagged:
        print("warning: possible prompt-injection patterns flagged (answer proceeds anyway):",
              file=sys.stderr)
        for s in flagged:
            print(f"  - {s.id} ({s.origin}): {', '.join(s.flags)}", file=sys.stderr)

    return orbit, corpus_of(orbit)


def _print_citations(citations: list[Citation], corpus: Corpus) -> None:
    """Print a blank-line-separated "Citations:" block, or nothing at all if `citations` is empty
    — the blank line is part of THIS function's output, not a separate `print()` each call site
    must remember, so "no citations" prints nothing rather than a stray trailing blank line (an
    independent review caught a version where every call site printed its own unconditional blank
    line first, so a citation-less answer ended in `"...text\\n\\n"` instead of `"...text\\n"`)."""
    verified = verify_citations(citations, corpus)
    if not verified:
        return
    print()
    print("Citations:")
    for v in verified:
        mark = "✓" if v.verified else "✗ UNVERIFIED"
        print(f"  [{mark}] {v.citation.source_id}|{v.citation.locator}: {v.citation.quote}")
        if not v.verified:
            print(f"        ({v.reason})")


@contextlib.contextmanager
def _traced(args, task: Any, config: Any, kwargs: dict) -> Iterator[None]:
    """Record this run to `--trace` if one was asked for, otherwise do nothing at all.

    **OPT-IN with an EXPLICIT path, and both halves are the design.** The API's `traces/` is a bare
    relative directory resolved against the server's working directory, swept by `prune_traces` at
    startup and after every run — neither of which a CLI has. Writing there by default would
    scatter a `traces/` directory into whatever directory the command was invoked from and leave
    files nobody ever collects, and a trace is the one artifact here that can hold FULL ingested
    source text (invariant 34). A path the caller named is a path the caller owns.

    The recorder is entered BEFORE the model call, so an unwritable path fails for free rather than
    after a run has been paid for — invariant 19's discipline, which is also why `_cmd_audio`
    resolves its TTS provider first. **A missing directory is not unwritable**: `TraceRecorder`
    calls `os.makedirs(..., exist_ok=True)`, so `--trace new/dir/run.jsonl` creates the path. That
    is a side effect of naming a path, not of running the command, and it is stated because a first
    reading of this assumed the opposite.
    """
    if not args.trace:
        yield
        return

    from rlm_harness.trace import TraceRecorder

    from .traces import run_meta

    dotted = f"{type(task).__module__}:{type(task).__name__}"
    run_id = f"cli-{uuid4().hex[:12]}"
    recorder = TraceRecorder(args.trace, run_id=run_id, meta=run_meta(dotted, config, kwargs))
    # ONLY `__enter__` is wrapped. A `try:` around the `yield` also catches an `OSError` raised by
    # the MODEL RUN — and `TimeoutError`, `BrokenPipeError` and `ConnectionResetError` are all
    # `OSError` subclasses, so a dying sandbox pipe or a timed-out call was reported as
    # "cannot write the trace to ...". The path was fine, the trace was on disk and complete with
    # `run_end ok=false` in it, and the operator re-ran and paid for the model call again.
    try:
        recorder.__enter__()
    except OSError as exc:
        raise SystemExit(f"cannot write the trace to {args.trace!r}: {exc}") from exc
    try:
        yield
    finally:
        recorder.__exit__(*sys.exc_info())


def _cmd_ask(args) -> int:
    prepared = _prepare(args)
    if prepared is None:
        return 1
    orbit, corpus = prepared

    config = setup(PenumbraConfig.from_env())
    try:
        blob = corpus.blob(max_chars=config.max_corpus_chars)
    except CorpusTooLargeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    task = AnswerQuestion()
    kwargs = {
        "sources": blob,
        "history": history_text(orbit),
        "question": args.question,
        "output_language": _language_for(orbit, _DEFAULT_CHAT_LANGUAGE),
    }
    with _traced(args, task, config, kwargs):
        result = task.run(**kwargs)

    print(result.text)
    _print_citations(result.citations, corpus)

    if args.orbit:
        # Appended to an orbit re-loaded fresh after the run, not to the snapshot `_prepare`
        # returned before it — see `orbit.mutate_orbit`. `_prepare` already persisted any
        # newly ingested sources, so this critical section carries only the turn.
        turn = ChatTurn(question=args.question, answer=result)
        mutate_orbit(args.orbit, lambda nb: nb.turns.append(turn), create=True)
    return 0


def _cmd_guide(args) -> int:
    prepared = _prepare(args)
    if prepared is None:
        return 1
    _orbit, corpus = prepared  # guide/audio persist nothing; only the corpus is used

    config = setup(PenumbraConfig.from_env())
    try:
        blob = corpus.blob(max_chars=config.max_corpus_chars)
    except CorpusTooLargeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    task = _GUIDE_TASKS[args.kind]()
    kwargs = {
        "sources": blob,
        "output_language": _language_for(_orbit, _DEFAULT_ARTIFACT_LANGUAGE),
    }
    with _traced(args, task, config, kwargs):
        result = task.run(**kwargs)

    if args.kind == "summary":
        print(result.text)
        _print_citations(result.citations, corpus)
    elif args.kind == "faq":
        if not result.items:
            # A source with nothing FAQ-worthy is a legitimate answer this task is explicitly
            # instructed to give (guide.py) — an empty list must not look identical to "this
            # silently produced no output," which an independent review found it did.
            print("(no FAQ items — the sources didn't raise anything worth asking)")
        for i, item in enumerate(result.items, start=1):
            print(f"Q{i}: {item.question}\nA{i}: {item.answer}")
            _print_citations(item.citations, corpus)
            print()
    elif args.kind == "timeline":
        if not result.events:
            print("(no timeline — the sources don't describe a sequence of events)")
        for event in result.events:
            print(f"[{event.when}] {event.description}")
            _print_citations(event.citations, corpus)
            print()
    else:  # "insight"
        print(result.text)
        _print_citations(result.citations, corpus)

    # Guide artifacts aren't cached onto the orbit or made citable as sources yet (deferred —
    # see CHANGELOG), and `_prepare` has already persisted any --source values just ingested, so
    # there is nothing left for this command to write. The trailing `save_orbit` that used to
    # sit here existed only for that ingestion; keeping it would be a second write path holding a
    # pre-run snapshot — the exact shape this slice removed.
    return 0


def _cmd_audio(args) -> int:
    prepared = _prepare(args)
    if prepared is None:
        return 1
    _orbit, corpus = prepared  # guide/audio persist nothing; only the corpus is used

    config = setup(PenumbraConfig.from_env())
    try:
        blob = corpus.blob(max_chars=config.max_corpus_chars)
    except CorpusTooLargeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Resolve the TTS provider BEFORE the (potentially expensive) script-generation model call,
    # not after — found by an independent review: a mistyped PN_TTS_PROVIDER used to only surface
    # as an uncaught TTSError once the model had already run and the transcript had already
    # printed, wasting that model call on a config mistake that was knowable up front.
    try:
        provider = get_tts_provider(config.tts_provider)
    except TTSError as exc:
        print(f"cannot generate audio: {exc}", file=sys.stderr)
        return 1

    language = _language_for(_orbit, _DEFAULT_ARTIFACT_LANGUAGE)
    # BEFORE the (expensive) script run: a language this provider has no id for, or a voice it does
    # not know, can never produce audio (invariant 19, extended from the provider NAME to its own
    # inputs). `get_tts_provider` above already covers a typo'd PN_TTS_PROVIDER.
    voice_map = tts_voice_map(config, language, provider)
    try:
        provider.validate(language, voice_map)
    except TTSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    task = GeneratePodcastScript()
    kwargs = {"sources": blob, "output_language": language, "target_length": args.length}
    with _traced(args, task, config, kwargs):
        script = task.run(**kwargs)

    if not script.utterances:
        # A source with nothing worth discussing is a legitimate answer (audio.py's instructions
        # explicitly allow it) — same "don't print silence and look broken" fix guide.py's empty
        # FAQ/timeline needed.
        print("(no podcast script — the sources didn't produce enough to discuss)")
    else:
        for utterance in script.utterances:
            print(f"{_SPEAKER_LABELS[utterance.speaker]}: {utterance.text}")
            _print_citations(utterance.citations, corpus)
            print()

        out_path = Path(args.out)
        # `--out` defaults to `podcast.mp3`, but a provider may emit another format (the local provider writes
        # WAV). Correct the extension rather than writing WAV bytes into a file named `.mp3` —
        # unless the user named the path themselves, in which case their choice stands.
        if args.out == _DEFAULT_AUDIO_OUT and out_path.suffix != provider.suffix:
            out_path = out_path.with_suffix(provider.suffix)
        try:
            provider.synthesize(spoken_script(script), voice_map, out_path, language)
        except TTSError as exc:
            # The transcript above already printed successfully — a synthesis failure (network,
            # bad voice config, an --out path whose parent doesn't exist — see tts.py's own fix)
            # must not make it look like NOTHING happened; the script is still useful on its own
            # even without audio.
            print(f"transcript generated above, but audio synthesis failed: {exc}", file=sys.stderr)
            return 1
        print(f"-> {out_path}")

    # Nothing to persist here either — see `_cmd_guide`'s note above.
    return 0


def _add_source_and_orbit_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--source", action="append", dest="source",
        help="a text file path, a PDF path, or an http(s) URL — repeatable. Required unless "
             "--orbit points at one that already has sources",
    )
    sub.add_argument(
        "--orbit", default=None,
        help="persist sources under this id across invocations (default: ephemeral, nothing is "
             "saved)",
    )
    sub.add_argument(
        "--trace", default=None, metavar="PATH",
        help="write this run's reasoning trace to PATH (JSONL). Off by default; the API writes "
             "traces of its own and prunes them, this one is yours to keep or delete",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="penumbra",
        description=_CLI_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="ask one question grounded in one or more sources")
    a.add_argument("question", help="the question to ask")
    _add_source_and_orbit_args(a)
    a.set_defaults(func=_cmd_ask)

    g = sub.add_parser("guide", help="generate a whole-orbit artifact from one or more sources")
    g.add_argument("kind", choices=sorted(_GUIDE_TASKS), help="which artifact to generate")
    _add_source_and_orbit_args(g)
    g.set_defaults(func=_cmd_guide)

    au = sub.add_parser(
        "audio", help="generate a two-host podcast script + synthesized audio (Audio Overview)"
    )
    _add_source_and_orbit_args(au)
    au.add_argument(
        "--length", choices=("short", "default", "long"), default="default",
        help="how long an episode to aim for: short (~3-5 min), default (~8-12), long (~18-25). "
             "The web UI offers the same three; both feed the task's `target_length` field",
    )
    au.add_argument(
        "--out", default=_DEFAULT_AUDIO_OUT,
        help="output audio file path (default: podcast.mp3). Only written if the script is "
             "non-empty and synthesis succeeds; the transcript is always printed regardless",
    )
    au.set_defaults(func=_cmd_audio)

    s = sub.add_parser("serve", help="run the HTTP API and the web UI (needs the `api` extra)")
    s.add_argument(
        "--host", default="127.0.0.1",
        help="interface to bind (default: 127.0.0.1, loopback only). Requests need the API "
             "token (AGENTS.md invariant 77) but there is no authorization behind it (25), so any "
             "other value is a deliberate decision to let everyone who obtains that token read, "
             "rewrite and delete every orbit on this machine",
    )
    s.add_argument(
        "--port", type=_port, default=8000,
        help="port to bind (default: 8000)",
    )
    s.add_argument(
        "--reload", action="store_true",
        help="restart when the files under the CURRENT DIRECTORY change. Only useful from a source "
             "checkout: uvicorn watches the working directory, never the installed package, so on "
             "a `uv tool install`/`pipx`/container install this watches your orbits and never "
             "the code. Without `uvicorn[standard]`'s watchfiles it also degrades to polling every "
             "file under that directory",
    )
    s.set_defaults(func=_cmd_serve)

    return p


#: Whether a host is a promise to stay on this machine. Parsed as an ADDRESS rather than compared
#: as a string, so `::1`, `127.0.0.2` and an IPv4-mapped loopback all read as loopback without
#: anyone enumerating spellings.
#:
#: It decides whether to PRINT A WARNING, so it is allowed to be wrong in one direction only. It
#: over-warns on forms getaddrinfo accepts and `ipaddress` does not (`[::1]`, `127.1`, `LOCALHOST`,
#: `0177.0.0.1`): a spurious warning on a genuinely local bind costs a line. It under-warns in
#: exactly ONE case, stated rather than hidden: `"localhost"` is trusted unconditionally, so an
#: `/etc/hosts` entry pointing it at a LAN address binds non-loopback in silence. Resolving it here
#: would make the warning depend on the resolver, which is the worse trade.
def _port(value: str) -> int:
    """A port argparse rejects cleanly rather than letting `bind()` raise.

    `type=int` alone accepts 99999, and `socket.bind` then raises `OverflowError` — which is NOT an
    `OSError`, so uvicorn's own `except OSError: sys.exit(STARTUP_FAILURE)` never catches it and the
    user gets a twelve-line traceback for a typo.
    """
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 0-65535, not {port}")
    return port


def _is_loopback(host: str) -> bool:
    # NOT the empty string, which is the trap: `bind("")` is `INADDR_ANY`, so `--host ""` is the
    # most exposed value there is. An earlier draft of this function listed it beside "localhost"
    # and would have suppressed the warning on exactly the binding that most needs it.
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A hostname we cannot classify without resolving it. Resolving here would make the warning
        # depend on DNS, so treat it as exposed: over-warning costs a line, under-warning costs
        # invariant 25.
        return False


class RedactToken(logging.Filter):
    """Blank the API token out of uvicorn's access log.

    The browser cannot put a header on an `EventSource` or an `<audio src>`, so those requests carry
    the token as `?token=` (invariant 77), and uvicorn logged every such URL in full. The desktop
    app writes that log to a file its File menu offers to show, which is exactly the file somebody
    attaches to a bug report.
    """

    _TOKEN = re.compile(r"(token=)[^&\s\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                self._TOKEN.sub(r"\1[redacted]", a) if isinstance(a, str) else a for a in record.args
            )
        return True


def _log_config() -> dict | None:
    """uvicorn's own logging configuration, with `RedactToken` on the access handler. `None` (keep
    uvicorn's default) when that configuration cannot be found, e.g. under a stub `uvicorn`."""
    import copy

    try:
        from uvicorn.config import LOGGING_CONFIG
    except ImportError:
        return None

    config = copy.deepcopy(LOGGING_CONFIG)
    config.setdefault("filters", {})["redact_token"] = {"()": "penumbra.cli.RedactToken"}
    config["handlers"]["access"].setdefault("filters", []).append("redact_token")
    return config


def _exit_with_parent_if_asked() -> None:
    """Shut down when the process that started us is gone, if it asked for that.

    The desktop shell sets `PN_EXIT_WITH_PARENT=1` and keeps our stdin open as a pipe. A shell that
    QUITS stops the server itself, but one that is killed, crashes or is force-quit runs no
    teardown at all, and the server it started kept running with nobody left to stop it: measured,
    a SIGTERM to the app left `serve` alive. The pipe closes however the parent dies, on every
    platform, so reading it to EOF is the one signal that cannot be missed. On EOF this takes the
    same graceful path as Ctrl-C, which also ends every in-flight run (invariant 22).
    """
    if os.environ.get("PN_EXIT_WITH_PARENT") != "1":
        return

    def _watch() -> None:
        with contextlib.suppress(Exception):
            while sys.stdin.buffer.read(65536):
                pass
        signal.raise_signal(signal.SIGTERM if hasattr(signal, "SIGTERM") else signal.SIGINT)

    threading.Thread(target=_watch, name="exit-with-parent", daemon=True).start()


def _cmd_serve(args: argparse.Namespace) -> int:
    """Run the API and the web UI it serves.

    The API is reachable ONLY from this machine by default, and that default is the point. Every
    request needs the token minted below (invariant 77), but there is no authorization behind it
    (invariant 25): any caller HOLDING IT can create, rename, query, cancel, irreversibly delete a
    source from, and read the FULL TEXT and reasoning traces of any orbit, and can change global
    settings for orbits they never named. The token and the binding are the two layers of access
    control, so both belong in the code rather than only in a warning in `README.md`.

    A non-loopback `--host` is allowed, because a genuinely trusted network is a use the README
    already sanctions, and refusing it would be this command deciding something the operator knows
    better. It is not allowed to be QUIET, though: the same reasoning invariant 9 uses for
    `PN_INTERPRETER`, where an operator who set the value believes something that has to be true.

    Deliberately does NOT read `PenumbraConfig.from_env`: that raises `SystemExit` whenever
    `PN_MAIN_MODEL` is unset, and a server with no model configured must still start, or the
    settings page invariant 41 built for exactly that operator is unreachable.
    """
    try:
        import uvicorn
    except ImportError:
        print(
            "penumbra serve needs the `api` extra (fastapi + uvicorn).\n"
            "  from a source checkout:  uv sync --extra api\n"
            "  otherwise, reinstall with the extra, e.g.\n"
            "      uv tool install 'penumbra[api] @ git+"
            "https://github.com/qazbnm456/penumbra'",
            file=sys.stderr,
        )
        return 2

    # Minted BEFORE uvicorn starts and put into the environment, not passed as an argument, for a
    # specific reason: `uvicorn.run` is given the app as an IMPORT STRING, so under `--reload` the
    # app is constructed in a child process. The environment is what both processes share, and it
    # is also the channel the desktop shell will use to inject a token it minted itself
    # (`auth.api_token`). Setting it here means `api._announce_minted_token` stays quiet and this
    # function owns the one, better-worded announcement.
    minted = auth.token_is_minted()
    if minted:
        os.environ["PN_API_TOKEN"] = auth.api_token()

    if not _is_loopback(args.host):
        print(
            f"WARNING: binding {args.host}, not loopback. Every request needs the API token below, "
            "but that token is the ONLY thing protecting this server: there is no authorization of "
            "any kind (invariant 25), so anyone who obtains it can read every orbit's full "
            "source text and reasoning traces, delete sources, and change settings for orbits "
            "they never named. It also travels in cleartext over plain HTTP, and in a query string "
            "for the stream and audio endpoints, where proxies and access logs can record it. "
            "Only do this on a network you fully trust.",
            file=sys.stderr,
        )
    # `orbits/`, `traces/` and `horizon/` are relative paths resolved against the working
    # directory (invariant 34), so where you START this decides where your orbits live. (A
    # generated episode lives at `orbits/audio/`, inside the first of them, not beside it.) That is
    # the one fact worth printing, and it is printed to STDERR: stdout is block-buffered off a TTY,
    # so on the containerised path this line never reached `docker logs` at all — the path a
    # reader most needs when their orbits are inside a container that is about to be removed.
    #
    # The URL is NOT printed here. It used to be, one line BEFORE the bind, so an occupied port
    # announced an address it then failed to serve. uvicorn prints it after binding, which is the
    # only point at which it is true.
    print(
        f"penumbra: orbits, traces, audio and the Horizon under {Path.cwd()}", file=sys.stderr
    )
    # The TOKEN is printed here; the URL still is not. That split is deliberate and keeps the
    # reasoning above intact — a token is not an address, so printing it before the bind cannot
    # announce something this process then fails to serve. uvicorn prints the address once it is
    # true, and the two are combined by whoever reads them.
    if minted:
        print(
            f"penumbra: API token (every request needs it): {auth.api_token()}\n"
            f"  in a browser, open the address uvicorn prints below with "
            f"`?{auth.QUERY_PARAM}={auth.api_token()}` appended — the page stores it and strips it "
            "from the address bar.\n"
            "  elsewhere, send `Authorization: Bearer <token>`.\n"
            "  set PN_API_TOKEN to choose the token yourself instead.",
            file=sys.stderr,
        )
    else:
        print(
            "penumbra: using the API token from PN_API_TOKEN; every request needs it.",
            file=sys.stderr,
        )
    #: **Without a graceful-shutdown timeout, this server cannot be quit while a run is in flight.**
    #: `Server.shutdown()` ends in `await server.wait_closed()`, and since Python 3.12 that waits for
    #: every active connection handler — `force_exit` does not break out of it, so a second Ctrl-C
    #: does not help either. An independent review reproduced it against the shipped binary:
    #: SIGTERM, then SIGINT twice, then a third and fourth, all with the listener already closed and
    #: the process still up; the only remaining exit was SIGKILL, which reparents the worker and its
    #: Deno grandchild to init, still billing to their own backstop (1500s on the API path, 9000s on
    #: the subscription one).
    #:
    #: It also made the previous round's fix DEAD CODE on this path: `uvicorn` guards
    #: `lifespan.shutdown()` with `if not self.force_exit`, so a forced quit skips `_lifespan`'s
    #: cancel loop — and every entry in `_ACTIVE_RUNS` belongs to an in-flight request whose
    #: `finally` clears it, so by the time that loop can run the map is empty by construction. The
    #: test written for it put `FakeRun`s into the map by hand and could see neither fact.
    #:
    #: Three seconds: long enough for a request that is genuinely about to finish, short enough that
    #: Ctrl-C feels like quitting. Verified with the same probe — one SIGINT, server gone, worker and
    #: grandchild gone with it.
    #: SIGHUP gets its own handler because uvicorn installs none, so closing the terminal took the
    #: default action and tore the process down with no shutdown at all. It RE-RAISES AS SIGTERM,
    #: which uvicorn does capture while serving: the first version raised `KeyboardInterrupt` from
    #: the handler, which passed its unit test and, run live, blew up the event loop mid-`await` —
    #: a traceback, no "Shutting down", no lifespan teardown. SIGTERM takes the same bounded,
    #: graceful path as Ctrl-C.
    def _hangup(_signum, _frame):
        signal.raise_signal(signal.SIGTERM)

    _exit_with_parent_if_asked()
    # Windows has no SIGHUP at all, and `signal.SIGHUP` raised AttributeError there before uvicorn
    # ever started. The desktop shell stops the server itself on every platform.
    if hasattr(signal, "SIGHUP"):
        with contextlib.suppress(ValueError):  # not the main thread (a test, an embedded host)
            signal.signal(signal.SIGHUP, _hangup)
    uvicorn.run(
        "penumbra.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        timeout_graceful_shutdown=3,
        **({"log_config": log_config} if (log_config := _log_config()) else {}),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _report_legacy_state()
    return args.func(args)


def _report_legacy_state() -> None:
    """Move pre-rename data folders into place and name any `RN_*` variable still set (`legacy`)."""
    from . import legacy

    for old, new in legacy.migrate_data_dirs():
        print(f"penumbra: moved {old}/ to {new}/ (renamed from rlm-notebook)", file=sys.stderr)
    for old, new in legacy.stranded_dirs():
        print(
            f"penumbra: left {old}/ in place because {new}/ already exists; nothing reads {old}/. "
            f"Move what you need from it into {new}/ by hand.",
            file=sys.stderr,
        )
    stale = legacy.legacy_env_names()
    if stale:
        renamed = ", ".join(f"{name} -> PN_{name[3:]}" for name in stale)
        print(
            f"penumbra: ignoring {len(stale)} old setting(s); rename them: {renamed}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
