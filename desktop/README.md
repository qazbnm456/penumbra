# The desktop app

`desktop/` wraps the web UI in a native window with [Tauri 2](https://tauri.app) and ships everything it needs inside the app: a Python with Penumbra installed and the deno binary every live run uses. Nobody has to install Python, uv or deno to use it. One codebase produces all three platforms:

| Platform | Webview | Installer |
|---|---|---|
| macOS 13 or later (Apple silicon and Intel) | WKWebView | `.dmg` |
| Windows 10 and 11 (x64) | WebView2 | `.msi` and `.exe` |
| Linux (x64, glibc) | WebKitGTK 4.1 | `.AppImage` and `.deb` |

macOS 13 is the floor because the stylesheet uses `color-mix()`, which WKWebView gained with Safari 16.2.

## What the shell does

- **Lives in the notch.** At rest Penumbra is a background app with no Dock icon and no menu bar; its only presence is the island, a black shape in the MacBook notch (the top centre of a screen without one, the left edge on Windows and Linux). It opens when the pointer rests on it or when something is dragged toward it, swallows what is dropped on it into the Horizon, and opens the workspace when clicked. Right-click it to configure, restart or quit. Launching Penumbra again also opens the workspace.
- **Accepts dropped files.** Tauri's own drop handler is turned off so the web UI's drop-anywhere capture receives them.
- **Starts and stops the server.** On launch it runs the bundled `python -m penumbra.cli serve` on a loopback port, with an API token it mints for that launch, and moves the window onto the web UI once the server answers. Quitting stops the server, which ends every run in flight. If the app is killed instead of quit, the server notices its stdin pipe close and shuts itself down (invariant 81).
- **Keeps the port.** The port is remembered between launches, because the web UI stores its interface language, theme and panel widths per origin, and the origin includes the port.
- **Provides what a browser tab gave for free.** Downloads (Export, the podcast) go to the Downloads folder and are shown in the file manager. File > Print (Cmd/Ctrl+P) prints the page with the web UI's print stylesheet. Links to other sites open in the system browser.
- **Gives the web UI no IPC.** The page talks to its own server over HTTP exactly as it does in a browser, so the token, the local-path ban and every other API rule hold unchanged.

## Configuration and data

Model settings live in `penumbra.env` in the app's data folder, one `KEY=VALUE` per line, the same names as `.env.example`. **File > Open Configuration File…** creates it from a template and opens it; **File > Restart Server** applies a change. Keys never go on the settings page (invariant 41).

An install from before the rename (rlm-notebook, `tw.boik.rlm-notebook`) is moved here on first launch, and its `rlm-notebook.env` becomes `penumbra.env` with every `RN_` setting spelled `PN_`.

The data folder holds orbits, the Horizon, traces and the server log (**File > Show Data Folder**, **File > Show Server Log**):

- macOS: `~/Library/Application Support/tw.boik.penumbra/`
- Windows: `%APPDATA%\tw.boik.penumbra\`
- Linux: `~/.local/share/tw.boik.penumbra/`

Tesseract is not bundled. RapidOCR is the primary OCR engine and is included; tesseract is only its fallback (invariant 7).

## Building

Each platform is built on that platform, because the wheels inside the bundled Python are platform-specific. You need Rust, [uv](https://docs.astral.sh/uv/) and the Tauri CLI (`cargo install tauri-cli --version "^2" --locked`); on Linux, also the WebKitGTK development packages listed in `.github/workflows/desktop.yml`.

```bash
uv run python desktop/scripts/build_runtime.py   # assembles desktop/src-tauri/runtime/ (about 800 MB)
cd desktop/src-tauri && cargo tauri build        # installers in target/release/bundle/
```

For development against a source checkout, skip the runtime and point the shell at the checkout's own interpreter:

```bash
cd desktop/src-tauri && PENUMBRA_PYTHON=../../.venv/bin/python cargo tauri dev
```

The **Desktop** workflow checks the shell and builds every installer on all three platforms. It runs only by hand (Actions > Desktop > Run workflow) until the macOS app is stable; the installers are uploaded as workflow artifacts and nothing is published automatically.

## Signing

The builds are not signed with a developer identity yet.

- **macOS** apps carry an ad-hoc signature, and so does every binary inside the bundled runtime. They run on the machine that built them. On another Mac, Gatekeeper refuses the first launch of a downloaded copy: open System Settings > Privacy & Security and choose Open Anyway, once. (Right-click > Open no longer bypasses it on macOS 15 and later.)
- **Windows** installers are unsigned, so SmartScreen warns on first run; choose More info > Run anyway.
- **Linux** packages are not signed; nothing asks.

With an Apple Developer account, set `bundle.macOS.signingIdentity` to the Developer ID, sign the runtime's binaries with that identity instead of `-` (`adhoc_sign` in `build_runtime.py`), add the hardened-runtime entitlements Python needs (`com.apple.security.cs.allow-unsigned-executable-memory` and `disable-library-validation`), and add notarization to the workflow with the `APPLE_ID`, `APPLE_PASSWORD` and `APPLE_TEAM_ID` secrets the Tauri CLI reads. Windows signing works the same way with a code-signing certificate. Nothing in the app itself changes.

## Regenerating the icon

`desktop/icon.png` is drawn by `scripts/make_icon.py` with the standard library: the citation's highlighter stroke on a copper tile. After changing it, run `cargo tauri icon ../icon.png` in `desktop/src-tauri` and delete the `android` and `ios` folders it adds.
