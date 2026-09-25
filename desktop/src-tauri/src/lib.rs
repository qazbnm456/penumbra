//! The desktop shell: a native window around the same web UI `penumbra serve` ships.
//!
//! The shell owns three things and nothing else:
//!
//! 1. **The server's lifetime.** It starts the bundled Python (`python -m penumbra.cli serve`)
//!    on a loopback port, with a token it minted itself, and stops it (and every run it spawned)
//!    when the app quits.
//! 2. **The window.** A splash page while the server comes up, then the web UI. Navigation is held
//!    to the app's own origin; any other http(s) link opens in the system browser.
//! 3. **What a browser tab gave the web UI for free:** downloads (Export, the podcast) and a Print
//!    command, which a bare webview does not provide.
//!
//! The web UI gets NO IPC. It talks to its own server over HTTP exactly as it does in a browser,
//! so every invariant that holds there (token on every request, no local paths through the API)
//! holds here unchanged.

use std::fs::{self, File};
use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

mod island;

use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::webview::DownloadEvent;
use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const WINDOW: &str = "main";
/// How long the first start may take. The first launch compiles nothing, but it imports numpy,
/// an ONNX runtime and dspy, which is several seconds on a cold disk.
const START_TIMEOUT: Duration = Duration::from_secs(120);
/// `serve` shuts down gracefully in about three seconds (`timeout_graceful_shutdown=3`), killing
/// each run's process group on the way out. This is the margin before the shell stops asking.
const STOP_GRACE: Duration = Duration::from_secs(8);

struct Server {
    child: Child,
    port: u16,
    token: String,
    /// Held, never written. `serve` reads it to EOF (`PN_EXIT_WITH_PARENT`), so the server shuts
    /// itself down if this process dies without stopping it: a crash, a force quit, a SIGKILL.
    _lifeline: Option<std::process::ChildStdin>,
}

#[derive(Default)]
struct ServerState(Mutex<Option<Server>>);

// --- paths -------------------------------------------------------------------------------------

fn data_dir(app: &AppHandle) -> PathBuf {
    let dir = app
        .path()
        .app_data_dir()
        .expect("the OS has no per-user application data directory");
    fs::create_dir_all(&dir).ok();
    dir
}

fn runtime_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path().resource_dir().ok().map(|dir| dir.join("runtime"))
}

/// The interpreter to run the server with. `PENUMBRA_PYTHON` wins, which is how `cargo tauri dev`
/// runs against a source checkout's own `.venv` without bundling anything.
fn python_path(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(value) = std::env::var("PENUMBRA_PYTHON") {
        let path = PathBuf::from(value);
        return path.exists().then_some(path);
    }
    let runtime = runtime_dir(app)?;
    let python = if cfg!(windows) {
        runtime.join("python").join("python.exe")
    } else {
        runtime.join("python").join("bin").join("python3")
    };
    python.exists().then_some(python)
}

fn config_path(app: &AppHandle) -> PathBuf {
    data_dir(app).join("penumbra.env")
}

fn log_path(app: &AppHandle) -> PathBuf {
    let dir = data_dir(app).join("logs");
    fs::create_dir_all(&dir).ok();
    dir.join("server.log")
}

// --- the rename ----------------------------------------------------------------------------------

/// The app was called rlm-notebook, with the identifier `tw.boik.rlm-notebook`, and the OS keys the
/// data folder on the identifier. Before anything creates the new folder, an old one beside it is
/// moved into place, and its configuration file is renamed with every `RN_` setting spelled `PN_`.
/// The server moves the data folders inside it (`notebooks/` to `orbits/`, `inbox/` to `horizon/`)
/// on its own first start (`penumbra.legacy`). Nothing is merged: if both folders exist, the old
/// one is left where it is.
/// Set when the old data folder could not be moved. Boot then shows why instead of starting a
/// server, because starting one would create an EMPTY new folder: the app would open with none of
/// the reader's data, and every later launch would skip the move since the new folder now exists.
static MIGRATION_ERROR: Mutex<Option<String>> = Mutex::new(None);

