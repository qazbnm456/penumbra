"""Assemble the runtime the desktop app ships: a relocatable Python with penumbra installed in
it, plus the deno binary every live run needs.

    uv run python desktop/scripts/build_runtime.py        # then: cd desktop/src-tauri && cargo tauri build

Output goes to `desktop/src-tauri/runtime/`, which `tauri.conf.json` bundles as a resource:

    runtime/python/   bin/python3 (macOS, Linux) or python.exe (Windows), penumbra in site-packages
    runtime/deno/     deno or deno.exe

**Why a relocatable interpreter and not PyInstaller.** dspy and litellm import a great deal by
name at run time, and a freezer that follows static imports misses them in ways that only show
up on a user's first question. uv's managed interpreters are python-build-standalone builds that
run from any directory, so the app ships an ordinary Python with an ordinary `site-packages`, and
the server starts exactly as `python -m penumbra.cli serve` does in a checkout.

**Build on the platform you ship to.** Wheels such as numpy, onnxruntime and pypdfium2 are
platform-specific, so each OS and architecture is built on its own machine (the CI workflow runs
one job per target). The script refuses a target other than the host's rather than producing an
app that fails at import.

Tesseract is not bundled: RapidOCR is the primary OCR engine and ships as a normal dependency, and
tesseract is only the fallback (invariant 7).
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "desktop" / "src-tauri" / "runtime"
#: The container pins the same version (Dockerfile `DENO_VERSION`), so a desktop run and a
#: container run execute the sandbox on the same deno.
DENO_VERSION = "2.1.4"
PYTHON_VERSION = "3.13"
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
}


def host_target() -> str:
    machine = platform.machine().lower()
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64", "amd64": "x86_64"}.get(machine)
    if arch is None:
        raise SystemExit(f"unsupported architecture: {machine}")
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if sys.platform.startswith("linux"):
        return f"{arch}-unknown-linux-gnu"
    if sys.platform == "win32":
        return f"{arch}-pc-windows-msvc"
    raise SystemExit(f"unsupported platform: {sys.platform}")


def run(*argv: str, env: dict | None = None) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True, env=env)


def install_python(dest: Path) -> Path:
    """A python-build-standalone interpreter via uv, copied into `dest` with symlinks resolved so
    the bundler never meets a link it might not carry across."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "UV_PYTHON_INSTALL_DIR": tmp}
        run("uv", "python", "install", PYTHON_VERSION, env=env)
        found = sorted(p for p in Path(tmp).iterdir() if p.is_dir() and p.name.startswith("cpython-"))
        if not found:
            raise SystemExit("uv installed no interpreter")
        shutil.copytree(found[-1], dest, symlinks=False)
    python = dest / ("python.exe" if sys.platform == "win32" else "bin/python3")
    if not python.exists():
        raise SystemExit(f"no interpreter at {python}")
    # uv marks its managed interpreters EXTERNALLY-MANAGED so nobody pip-installs into them by
    # accident. This one exists to be installed into.
    for marker in dest.rglob("EXTERNALLY-MANAGED"):
        marker.unlink()
    return python


def install_app(python: Path, home: Path) -> None:
    run("uv", "pip", "install", "--python", str(python), "--no-cache", f"{ROOT}[api]")
    # Precompiled bytecode: the first launch imports numpy, onnxruntime and dspy, and compiling
    # them on that launch is seconds the reader spends watching a splash screen. UNCHECKED hashes,
    # not the default timestamps: a .deb, an AppImage or an MSI install does not keep source
    # mtimes, so timestamp-checked .pyc files would all look stale and every launch would
    # recompile in memory (the install directory is read-only, and the shell sets
    # PYTHONDONTWRITEBYTECODE besides).
    run(
        str(python), "-m", "compileall", "-q", "-j", "0",
        "--invalidation-mode", "unchecked-hash", str(home),
    )


def install_deno(dest: Path, target: str) -> None:
    url = f"https://github.com/denoland/deno/releases/download/v{DENO_VERSION}/deno-{target}.zip"
    print("+ fetch", url, flush=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    dest.mkdir(parents=True, exist_ok=True)
    archive.extractall(dest)
    for binary in dest.iterdir():
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def adhoc_sign(root: Path) -> None:
    """macOS on Apple silicon runs no unsigned code, and a bundle's nested binaries are checked
    when the app launches them. Every Mach-O file gets an ad-hoc signature (`-`), which is what the
    app itself carries until there is a Developer ID to sign with."""
    machos = []
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as fh:
                if fh.read(4) in MACHO_MAGIC:
                    machos.append(str(path))
    print(f"+ codesign -s - ({len(machos)} Mach-O files)", flush=True)
    for start in range(0, len(machos), 200):
        run("codesign", "--force", "--sign", "-", *machos[start : start + 200])


def size_of(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", default=host_target(), help="Rust target triple (default: this machine)")
    args = parser.parse_args()
    if args.target != host_target():
        raise SystemExit(
            f"refusing to build {args.target} on {host_target()}: its wheels would be the wrong platform"
        )

    for child in OUT.iterdir() if OUT.exists() else []:
        if child.name != ".keep":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    python = install_python(OUT / "python")
    install_app(python, OUT / "python")
    install_deno(OUT / "deno", args.target)
    if sys.platform == "darwin":
        adhoc_sign(OUT)

    run(str(python), "-c", "import penumbra.api, penumbra.cli; print('penumbra imports ok')")
    print(f"runtime for {args.target}: {size_of(OUT) / 1e6:.0f} MB in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
