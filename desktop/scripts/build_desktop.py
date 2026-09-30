"""Build the desktop app end to end, keep the whole log, and retry a failed disk image once.

    uv run python desktop/scripts/build_desktop.py                  # runtime, then the app and installers
    uv run python desktop/scripts/build_desktop.py --skip-runtime   # reuse desktop/src-tauri/runtime/

It runs `build_runtime.py`, then `cargo tauri build -vv` in `desktop/src-tauri`, with every line
written to `desktop/src-tauri/target/build-logs/<time>.log` as well as the terminal.

**Why a wrapper.** On macOS the disk-image step (`bundle_dmg.sh`, from create-dmg) failed now and
then while the `.app` beside it was fine, and Tauri's default output records only that the script
failed. Nine runs with full output, including runs under heavy load, never reproduced it, so this
keeps the full output of every build and gives the step one more try: when the build fails in that
step, it detaches any disk image the step left mounted, deletes its `rw.*.dmg`, and runs
`cargo tauri bundle --bundles app,dmg -vv` again. `app` is named on purpose, because
`tauri bundle` deletes any bundle it was not asked for, the `.app` included.

It ends by checking that the bundled Python imports the modules a live run needs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "desktop" / "src-tauri"
BUNDLE = SHELL / "target" / "release" / "bundle"
LOGS = SHELL / "target" / "build-logs"
#: How many more times the disk-image step is tried after it fails once.
DMG_RETRIES = 1


def dmg_step_failed(log_text: str) -> bool:
    """Whether a Tauri build failed in the disk-image step, rather than anywhere else."""
    if "error running bundle_dmg.sh" in log_text:
        return True
    return "failed to run" in log_text and "bundle_dmg.sh" in log_text


def dmg_failure_reason(log_text: str) -> str:
    """The create-dmg lines that say where it stopped, for the report."""
    markers = ("Failed running AppleScript", "Resource busy", "Wait a moment", "hdiutil:", "exit code",
               "Unmounting disk image", "Running AppleScript", "Creating disk image")
    lines = [line.strip() for line in log_text.splitlines() if any(m in line for m in markers)]
    return "\n".join(lines[-6:]) or "(no create-dmg output before the failure)"


def leftover_images(hdiutil_info: str, bundle_dir: Path) -> list[str]:
    """Devices of disk images mounted from this build's `rw.*.dmg` files, from `hdiutil info`."""
    devices: list[str] = []
    for block in hdiutil_info.split("================================================"):
        path = re.search(r"^image-path\s*:\s*(.+)$", block, re.MULTILINE)
        if not path or Path(path.group(1).strip()).parent != bundle_dir / "macos":
            continue
        if not Path(path.group(1).strip()).name.startswith("rw."):
            continue
        device = re.search(r"^(/dev/disk\d+)\s", block, re.MULTILINE)
        if device:
            devices.append(device.group(1))
    return devices


def run_logged(cmd: list[str], cwd: Path, log) -> tuple[int, str]:
    """Run `cmd`, echoing and logging every line; return its exit code and its output."""
    log.write(f"\n$ {' '.join(cmd)}  (in {cwd})\n")
    log.flush()
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            bufsize=1, encoding="utf-8", errors="replace")
    assert proc.stdout is not None
    seen: list[str] = []
    for line in proc.stdout:
        sys.stdout.write(line)
        log.write(line)
        seen.append(line)
    log.flush()
    return proc.wait(), "".join(seen)


def clean_disk_image_leftovers(log) -> None:
    info = subprocess.run(["hdiutil", "info"], capture_output=True, text=True, check=False).stdout
    for device in leftover_images(info, BUNDLE):
        log.write(f"detaching leftover {device}\n")
        subprocess.run(["hdiutil", "detach", "-force", device], capture_output=True, check=False)
    for path in (BUNDLE / "macos").glob("rw.*.dmg"):
        log.write(f"deleting leftover {path.name}\n")
        path.unlink(missing_ok=True)


def check_runtime(log) -> bool:
    resources = BUNDLE / "macos" / "Penumbra.app" / "Contents" / "Resources"
    python = resources / "runtime" / "python" / "bin" / "python3"
    if not python.exists():
        return True  # not a macOS bundle; nothing to check here
    got = subprocess.run([str(python), "-c", "import litellm, dspy, penumbra.api"], capture_output=True,
                         text=True, check=False)
    log.write(f"runtime import check: {'ok' if got.returncode == 0 else got.stderr}\n")
    return got.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-runtime", action="store_true", help="reuse desktop/src-tauri/runtime/")
    args = parser.parse_args()

    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{time.strftime('%Y%m%d-%H%M%S')}.log"
    with log_path.open("w", encoding="utf-8") as log:
        runtime = [sys.executable, str(ROOT / "desktop" / "scripts" / "build_runtime.py")]
        if not args.skip_runtime and run_logged(runtime, ROOT, log)[0]:
            print(f"\nThe runtime build failed. Full log: {log_path}")
            return 1
        code, text = run_logged(["cargo", "tauri", "build", "-vv"], SHELL, log)
        attempts = 0
        while code != 0 and dmg_step_failed(text) and attempts < DMG_RETRIES:
            attempts += 1
            print(f"\nThe disk-image step failed; trying it again ({attempts}/{DMG_RETRIES}).")
            print("Where it stopped:")
            print(dmg_failure_reason(text))
            log.write(f"\n--- disk-image step failed; retry {attempts} ---\n{dmg_failure_reason(text)}\n")
            clean_disk_image_leftovers(log)
            code, text = run_logged(["cargo", "tauri", "bundle", "--bundles", "app,dmg", "-vv"], SHELL, log)
        if code != 0:
            if dmg_step_failed(text):
                clean_disk_image_leftovers(log)
                print("\nThe disk-image step failed again. Where it stopped:")
                print(dmg_failure_reason(text))
            print(f"\nThe build failed. Full log: {log_path}")
            return code
        ok = check_runtime(log)
        print(f"\nBuilt{' after retrying the disk image' if attempts else ''}. Full log: {log_path}")
        if not ok:
            print("The bundled Python does not import litellm, dspy and penumbra.api; see the log.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