fn migrate_from_rlm_notebook(app: &AppHandle) {
    let Ok(new_dir) = app.path().app_data_dir() else {
        return;
    };
    let Some(old_dir) = new_dir.parent().map(|p| p.join("tw.boik.rlm-notebook")) else {
        return;
    };
    if old_dir.is_dir() && !new_dir.exists() {
        if let Err(error) = fs::rename(&old_dir, &new_dir) {
            *MIGRATION_ERROR.lock().unwrap_or_else(|p| p.into_inner()) = Some(format!(
                "{}\n\n{}\n→ {}\n\n{error}",
                word(
                    "Your data from rlm-notebook could not be moved. Quit rlm-notebook if it is still running, then open Penumbra again. Nothing has been deleted.",
                    "無法搬移 rlm-notebook 的資料。如果 rlm-notebook 還開著，請先結束它，再重新打開 Penumbra。沒有任何資料被刪除。",
                ),
                old_dir.display(),
                new_dir.display(),
            ));
            return;
        }
    }
    let old_config = new_dir.join("rlm-notebook.env");
    let new_config = new_dir.join("penumbra.env");
    if old_config.exists() && !new_config.exists() {
        if let Ok(text) = fs::read_to_string(&old_config) {
            let renamed: Vec<String> = text.lines().map(rename_legacy_setting).collect();
            if fs::write(&new_config, renamed.join("\n") + "\n").is_ok() {
                let _ = fs::remove_file(&old_config);
            }
        }
    }
}

/// `RN_X=...` becomes `PN_X=...`, keeping an `export ` prefix or a leading `#` (a commented-out
/// setting), and every other line exactly as it was.
fn rename_legacy_setting(line: &str) -> String {
    let (lead, rest) = match line.find(|c: char| !(c == '#' || c.is_whitespace())) {
        Some(at) => line.split_at(at),
        None => return line.to_string(),
    };
    let (export, rest) = match rest.strip_prefix("export ") {
        Some(tail) => ("export ", tail),
        None => ("", rest),
    };
    match rest.strip_prefix("RN_") {
        Some(tail) => format!("{lead}{export}PN_{tail}"),
        None => line.to_string(),
    }
}

// --- configuration -----------------------------------------------------------------------------

/// Written the first time someone opens the configuration file. Keys stay in this file, never on
/// the settings page (invariant 41): a page every token holder can write must not hold a secret.
const CONFIG_TEMPLATE: &str = "\
# Penumbra desktop configuration.
#
# One KEY=VALUE per line. Lines starting with # are ignored. After editing, choose
# File > Restart Server for the change to take effect. Every setting an error message in the app
# names is listed below with its default; remove the # to change one.
#
# --- The model (required before you can ask a question or summarise) ---
#
# The model every run uses, as provider/model, and its API key.
# PN_MAIN_MODEL=anthropic/claude-sonnet-5
# PN_API_KEY=
#
# Or use your Claude Pro or Max subscription instead of a key: install Claude Code, run claude
# once in a terminal to log in, and set this instead (no PN_API_KEY needed):
# PN_MAIN_MODEL=claude-agent-sdk/claude-sonnet-5
#
# Optional: a separate, cheaper model for sub-calls, and an OpenAI-compatible endpoint.
# PN_SUB_MODEL=
# PN_BASE_URL=
#
# --- Network ---
#
# Behind a fake-IP proxy or VPN (Clash, Surge, Mihomo), every link resolves into a reserved range
# and is refused. Set this to the range your proxy uses:
# PN_FETCH_ALLOW_CIDRS=198.18.0.0/15
#
# --- Limits ---
#
# The longest reply one model call may write. Lower it if a model refuses the reply length.
# PN_MAX_TOKENS=32768
# Seconds one run may take before it is stopped. A long podcast takes longer.
# PN_RUN_TIMEOUT_SECONDS=300
# The most text one run reads at once, in characters.
# PN_MAX_CORPUS_CHARS=8000000
# How many captures one automatic summary pass may summarise.
# PN_AUTO_DISTIL_MAX_PER_BATCH=20
#
# --- Settings page overrides ---
#
# These are normally set on the settings page. Set here, they win and the page shows them locked.
# PN_OUTPUT_LANGUAGE=Traditional Chinese
# PN_AUTO_DISTIL=on
# PN_LANDING_ORBIT=off
#
# The podcast voice provider. The desktop app includes edge-tts only.
# PN_TTS_PROVIDER=edge-tts
#
# Every setting, with what it does:
# https://github.com/qazbnm456/penumbra/blob/main/.env.example
";

/// `KEY=VALUE` lines, `#` comments, optional surrounding quotes. Only names made of capitals,
/// digits and underscores are accepted, so a stray line cannot set something odd in the child's
/// environment.
fn read_config(path: &Path) -> Vec<(String, String)> {
    let Ok(text) = fs::read_to_string(path) else {
        return Vec::new();
    };
    text.lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }
            let line = line.strip_prefix("export ").unwrap_or(line);
            let (key, value) = line.split_once('=')?;
            let key = key.trim();
            if key.is_empty()
                || !key
                    .chars()
                    .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '_')
            {
                return None;
            }
            let value = value.trim();
            let value = value
                .strip_prefix('"')
                .and_then(|v| v.strip_suffix('"'))
                .or_else(|| value.strip_prefix('\'').and_then(|v| v.strip_suffix('\'')))
                .unwrap_or(value);
            Some((key.to_string(), value.to_string()))
        })
        .collect()
}

