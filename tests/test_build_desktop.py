"""The desktop build wrapper (`desktop/scripts/build_desktop.py`): it tells a failed disk-image step
from any other failure, says where create-dmg stopped, and finds the images that step left mounted."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "desktop" / "scripts" / "build_desktop.py"
_spec = importlib.util.spec_from_file_location("build_desktop", _PATH)
build_desktop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_desktop)


FAILED = """    Bundling Penumbra_0.1.0_aarch64.dmg (/x/bundle/dmg/Penumbra_0.1.0_aarch64.dmg)
     Running bundle_dmg.sh
Creating disk image...
Running AppleScript to make Finder stuff pretty: /usr/bin/osascript "/tmp/a" "dmg.X"
Failed running AppleScript
Unmounting disk image...
Error failed to bundle project: error running bundle_dmg.sh: `failed to run /x/dmg/bundle_dmg.sh`
"""


def test_a_disk_image_failure_is_told_from_other_failures():
    assert build_desktop.dmg_step_failed(FAILED)
    assert not build_desktop.dmg_step_failed("error[E0425]: cannot find value `x` in this scope")
    assert not build_desktop.dmg_step_failed("Disk image done\n    Finished 2 bundles")
    # `-vv` prints the script's command line on every build; a later, unrelated failure is not this.
    assert not build_desktop.dmg_step_failed(
        "Running Command `/x/dmg/bundle_dmg.sh --volname Penumbra`\nDisk image done\n"
        "Error failed to bundle project: failed to run codesign"
    )


def test_the_report_says_where_create_dmg_stopped():
    reason = build_desktop.dmg_failure_reason(FAILED)
    assert "Failed running AppleScript" in reason and "Unmounting disk image" in reason
    assert build_desktop.dmg_failure_reason("nothing useful") == "(no create-dmg output before the failure)"


def test_only_this_builds_rw_images_are_found_to_detach():
    bundle = Path("/b/target/release/bundle")
    info = """framework       : 685
================================================
image-path      : /b/target/release/bundle/macos/rw.77164.Penumbra_0.1.0_aarch64.dmg
image-alias     : x
/dev/disk4\tGUID_partition_scheme\t
/dev/disk4s1\t48465300-0000-11AA-AA11-00306543ECAC\t/Volumes/dmg.moJ03P
================================================
image-path      : /Users/someone/Downloads/Other.dmg
/dev/disk5\tGUID_partition_scheme\t
/dev/disk5s1\t48465300-0000-11AA-AA11-00306543ECAC\t/Volumes/Other
================================================
image-path      : /b/target/release/bundle/dmg/Penumbra_0.1.0_aarch64.dmg
/dev/disk6\tGUID_partition_scheme\t
"""
    assert build_desktop.leftover_images(info, bundle) == ["/dev/disk4"]


def test_a_failed_disk_image_is_retried_once_with_the_app_kept(tmp_path, monkeypatch, capsys):
    """A fake `cargo` fails the build in the disk-image step and succeeds on the retry; the wrapper
    must retry with `bundle --bundles app,dmg` (naming `app`, or Tauri deletes the `.app`), clean the
    leftover `rw.*.dmg`, keep the log, and report success."""
    import os
    import stat
    import sys

    calls = tmp_path / "calls.txt"
    fake = tmp_path / "bin" / "cargo"
    fake.parent.mkdir()
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{calls}"\n'
        'if [ "$2" = "build" ]; then\n'
        f'  touch "{tmp_path}/bundle/macos/rw.1.Penumbra.dmg"\n'
        '  echo "Error failed to bundle project: error running bundle_dmg.sh: failed to run bundle_dmg.sh"\n'
        "  exit 1\n"
        "fi\n"
        'echo "Disk image done"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "bundle" / "macos").mkdir(parents=True)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(build_desktop, "SHELL", tmp_path)
    monkeypatch.setattr(build_desktop, "BUNDLE", tmp_path / "bundle")
    monkeypatch.setattr(build_desktop, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(build_desktop.subprocess, "run",
                        lambda *a, **k: type("R", (), {"stdout": "", "returncode": 0, "stderr": ""})())
    monkeypatch.setattr(sys, "argv", ["build_desktop.py", "--skip-runtime"])

    assert build_desktop.main() == 0
    assert calls.read_text().splitlines() == ["tauri build -vv", "tauri bundle --bundles app,dmg -vv"]
    assert not list((tmp_path / "bundle" / "macos").glob("rw.*.dmg")), "the leftover image was removed"
    out = capsys.readouterr().out
    assert "trying it again" in out and "Built after retrying the disk image" in out
    log = next((tmp_path / "logs").glob("*.log")).read_text()
    assert "retry 1" in log and "Disk image done" in log


def test_an_image_that_will_not_detach_is_kept_and_the_reason_logged(tmp_path, monkeypatch):
    import io

    bundle = tmp_path / "bundle"
    (bundle / "macos").mkdir(parents=True)
    rw = bundle / "macos" / "rw.9.Penumbra.dmg"
    rw.write_bytes(b"x")
    info = (
        "================================================\n"
        f"image-path      : {rw}\n"
        "/dev/disk7\tGUID_partition_scheme\t\n"
    )

    def fake_run(cmd, **_kwargs):
        if cmd[:2] == ["hdiutil", "info"]:
            return type("R", (), {"stdout": info, "returncode": 0, "stderr": ""})()
        busy = "hdiutil: couldn't eject disk7: Resource busy"
        return type("R", (), {"stdout": "", "returncode": 16, "stderr": busy})()

    monkeypatch.setattr(build_desktop, "BUNDLE", bundle)
    monkeypatch.setattr(build_desktop.subprocess, "run", fake_run)
    log = io.StringIO()
    build_desktop.clean_disk_image_leftovers(log)
    assert rw.exists(), "a still-mounted image is not deleted from under its mount"
    assert "could not detach /dev/disk7 (16)" in log.getvalue()
    assert "keeping the rw images" in log.getvalue()