fn ensure_config(app: &AppHandle) -> PathBuf {
    let path = config_path(app);
    if !path.exists() {
        let _ = fs::write(&path, CONFIG_TEMPLATE);
    }
    path
}

fn model_configured(app: &AppHandle) -> bool {
    std::env::var("PN_MAIN_MODEL").is_ok()
        || read_config(&config_path(app))
            .iter()
            .any(|(k, v)| k == "PN_MAIN_MODEL" && !v.is_empty())
}

// --- port and token ----------------------------------------------------------------------------

/// The port is REMEMBERED, not picked fresh each launch. The web UI keeps its per-reader choices
/// (interface language, theme, panel widths) in `localStorage`, which is scoped to the origin, and
/// the origin includes the port: a new port every launch would forget all of them every launch.
fn choose_port(app: &AppHandle) -> u16 {
    let record = data_dir(app).join("desktop.json");
    let remembered = fs::read_to_string(&record)
        .ok()
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| value.get("port").and_then(|p| p.as_u64()))
        .and_then(|p| u16::try_from(p).ok());
    let free = |port: u16| TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port)).is_ok();
    let port = match remembered {
        Some(port) if free(port) => port,
        _ => TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0))
            .and_then(|listener| listener.local_addr())
            .map(|addr| addr.port())
            .unwrap_or(47821),
    };
    remember(app, "port", serde_json::json!(port));
    port
}

/// `desktop.json`, the shell's own small memory. Read-modify-write, so remembering one thing (the
/// port) never forgets another (whether the reader has met the island yet).
fn recall(app: &AppHandle) -> serde_json::Map<String, serde_json::Value> {
    fs::read_to_string(data_dir(app).join("desktop.json"))
        .ok()
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| value.as_object().cloned())
        .unwrap_or_default()
}

fn remember(app: &AppHandle, key: &str, value: serde_json::Value) {
    let mut record = recall(app);
    record.insert(key.to_string(), value);
    let _ = fs::write(
        data_dir(app).join("desktop.json"),
        serde_json::Value::Object(record).to_string(),
    );
}

/// Bring the workspace forward: from the island, the Dock, or a failure it has to show.
fn open_workspace(app: &AppHandle) {
    // A background app has no Dock icon and no menu bar; while the workspace is open it needs both
    // (File > Open Configuration File…, Edit > Paste, Cmd+Q), so it becomes a regular app for as
    // long as the window is up.
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Regular);
    if let Some(window) = app.get_webview_window(WINDOW) {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

/// Put the workspace away. The island and the server stay: Penumbra goes back to being a
/// background app, with no Dock icon and no menu bar, until it is called again.
fn close_workspace(app: &AppHandle) {
    if let Some(window) = app.get_webview_window(WINDOW) {
        let _ = window.hide();
    }
    #[cfg(target_os = "macos")]
    let _ = app.set_activation_policy(tauri::ActivationPolicy::Accessory);
}

/// The island's right-click menu: in the background there is no menu bar and no Dock icon, so this
/// is where Penumbra is opened, configured and quit from.
fn island_menu(app: &AppHandle) {
    let Some(island) = app.get_webview_window(island::LABEL) else {
        return;
    };
    let items = (|| -> tauri::Result<tauri::menu::Menu<tauri::Wry>> {
        MenuBuilder::new(app)
            .item(&MenuItemBuilder::with_id("open", word("Open Penumbra", "打開 Penumbra")).build(app)?)
            .separator()
            .item(&MenuItemBuilder::with_id("config", word("Open Configuration File…", "開啟設定檔…")).build(app)?)
            .item(&MenuItemBuilder::with_id("restart", word("Restart Server", "重新啟動伺服器")).build(app)?)
            .separator()
            .item(&MenuItemBuilder::with_id("quit", word("Quit Penumbra", "結束 Penumbra")).build(app)?)
            .build()
    })();
    if let Ok(menu) = items {
        let _ = island.popup_menu(&menu);
    }
}

/// The island page's navigations. Its own page stays; `/__shell/open`, the one thing it may ask
/// for, opens the workspace and is refused as a navigation; everything else is refused.
fn island_navigation(app: &AppHandle, url: &url::Url) -> bool {
    let ours = url.host_str() == Some("127.0.0.1") && url.port() == current_port(app);
    // Acted on from the event loop, not inside this callback: it runs within WebKit's navigation
    // decision, and opening a window or changing the app's activation from there did nothing,
    // which is why clicking the island never opened the workspace while relaunching did.
    let verb = if ours { url.path().strip_prefix("/__shell/") } else { None };
    if let Some(verb) = verb {
        let app = app.clone();
        let verb = verb.to_string();
        let target = app.clone();
        let _ = target.run_on_main_thread(move || match verb.as_str() {
            "open" => open_workspace(&app),
            "menu" => island_menu(&app),
            "rest" => island::request_rest(),
            _ => {}
        });
        return false;
    }
    ours && url.path() == "/island.html"
}

fn mint_token() -> String {
    let mut bytes = [0u8; 24];
    getrandom::getrandom(&mut bytes).expect("the OS random source failed");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

// --- the server --------------------------------------------------------------------------------

fn start_server(app: &AppHandle) -> Result<Server, String> {
    let python = python_path(app).ok_or_else(|| {
        // The developer's half (rebuild the runtime, or point PENUMBRA_PYTHON at a checkout's
        // Python) is in desktop/README.md; the reader of this screen installed an app.
        word(
            "Some of Penumbra's files are missing. Install the app again.",
            "Penumbra 有部分檔案不見了，請重新安裝這個 app。",
        )
        .to_string()
    })?;
    let data = data_dir(app);
    let port = choose_port(app);
    let token = mint_token();

    let log = File::create(log_path(app)).map_err(|e| format!("{}: {e}", word("Could not write the server log", "無法寫入伺服器紀錄")))?;
    let log_err = log.try_clone().map_err(|e| e.to_string())?;

    let mut command = Command::new(&python);
    command
        .args(["-m", "penumbra.cli", "serve", "--port", &port.to_string()])
        .current_dir(&data)
        .stdin(Stdio::piped())
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(log_err));
    for (key, value) in read_config(&config_path(app)) {
        command.env(key, value);
    }
    // Everything the SHELL owns is set after the configuration file, so no line in it can pin the
    // token, turn off the lifeline or point the server at another interpreter's packages.
    command
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONPATH")
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONUNBUFFERED", "1")
        // The runtime is precompiled with unchecked hashes; never write `__pycache__` into an
        // install directory, which on Linux and a per-machine Windows install is read-only anyway.
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env("PYTHONUTF8", "1")
        .env("DENO_DIR", data.join(".deno"))
        .env("PATH", search_path(app))
        .env("PN_EXIT_WITH_PARENT", "1")
        .env("PN_API_TOKEN", &token);

    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        // Its own process group, so a hard stop can take the whole group in one call.
        command.process_group(0);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
        // A hidden console the server's own children inherit, so no run ever flashes a window.
        command.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
    }

    let mut child = command
        .spawn()
        .map_err(|e| format!("could not start {}: {e}", python.display()))?;
    let lifeline = child.stdin.take();
    Ok(Server { child, port, token, _lifeline: lifeline })
}

/// The bundled deno first (every live run executes in its sandbox), then the usual places a GUI
/// app's minimal PATH leaves out on macOS, so a `claude` CLI for the subscription path is found.
fn search_path(app: &AppHandle) -> std::ffi::OsString {
    let mut parts: Vec<PathBuf> = Vec::new();
    if let Some(runtime) = runtime_dir(app) {
        parts.push(runtime.join("deno"));
    }
    if cfg!(target_os = "macos") {
        // Where Claude Code's installers put `claude`, which the subscription path runs: the
        // native installer's ~/.local/bin, and ~/.claude/local for an older local install.
        if let Some(home) = std::env::var_os("HOME") {
            parts.push(PathBuf::from(&home).join(".local/bin"));
            parts.push(PathBuf::from(&home).join(".claude/local"));
        }
        parts.push(PathBuf::from("/opt/homebrew/bin"));
        parts.push(PathBuf::from("/usr/local/bin"));
    }
    if let Some(existing) = std::env::var_os("PATH") {
        parts.extend(std::env::split_paths(&existing));
    }
    std::env::join_paths(parts).unwrap_or_default()
}

/// A plain HTTP probe of `/`, which the server serves without the token (invariant 77 exempts the
/// static assets). No HTTP client dependency for one request.
fn server_answers(port: u16) -> bool {
    let addr = SocketAddrV4::new(Ipv4Addr::LOCALHOST, port).into();
    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(300)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let request = format!("GET / HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut head = [0u8; 16];
    let read = stream.read(&mut head).unwrap_or(0);
    String::from_utf8_lossy(&head[..read]).contains(" 200")
}

fn stop_server(server: &mut Server) {
    if matches!(server.child.try_wait(), Ok(Some(_))) {
        return;
    }
    #[cfg(unix)]
    {
        let pid = server.child.id() as libc::pid_t;
        // SIGTERM to the server alone: its shutdown kills each run's own process group (invariant
        // 22), which a signal to the server's group would not reach.
        unsafe {
            libc::kill(pid, libc::SIGTERM);
        }
        let deadline = Instant::now() + STOP_GRACE;
        while Instant::now() < deadline {
            if matches!(server.child.try_wait(), Ok(Some(_))) {
                return;
            }
            thread::sleep(Duration::from_millis(100));
        }
        unsafe {
            libc::killpg(pid, libc::SIGKILL);
        }
        let _ = server.child.wait();
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        // No SIGTERM on Windows. `/T` takes the server's whole child tree, runs included.
        let _ = Command::new("taskkill")
            .args(["/T", "/F", "/PID", &server.child.id().to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
        let _ = server.child.wait();
    }
}

fn log_tail(app: &AppHandle) -> String {
    let text = fs::read_to_string(log_path(app)).unwrap_or_default();
    let lines: Vec<&str> = text.lines().collect();
    lines[lines.len().saturating_sub(12)..].join("\n")
}

// --- the splash page ---------------------------------------------------------------------------

/// `state` is `starting` or `failed`; the page holds the words for each in both languages.
fn splash(window: &WebviewWindow, state: &str, error: bool, detail: &str) {
    let call = format!(
        "window.setStatus && window.setStatus({}, {}, {})",
        serde_json::to_string(state).unwrap_or_default(),
        error,
        serde_json::to_string(detail).unwrap_or_default()
    );
    let _ = window.eval(&call);
}

/// Start (or restart) the server and move the window onto it once it answers. Runs on its own
/// thread, because waiting for a Python server to import its dependencies must not block the UI.
/// One boot at a time. Restart pressed while a boot is still waiting for its server would otherwise
/// race it: the older boot could navigate with the OLD token onto the NEW server (every request
/// then 401s), or two servers could be started on the same remembered port.
static BOOTING: Mutex<()> = Mutex::new(());

/// Set while a Restart is waiting its turn. Further presses fold into that one instead of queueing
/// a full stop-and-start each, which on a server slow to answer made Restart look dead for minutes.
static RESTART_QUEUED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

fn boot(app: AppHandle) {
    thread::spawn(move || {
        let _one_at_a_time = BOOTING.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        RESTART_QUEUED.store(false, std::sync::atomic::Ordering::SeqCst);
        let Some(window) = app.get_webview_window(WINDOW) else {
            return;
        };
        let stuck = MIGRATION_ERROR.lock().unwrap_or_else(|p| p.into_inner()).clone();
        if let Some(message) = stuck {
            splash_failure(&window, &message);
            return;
        }
        if window.url().map(|u| u.scheme() != "tauri" && u.host_str() != Some("tauri.localhost")).unwrap_or(false) {
            let _ = window.navigate(splash_url());
            thread::sleep(Duration::from_millis(300));
        }
        splash(&window, "starting", false, "");

        let state = app.state::<ServerState>();
        // Taken out first, THEN stopped: holding the lock through an up-to-8s stop would block the
        // navigation handler, which reads the port under the same lock on the UI thread.
        let old = state.0.lock().unwrap().take();
        if let Some(mut old) = old {
            stop_server(&mut old);
        }
        let server = match start_server(&app) {
            Ok(server) => server,
            Err(message) => {
                splash_failure(&window, &message);
                return;
            }
        };
        let (port, token) = (server.port, server.token.clone());
        *state.0.lock().unwrap() = Some(server);

        let deadline = Instant::now() + START_TIMEOUT;
        loop {
            if server_answers(port) {
                break;
            }
            let exited = state
                .0
                .lock()
                .unwrap()
                .as_mut()
                .map(|s| matches!(s.child.try_wait(), Ok(Some(_))))
                .unwrap_or(true);
            if exited || Instant::now() > deadline {
                let why = if exited {
                    word("The server stopped while starting. The end of its log:", "伺服器在啟動途中停止了。以下是紀錄的最後幾行：")
                } else {
                    word("The server did not answer in time. The end of its log:", "伺服器沒有及時回應。以下是紀錄的最後幾行：")
                };
                splash_failure(&window, &format!("{why}\n\n{}", log_tail(&app)));
                return;
            }
            thread::sleep(Duration::from_millis(150));
        }

        // In the FRAGMENT, which the browser never sends: in the query string uvicorn's access log
        // wrote the token into `server.log`, the file "Show Server Log" invites people to share.
        // `menu` is the language the menu bar is written in, which follows the OS, not the page's
        // interface language, so the page can quote a menu item the way the reader will see it.
        let menu = if chinese() { "zh" } else { "en" };
        let target = format!("http://127.0.0.1:{port}/#token={token}&shell=desktop&menu={menu}");
        if let Ok(url) = url::Url::parse(&target) {
            let _ = window.navigate(url);
        }
        let island_target = format!("http://127.0.0.1:{port}/island.html#token={token}");
        if let Ok(url) = url::Url::parse(&island_target) {
            let nav = app.clone();
            island::show(&app, url, move |u| island_navigation(&nav, u));
        }
    });
}

/// A failure can arrive before the splash page has loaded (a missing interpreter fails at once), and
/// an `eval` into a page that is not there yet is lost, leaving "Starting…" up forever. Sent a few
/// times over a few seconds, which costs nothing once it has landed.
fn splash_failure(window: &WebviewWindow, detail: &str) {
    // The workspace may be hidden (the island is the app at rest), and a failure nobody can see is
    // the worst kind. Through `open_workspace`, so the app also becomes a regular one with a Dock
    // icon and a menu bar: a background app whose server failed has no island either, and would
    // otherwise leave no way to quit.
    let app = window.app_handle().clone();
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || open_workspace(&handle));
    for _ in 0..10 {
        splash(window, "failed", true, detail);
        thread::sleep(Duration::from_millis(300));
    }
}

fn splash_url() -> url::Url {
    let base = if cfg!(windows) { "http://tauri.localhost/index.html" } else { "tauri://localhost/index.html" };
    url::Url::parse(base).expect("static URL")
}

// --- navigation and downloads ------------------------------------------------------------------

fn current_port(app: &AppHandle) -> Option<u16> {
    app.state::<ServerState>().0.lock().ok()?.as_ref().map(|s| s.port)
}

/// The app's own origin, the splash page and in-page schemes stay in the window. Any other
/// http(s) link opens in the system browser: a webview with no address bar is the wrong place to
/// read a third-party page, and the reader could not get back.
fn allow_navigation(app: &AppHandle, url: &url::Url) -> bool {
    match url.scheme() {
        "tauri" | "about" | "blob" | "data" => true,
        "http" | "https" => {
            let host = url.host_str().unwrap_or("");
            if host == "tauri.localhost" {
                return true;
            }
            if host == "127.0.0.1" && url.port() == current_port(app) {
                return true;
            }
            let _ = open::that_detached(url.as_str());
            false
        }
        _ => false,
    }
}

/// A browser tab saves `<a download>` and blob links on its own; a webview asks. Saved to the
/// Downloads folder under the name the page suggested, never overwriting, then shown in the file
/// manager so the reader sees where it went.
fn place_download(app: &AppHandle, suggested: &Path) -> PathBuf {
    let dir = app
        .path()
        .download_dir()
        .unwrap_or_else(|_| data_dir(app).join("downloads"));
    let _ = fs::create_dir_all(&dir);
    let name = suggested
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .filter(|n| !n.is_empty())
        .unwrap_or_else(|| "penumbra-download".to_string());
    let stem = Path::new(&name).file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
    let ext = Path::new(&name).extension().map(|e| format!(".{}", e.to_string_lossy())).unwrap_or_default();
    let mut candidate = dir.join(&name);
    let mut n = 1;
    while candidate.exists() {
        candidate = dir.join(format!("{stem} ({n}){ext}"));
        n += 1;
    }
    candidate
}

/// Open the configuration file in a TEXT editor. Handing it to the OS as a file did nothing on a
/// normal Mac: no application claims `.env`, `open` fails with kLSApplicationNotFoundErr, and the
/// menu item appeared dead. If even the text editor cannot be started, show the file instead.
fn open_as_text(path: &Path) {
    #[cfg(target_os = "macos")]
    let opened = Command::new("open").arg("-t").arg(path).status().map(|s| s.success()).unwrap_or(false);
    #[cfg(windows)]
    let opened = Command::new("notepad.exe").arg(path).spawn().is_ok();
    #[cfg(all(unix, not(target_os = "macos")))]
    let opened = open::that(path).is_ok();
    if !opened {
        reveal(path);
    }
}

fn reveal(path: &Path) {
    #[cfg(target_os = "macos")]
    let _ = Command::new("open").arg("-R").arg(path).spawn();
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // `raw_arg`: `.arg` would quote the whole `/select,<path>` and break on a path with spaces.
        let _ = Command::new("explorer").raw_arg(format!("/select,\"{}\"", path.display())).spawn();
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    if let Some(parent) = path.parent() {
        let _ = open::that_detached(parent);
    }
}

// --- words ---------------------------------------------------------------------------------------

/// The shell's own words follow the OS language: Traditional Chinese or English, the two the web UI
/// ships. The web UI decides its own language separately (invariant 48); this only covers what
/// the shell draws itself, the menu and the splash.
fn chinese() -> bool {
    sys_locale::get_locale()
        .map(|l| {
            let l = l.to_ascii_lowercase();
            l.starts_with("zh") && (l.contains("hant") || l.contains("tw") || l.contains("hk") || l.contains("mo"))
        })
        .unwrap_or(false)
}

fn word(en: &'static str, zh: &'static str) -> &'static str {
    if chinese() { zh } else { en }
}

// --- menu --------------------------------------------------------------------------------------

fn build_menu(app: &AppHandle) -> tauri::Result<tauri::menu::Menu<tauri::Wry>> {
    let config = MenuItemBuilder::with_id("config", word("Open Configuration File…", "開啟設定檔…")).build(app)?;
    let data = MenuItemBuilder::with_id("data", word("Show Data Folder", "顯示資料夾")).build(app)?;
    let logs = MenuItemBuilder::with_id("logs", word("Show Server Log", "顯示伺服器紀錄")).build(app)?;
    let restart = MenuItemBuilder::with_id("restart", word("Restart Server", "重新啟動伺服器"))
        .accelerator("CmdOrCtrl+Shift+R")
        .build(app)?;
    let print = MenuItemBuilder::with_id("print", word("Print…", "列印…")).accelerator("CmdOrCtrl+P").build(app)?;
    let reload = MenuItemBuilder::with_id("reload", word("Reload", "重新載入")).accelerator("CmdOrCtrl+R").build(app)?;

    let mut file = SubmenuBuilder::new(app, word("File", "檔案"))
        .item(&config)
        .item(&data)
        .item(&logs)
        .separator()
        .item(&restart)
        .separator()
        .item(&print)
        .separator()
        .item(&PredefinedMenuItem::close_window(app, None)?);
    if !cfg!(target_os = "macos") {
        file = file.item(&PredefinedMenuItem::quit(app, None)?);
    }
    let edit = SubmenuBuilder::new(app, word("Edit", "編輯"))
        .undo()
        .redo()
        .separator()
        .cut()
        .copy()
        .paste()
        .select_all()
        .build()?;
    let view = SubmenuBuilder::new(app, word("View", "顯示方式"))
        .item(&reload)
        .item(&PredefinedMenuItem::fullscreen(app, None)?)
        .build()?;
    let window = SubmenuBuilder::new(app, word("Window", "視窗")).minimize().maximize().build()?;

    let mut menu = MenuBuilder::new(app);
    if cfg!(target_os = "macos") {
        let app_menu = SubmenuBuilder::new(app, "Penumbra")
            .about(None)
            .separator()
            .services()
            .separator()
            .hide()
            .hide_others()
            .show_all()
            .separator()
            .quit()
            .build()?;
        menu = menu.item(&app_menu);
    }
    menu.item(&file.build()?).item(&edit).item(&view).item(&window).build()
}

fn on_menu(app: &AppHandle, id: &str) {
    let window = app.get_webview_window(WINDOW);
    match id {
        "open" => open_workspace(app),
        "quit" => app.exit(0),
        "config" => open_as_text(&ensure_config(app)),
        "data" => {
            let _ = open::that_detached(data_dir(app));
        }
        "logs" => reveal(&log_path(app)),
        "restart" => {
            if !RESTART_QUEUED.swap(true, std::sync::atomic::Ordering::SeqCst) {
                boot(app.clone());
            }
        }
        "print" => {
            if let Some(window) = window {
                let _ = window.print();
            }
        }
        "reload" => {
            if let Some(window) = window {
                let _ = window.eval("location.reload()");
            }
        }
        _ => {}
    }
}

// --- entry point -------------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        // Calling Penumbra again (a second launch from Finder, Spotlight or a shortcut) brings the
        // workspace forward instead of starting a second copy. macOS reports that as `Reopen`; on
        // Windows and Linux a second process would start, so this plugin forwards it instead.
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| open_workspace(app)))
        .manage(ServerState::default())
        .menu(build_menu)
        .on_menu_event(|app, event| on_menu(app, event.id().as_ref()))
        .setup(|app| {
            let handle = app.handle().clone();
            migrate_from_rlm_notebook(&handle);
            island::measure(&handle);
            // The workspace opens by itself only the first time, so the reader meets the app before
            // meeting the island. After that the island IS the app at rest.
            let introduced = MIGRATION_ERROR.lock().map(|e| e.is_none()).unwrap_or(false)
                && recall(&handle).get("introduced").and_then(|v| v.as_bool()).unwrap_or(false);
            let nav = handle.clone();
            let dl = handle.clone();
            WebviewWindowBuilder::new(app, WINDOW, WebviewUrl::App("index.html".into()))
                .title("Penumbra")
                .inner_size(1440.0, 900.0)
                .min_inner_size(900.0, 600.0)
                .visible(!introduced)
                // Tauri's own file-drop handler swallows the drag before the page sees it, so the
                // web UI's drop-anywhere capture never fired. The page handles drops itself.
                .disable_drag_drop_handler()
                .on_navigation(move |url| allow_navigation(&nav, url))
                // A `target="_blank"` link (the source viewer's origin) asks for a new window, which
                // a webview drops silently unless someone answers. The answer is the system browser.
                .on_new_window(|url, _features| {
                    if matches!(url.scheme(), "http" | "https") {
                        let _ = open::that_detached(url.as_str());
                    }
                    tauri::webview::NewWindowResponse::Deny
                })
                .on_download(move |_webview, event| {
                    match event {
                        DownloadEvent::Requested { destination, .. } => {
                            let placed = place_download(&dl, destination);
                            *destination = placed;
                        }
                        DownloadEvent::Finished { path: Some(path), success: true, .. } => reveal(&path),
                        _ => {}
                    }
                    true
                })
                .build()?;
            // Not while a failed move is pending: writing the template would create the new folder.
            let migration_pending = MIGRATION_ERROR.lock().map(|e| e.is_some()).unwrap_or(false);
            if !migration_pending && !model_configured(&handle) {
                ensure_config(&handle);
            }
            if !migration_pending {
                remember(&handle, "introduced", serde_json::json!(true));
            }
            // At rest Penumbra is a background app: the island is its only presence.
            #[cfg(target_os = "macos")]
            if introduced {
                let _ = handle.set_activation_policy(tauri::ActivationPolicy::Accessory);
            }
            boot(handle);
            Ok(())
        })
        // Closing the workspace puts it away; the island stays, and so does the server. Quit is
        // Cmd+Q (or File > Quit), which stops both.
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == WINDOW {
                    api.prevent_close();
                    close_workspace(window.app_handle());
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building the Penumbra desktop app");

    app.run(|app, event| {
        #[cfg(target_os = "macos")]
        if let RunEvent::Reopen { .. } = event {
            open_workspace(app);
        }
        if let RunEvent::Exit = event {
            let server = app.state::<ServerState>().0.lock().unwrap().take();
            if let Some(mut server) = server {
                stop_server(&mut server);
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::read_config;
    use std::io::Write;

    #[test]
    fn config_reads_keys_values_quotes_and_skips_the_rest() {
        let mut file = tempfile_path("cfg");
        writeln!(
            file.1,
            "# comment\n\nPN_MAIN_MODEL=\"openai/gpt\"\nexport PN_API_KEY='sk-1'\nlower=no\nBAD KEY=x\nPN_BASE_URL = http://x/v1\n"
        )
        .unwrap();
        let got = read_config(&file.0);
        assert_eq!(
            got,
            vec![
                ("PN_MAIN_MODEL".into(), "openai/gpt".into()),
                ("PN_API_KEY".into(), "sk-1".into()),
                ("PN_BASE_URL".into(), "http://x/v1".into()),
            ]
        );
        let _ = std::fs::remove_file(&file.0);
    }

    #[test]
    fn legacy_settings_are_renamed_and_nothing_else_is() {
        use super::rename_legacy_setting as r;
        assert_eq!(r("RN_MAIN_MODEL=x"), "PN_MAIN_MODEL=x");
        assert_eq!(r("export RN_API_KEY='k'"), "export PN_API_KEY='k'");
        assert_eq!(r("# RN_SUB_MODEL="), "# PN_SUB_MODEL=");
        assert_eq!(r("# a comment about RN_ things"), "# a comment about RN_ things");
        assert_eq!(r("RETURN_X=1"), "RETURN_X=1");
        assert_eq!(r(""), "");
    }

    fn tempfile_path(tag: &str) -> (std::path::PathBuf, std::fs::File) {
        let path = std::env::temp_dir().join(format!("penumbra-{tag}-{}.env", std::process::id()));
        let file = std::fs::File::create(&path).unwrap();
        (path, file)
    }
}

