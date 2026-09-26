//! The island: the whole app while the workspace is closed.
//!
//! A small, frameless, transparent window that sits in the MacBook notch (the top centre of a
//! screen without one, and the left edge on Windows and Linux). At rest it is exactly the notch's
//! size and colour. The shell watches the pointer and resizes it:
//!
//! - **hover**: the pointer rests on it, so it grows a little and says what it is; a click opens
//!   the workspace.
//! - **armed**: something is being DRAGGED near it (a mouse button is held), so it opens wide
//!   enough to be an easy target.
//! - **swallow**: the drag ended over it; the page plays the drop falling in, then it closes.
//! - **listen**: the pointer has rested on the hover shape for a few seconds without dragging. A
//!   drop is over by then, so the reader is waiting: a line fades in under the ring saying they can
//!   type, and the island takes the keyboard. The first key opens the note field with it; moving
//!   away puts the island to rest and hands the keyboard back.
//! - **note**: the reader asked to write a thought (the pen on the hover shape, or the menu), so
//!   it opens into a one-line field and, for this state only, takes the keyboard. It stays until
//!   the page says it is done, and then hands the keyboard back.
//!
//! The page draws every state; this module only decides which state it is and how big the window
//! is. Watching the pointer from here, rather than from the page, is what lets the island open
//! BEFORE the pointer reaches it and keeps the page free of any bridge to the shell (invariant 81).

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, LogicalPosition, LogicalSize, Manager, WebviewUrl, WebviewWindowBuilder};

pub const LABEL: &str = "island";
/// One display frame. The pointer is sampled this often, so the island reacts within a frame of the
/// pointer arriving; at 40ms it lagged visibly behind a quick drag.
const TICK: Duration = Duration::from_millis(16);
/// How long the pointer must rest on the island before it says what it is. Shorter and every trip
/// to the menu bar flickers it; longer and it feels unresponsive.
const HOVER_DELAY: Duration = Duration::from_millis(160);
/// How long the pointer must rest on the hover shape before the island offers to take a typed
/// thought. A drag and drop is over well within it, so resting this long means waiting, not aiming.
const DWELL: Duration = Duration::from_millis(3500);
/// How long it stays open after the pointer leaves, so a drag that wobbles out and back in does not
/// make it snap shut under the cursor.
const LEAVE_GRACE: Duration = Duration::from_millis(380);
/// How far a press must travel before it counts as a drag rather than a click.
const DRAG_DISTANCE: f64 = 12.0;
/// The longest the island stays open after a release over it if the page never says it took a
/// drop: a drag cancelled with Escape ends the same way, and must not leave it open for long.
const SWALLOW_BACKSTOP: Duration = Duration::from_millis(1600);
/// How long the page's shrink animation takes; the window is only made small after it.
const SHRINK_AFTER: Duration = Duration::from_millis(320);

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
}

impl Rect {
    fn contains(&self, px: f64, py: f64, margin: f64) -> bool {
        px >= self.x - margin && px <= self.x + self.w + margin && py >= self.y - margin && py <= self.y + self.h + margin
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Geometry {
    /// `top` for the notch or a screen's top centre, `left` for the left edge.
    pub edge: &'static str,
    /// How much of the window's top the hardware hides: the notch's height, or 0. The page keeps
    /// its content below it, because the display has no pixels there.
    pub inset: f64,
    /// The menu-bar screen's height, measured with the rest on the main thread, for turning
    /// AppKit's bottom-left pointer coordinates into the top-left ones the window is placed in.
    pub screen_h: f64,
    pub rest: Rect,
    pub hover: Rect,
    pub armed: Rect,
    pub note: Rect,
    /// The hover shape with room under the ring for the line that says typing works.
    pub listen: Rect,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    Rest,
    Hover,
    Armed,
    Swallow,
    Note,
    Listen,
}

impl State {
    fn name(self) -> &'static str {
        match self {
            State::Rest => "collapsed",
            State::Hover => "hover",
            State::Armed => "armed",
            State::Swallow => "swallow",
            State::Note => "note",
            State::Listen => "listen",
        }
    }
}

static GEOMETRY: Mutex<Option<Geometry>> = Mutex::new(None);
static WATCHING: AtomicBool = AtomicBool::new(false);
/// Bumped on every state change, so a delayed shrink can tell whether the island reopened while it
/// waited. Without it a Rest -> Armed within the shrink delay left a notch-sized window under a
/// page drawing the open shape, and the drop fell through to whatever was underneath.
static EPOCH: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
/// How often the screens are re-measured: a display plugged in, the lid closed, a resolution
/// change. Measuring once at launch left the notch shape stranded on the wrong screen.
const REMEASURE_EVERY: Duration = Duration::from_secs(4);
/// The loop's pace when nothing is near: at rest, no button held, the pointer far away. 16ms is
/// only needed while something could happen within a frame.
const IDLE_TICK: Duration = Duration::from_millis(120);
/// Set by the page (`/__shell/rest`) once a drop has been swallowed: the page, not the pointer,
/// knows when that happened.
static REST_REQUESTED: AtomicBool = AtomicBool::new(false);

/// Set by the page (`/__shell/note`) or the menu: open the one-line field.
static NOTE_REQUESTED: AtomicBool = AtomicBool::new(false);

/// The page asks for the island to close (after a swallow, or when a note is sent or dismissed).
/// Picked up by the pointer loop.
pub fn request_rest() {
    REST_REQUESTED.store(true, Ordering::SeqCst);
}

/// Set while the workspace fills the screen at rest: the island is hidden and the pointer loop
/// leaves it alone, so the sky has no bar floating over it.
static SUSPENDED: AtomicBool = AtomicBool::new(false);

pub fn suspend(app: &AppHandle, on: bool) {
    if SUSPENDED.swap(on, Ordering::SeqCst) == on {
        return;
    }
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        let Some(window) = handle.get_webview_window(LABEL) else {
            return;
        };
        if on {
            let _ = window.hide();
            return;
        }
        // Shown again, macOS keeps an ordinary window below the menu bar, which left the island
        // hanging under it as a black bar. Its level goes back first, then its place in the notch.
        let _ = window.show();
        platform::float_above_menu_bar(&handle, &window);
        // Queued after the level change, which is itself queued on this thread.
        let again = handle.clone();
        let _ = handle.run_on_main_thread(move || {
            if let Some(geo) = geometry() {
                place(&again, geo.rest);
                tell(&again, State::Rest, &geo);
            }
        });
    });
}

pub fn hide_pointer_until_it_moves() {
    platform::hide_pointer_until_it_moves();
}

/// Open the island as a field to write a thought in. Picked up by the pointer loop.
pub fn request_note() {
    NOTE_REQUESTED.store(true, Ordering::SeqCst);
}

/// Work out where the island goes. Must run on the main thread on macOS (AppKit's screen APIs).
pub fn measure(app: &AppHandle) {
    let geometry = platform::geometry(app);
    *GEOMETRY.lock().unwrap_or_else(|p| p.into_inner()) = geometry;
}

fn geometry() -> Option<Geometry> {
    *GEOMETRY.lock().unwrap_or_else(|p| p.into_inner())
}

/// Show the island on `url` (the server's `island.html` with the token in the fragment), creating
/// the window the first time and re-pointing it after a restart, then start watching the pointer.
pub fn show(app: &AppHandle, url: url::Url, on_navigation: impl Fn(&url::Url) -> bool + Send + 'static) {
    let Some(geo) = geometry() else {
        return;
    };
    if let Some(window) = app.get_webview_window(LABEL) {
        let _ = window.navigate(url);
    } else {
        let built = WebviewWindowBuilder::new(app, LABEL, WebviewUrl::External(url))
            .title("Penumbra")
            .decorations(false)
            .transparent(true)
            .always_on_top(true)
            .skip_taskbar(true)
            .resizable(false)
            .shadow(false)
            .focused(false)
            // A click on the island acts at once. Without it macOS spends the first click making
            // the window key, so opening the workspace took two clicks while the app was in the
            // background, which is always.
            .accept_first_mouse(true)
            .visible_on_all_workspaces(true)
            .inner_size(geo.rest.w, geo.rest.h)
            .position(geo.rest.x, geo.rest.y)
            .disable_drag_drop_handler()
            .on_navigation(on_navigation)
            .build();
        let Ok(window) = built else {
            return;
        };
        platform::float_above_menu_bar(app, &window);
    }
    if !WATCHING.swap(true, Ordering::SeqCst) {
        let app = app.clone();
        thread::spawn(move || watch(app));
    }
}

/// Room around the shape for what is drawn OUTSIDE it: the concave shoulders where it meets the top
/// of the screen, and its shadow. At rest there is none, so the resting window is exactly the notch.
const PAD_SIDE: f64 = 18.0;
const PAD_BELOW: f64 = 30.0;

fn padded(rect: Rect, edge: &str) -> Rect {
    if edge == "left" {
        Rect { x: rect.x, y: rect.y - PAD_SIDE, w: rect.w + PAD_BELOW, h: rect.h + 2.0 * PAD_SIDE }
    } else {
        Rect { x: rect.x - PAD_SIDE, y: rect.y, w: rect.w + 2.0 * PAD_SIDE, h: rect.h + PAD_BELOW }
    }
}

fn place(app: &AppHandle, rect: Rect) {
    if let Some(window) = app.get_webview_window(LABEL) {
        let _ = window.set_size(LogicalSize::new(rect.w, rect.h));
        let _ = window.set_position(LogicalPosition::new(rect.x, rect.y));
    }
}

/// Tell the page the state AND the size its shape should reach. The page animates the shape from
/// whatever size it has now to that one; it cannot read the target from its own window, because the
/// resize is dispatched asynchronously and may not have landed when this runs.
fn tell(app: &AppHandle, state: State, geo: &Geometry) {
    let target = match state {
        State::Rest => geo.rest,
        State::Hover => geo.hover,
        State::Armed | State::Swallow => geo.armed,
        State::Note => geo.note,
        State::Listen => geo.listen,
    };
    if let Some(window) = app.get_webview_window(LABEL) {
        let _ = window.eval(format!(
            "window.island && window.island.setState({:?}, {:?}, {}, {}, {})",
            state.name(),
            geo.edge,
            geo.inset,
            target.w,
            target.h
        ));
    }
}

/// The pointer loop. Growing: the window is enlarged first, then the page animates into it.
/// Shrinking: the page animates first, then the window is made small, so nothing is ever clipped.
fn watch(app: AppHandle) {
    let mut state = State::Rest;
    let mut hover_since: Option<Instant> = None;
    // When the current hover began, for the dwell that turns it into listening.
    let mut hovering_since: Option<Instant> = None;
    // Where the window is, so the pointer can be told to the page in the page's own coordinates.
    let mut placed = Rect { x: 0.0, y: 0.0, w: 0.0, h: 0.0 };
    let mut last_told: Option<(f64, f64)> = None;
    // Where the pointer was when the workspace went to rest, to tell a move from stillness.
    let mut rest_pointer: Option<(f64, f64)> = None;
    let mut away_since: Option<Instant> = None;
    let mut swallow_until: Option<Instant> = None;
    let mut was_dragging = false;
    let mut press: Option<Press> = None;
    let mut measured_at = Instant::now();
    let mut tick = TICK;
    loop {
        thread::sleep(tick);
        if measured_at.elapsed() >= REMEASURE_EVERY {
            measured_at = Instant::now();
            remeasure(&app, state);
        }
        if SUSPENDED.load(Ordering::SeqCst) {
            // At rest the workspace fills the screen borderless, and a borderless window gets no
            // mouse-moved events, so the page never saw the pointer move and rest would not end.
            // The shell sees it here and tells the page, the way it tells the island its state.
            tick = Duration::from_millis(50);
            if let Some(at) = platform::pointer(&app) {
                match rest_pointer {
                    None => rest_pointer = Some(at),
                    Some(from) if ((at.0 - from.0).powi(2) + (at.1 - from.1).powi(2)).sqrt() > 3.0 => {
                        rest_pointer = None;
                        wake_workspace(&app);
                    }
                    _ => {}
                }
            }
            continue;
        }
        rest_pointer = None;
        let (Some(geo), Some((px, py))) = (geometry(), platform::pointer(&app)) else {
            continue;
        };
        // **A held button is not a drag, and neither is every drag.** Clicking the island held the
        // button over it, and selecting text or moving a window near the top of the screen is a
        // press that moves: both opened it as a drop target. A drag here is a press that started
        // off the island, has moved, and (where the platform can tell) is a real drag-and-drop:
        // on macOS the drag pasteboard changes when one begins.
        let pressed = platform::button_down();
        if !pressed {
            press = None;
        } else if press.is_none() {
            press = Some(Press { x: px, y: py, pasteboard: platform::drag_pasteboard() });
        }
        let dragging = press.is_some_and(|p| {
            !geo.hover.contains(p.x, p.y, 4.0)
                && ((px - p.x).powi(2) + (py - p.y).powi(2)).sqrt() > DRAG_DISTANCE
                && platform::drag_began_since(p.pasteboard)
        });
        let now = Instant::now();

        let rest_asked = REST_REQUESTED.swap(false, Ordering::SeqCst);
        let note_asked = NOTE_REQUESTED.swap(false, Ordering::SeqCst);
        let next = match state {
            _ if rest_asked => State::Rest,
            _ if note_asked => State::Note,
            // Writing ignores the pointer: the reader may move it anywhere while they type, and a
            // drag passing by must not turn the field into a drop target under their words.
            State::Note => State::Note,
            // After a release over it the island waits for the page to say it took a drop (it
            // then asks for rest itself); the backstop covers a drag cancelled with Escape.
            State::Swallow => match swallow_until {
                Some(until) if now < until => State::Swallow,
                _ => State::Rest,
            },
            State::Armed if was_dragging && !dragging && geo.armed.contains(px, py, 0.0) => {
                swallow_until = Some(now + SWALLOW_BACKSTOP);
                State::Swallow
            }
            // A drag opens the island only when it reaches the notch's own row, a little wider than
            // the notch. A zone the size of the open shape plus 70 points caught every drag across
            // the top of the screen: moving a terminal's tab opened it. Once open, it stays open
            // anywhere over the open shape, so the drop still lands.
            _ if dragging && (state == State::Armed || drag_target(&geo).contains(px, py, 0.0)) && geo.armed.contains(px, py, 24.0) => {
                State::Armed
            }
            State::Armed | State::Hover | State::Listen => {
                let region = match state {
                    State::Armed => geo.armed,
                    State::Listen => geo.listen,
                    _ => geo.hover,
                };
                if region.contains(px, py, 6.0) {
                    away_since = None;
                    let dwelt = hovering_since.is_some_and(|since| now.duration_since(since) >= DWELL);
                    if state == State::Hover && dwelt && !pressed {
                        State::Listen
                    } else {
                        state
                    }
                } else if away_since.get_or_insert(now).elapsed() >= LEAVE_GRACE {
                    State::Rest
                } else {
                    state
                }
            }
            State::Rest => {
                if !dragging && geo.rest.contains(px, py, 3.0) {
                    if hover_since.get_or_insert(now).elapsed() >= HOVER_DELAY {
                        State::Hover
                    } else {
                        State::Rest
                    }
                } else {
                    hover_since = None;
                    State::Rest
                }
            }
        };
        was_dragging = dragging;
        // Slow down only when nothing can happen within a frame.
        tick = if next == State::Rest && !pressed && !note_asked && !geo.armed.contains(px, py, 300.0) { IDLE_TICK } else { TICK };
        if next == state {
            // The page cannot see the pointer while the app is in the background (a background
            // window gets no mouse-moved events), so what is under it is told from here.
            if matches!(state, State::Hover | State::Listen) {
                let at = (px - placed.x, py - placed.y);
                if last_told.is_none_or(|(x, y)| (x - at.0).abs() + (y - at.1).abs() > 0.5) {
                    last_told = Some(at);
                    point(&app, at);
                }
            }
            continue;
        }
        last_told = None;
        if matches!(state, State::Note | State::Listen) && !matches!(next, State::Note | State::Listen) {
            yield_keyboard(&app);
        }
        hovering_since = if next == State::Hover { Some(now) } else { None };
        away_since = None;
        hover_since = None;
        let epoch = EPOCH.fetch_add(1, Ordering::SeqCst) + 1;
        match next {
            State::Rest => {
                tell(&app, State::Rest, &geo);
                let app = app.clone();
                thread::spawn(move || {
                    thread::sleep(SHRINK_AFTER);
                    // Only if nothing reopened it while the page was shrinking.
                    if EPOCH.load(Ordering::SeqCst) == epoch {
                        place(&app, geo.rest);
                    }
                });
            }
            State::Hover => {
                placed = padded(geo.hover, geo.edge);
                place(&app, placed);
                tell(&app, State::Hover, &geo);
            }
            State::Listen => {
                placed = padded(geo.listen, geo.edge);
                place(&app, placed);
                tell(&app, State::Listen, &geo);
                take_keyboard(&app);
            }
            State::Armed => {
                placed = padded(geo.armed, geo.edge);
                place(&app, placed);
                tell(&app, State::Armed, &geo);
            }
            State::Note => {
                placed = padded(geo.note, geo.edge);
                place(&app, placed);
                tell(&app, State::Note, &geo);
                // From listening it already has the keyboard; focusing again can bounce key status
                // and read as the reader clicking away.
                if state != State::Listen {
                    take_keyboard(&app);
                }
            }
            // The page already put itself in the swallow state when it received the drop; telling it
            // again would only race its own words.
            State::Swallow => {}
        }
        state = next;
    }
}

/// The workspace is resting and the pointer moved: the page ends its rest.
fn wake_workspace(app: &AppHandle) {
    if let Some(workspace) = app.get_webview_window("main") {
        let _ = workspace.eval("window.penumbraWake && window.penumbraWake()");
    }
}

/// Tell the page where the pointer is, in the window's coordinates.
fn point(app: &AppHandle, at: (f64, f64)) {
    if let Some(window) = app.get_webview_window(LABEL) {
        let _ = window.eval(format!("window.island && window.island.pointer && window.island.pointer({}, {})", at.0, at.1));
    }
}

/// The island takes the keyboard only while it is a field. On the main thread, as AppKit requires.
fn take_keyboard(app: &AppHandle) {
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        // Who had the keyboard, so it can be given back to exactly them.
        platform::remember_front();
        if let Some(window) = handle.get_webview_window(LABEL) {
            let _ = window.set_focus();
        }
    });
}

/// Give the keyboard back to whatever had it before, unless the workspace is up and should keep it.
fn yield_keyboard(app: &AppHandle) {
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        let workspace_up = handle
            .webview_windows()
            .iter()
            .any(|(label, w)| label != LABEL && w.is_visible().unwrap_or(false));
        if !workspace_up {
            platform::give_back();
        }
    });
}

/// Where a drag has to reach to open the island: the notch's row, 30 points wider on each side.
fn drag_target(geo: &Geometry) -> Rect {
    if geo.edge == "left" {
        Rect { x: 0.0, y: geo.rest.y - 30.0, w: geo.rest.w + 14.0, h: geo.rest.h + 60.0 }
    } else {
        Rect { x: geo.rest.x - 30.0, y: 0.0, w: geo.rest.w + 60.0, h: geo.rest.h.max(24.0) + 14.0 }
    }
}

#[derive(Clone, Copy)]
struct Press {
    x: f64,
    y: f64,
    /// The drag pasteboard's change count when the button went down, where the platform has one.
    pasteboard: Option<i64>,
}

/// Re-measure on the main thread (AppKit's screen APIs require it) and, if the island is at rest,
/// move it to where the notch now is.
fn remeasure(app: &AppHandle, state: State) {
    let handle = app.clone();
    let _ = app.run_on_main_thread(move || {
        let before = geometry();
        measure(&handle);
        let after = geometry();
        if state == State::Rest && after != before {
            if let Some(geo) = after {
                place(&handle, geo.rest);
                tell(&handle, State::Rest, &geo);
            }
        }
    });
}

#[cfg(target_os = "macos")]
mod platform {
    use super::{Geometry, Rect};
    use objc2::MainThreadMarker;
    use std::sync::atomic::{AtomicI32, Ordering};
    use objc2_app_kit::{
        NSApplication, NSApplicationActivationOptions, NSCursor, NSEvent, NSPasteboard, NSRunningApplication, NSWorkspace, NSPasteboardNameDrag, NSScreen, NSStatusWindowLevel, NSWindow,
        NSWindowCollectionBehavior,
    };
    use tauri::{AppHandle, WebviewWindow};

    /// The notch, measured from the screen that carries the menu bar. A screen without one gets a
    /// thin target at its top centre instead.
    pub fn geometry(_app: &AppHandle) -> Option<Geometry> {
        let mtm = MainThreadMarker::new()?;
        let screen = NSScreen::screens(mtm).firstObject()?;
        let frame = screen.frame();
        let top = screen.safeAreaInsets().top;
        let width = frame.size.width;
        let rest = if top > 0.0 {
            let left = screen.auxiliaryTopLeftArea().size.width;
            let right = screen.auxiliaryTopRightArea().size.width;
            Rect { x: left, y: 0.0, w: width - left - right, h: top }
        } else {
            Rect { x: width / 2.0 - 100.0, y: 0.0, w: 200.0, h: 5.0 }
        };
        let centre = rest.x + rest.w / 2.0;
        let bar = rest.h.max(24.0);
        // Icons only, so the hover shape only has to fit the status glyph below the notch (the
        // ring, the arc around it and the four dots under it); the armed one stays wide because it
        // is a drop target, and a bigger target is easier to hit.
        let hover_w = rest.w + 40.0;
        let armed_w = (rest.w + 160.0).max(340.0);
        // Wide enough for a sentence to be read back while it is typed.
        let note_w = (rest.w + 260.0).max(460.0);
        // Wide enough for the typing hint under the ring.
        let listen_w = (rest.w + 110.0).max(300.0);
        Some(Geometry {
            edge: "top",
            inset: if top > 0.0 { top } else { 0.0 },
            screen_h: frame.size.height,
            rest,
            hover: Rect { x: centre - hover_w / 2.0, y: 0.0, w: hover_w, h: bar + 76.0 },
            armed: Rect { x: centre - armed_w / 2.0, y: 0.0, w: armed_w, h: bar + 118.0 },
            note: Rect { x: centre - note_w / 2.0, y: 0.0, w: note_w, h: bar + 60.0 },
            listen: Rect { x: centre - listen_w / 2.0, y: 0.0, w: listen_w, h: bar + 116.0 },
        })
    }

    /// Above the menu bar (the notch lives in its row), on every Space, over full-screen apps, and
    /// out of the window cycle. Must run on the main thread, so it is dispatched there.
    pub fn float_above_menu_bar(app: &AppHandle, window: &WebviewWindow) {
        let window = window.clone();
        let _ = app.run_on_main_thread(move || {
            let Ok(pointer) = window.ns_window() else {
                return;
            };
            // SAFETY: Tauri hands back this window's live NSWindow, on the main thread.
            let ns: &NSWindow = unsafe { &*(pointer as *const NSWindow) };
            ns.setLevel(NSStatusWindowLevel);
            ns.setCollectionBehavior(
                NSWindowCollectionBehavior::CanJoinAllSpaces
                    | NSWindowCollectionBehavior::Stationary
                    | NSWindowCollectionBehavior::FullScreenAuxiliary
                    | NSWindowCollectionBehavior::IgnoresCycle,
            );
            ns.setHasShadow(false);
        });
    }

    /// The pointer in the same top-left, point-based space the window is placed in. AppKit measures
    /// from the bottom-left of the menu-bar screen, whose height the last measurement recorded.
    pub fn pointer(_app: &AppHandle) -> Option<(f64, f64)> {
        let at = NSEvent::mouseLocation();
        let height = super::geometry()?.screen_h;
        Some((at.x, height - at.y))
    }

    /// The drag pasteboard's change count. It moves when a drag-and-drop session begins, and only
    /// then: selecting text or moving a window never touches it.
    pub fn drag_pasteboard() -> Option<i64> {
        // SAFETY: a system constant, valid for the life of the process.
        let name = unsafe { NSPasteboardNameDrag };
        Some(NSPasteboard::pasteboardWithName(name).changeCount() as i64)
    }

    pub fn drag_began_since(at_press: Option<i64>) -> bool {
        match (at_press, drag_pasteboard()) {
            (Some(before), Some(now)) => now != before,
            _ => true,
        }
    }

    /// A drag is a held primary button. Readable without any permission.
    pub fn button_down() -> bool {
        NSEvent::pressedMouseButtons() & 1 == 1
    }

    /// The pointer disappears until the reader moves it: for a screen at rest.
    pub fn hide_pointer_until_it_moves() {
        NSCursor::setHiddenUntilMouseMoves(true);
    }

    /// The app that was in front when the island took the keyboard, by process id.
    static FRONT: AtomicI32 = AtomicI32::new(0);

    pub fn remember_front() {
        let own = std::process::id() as i32;
        if let Some(front) = NSWorkspace::sharedWorkspace().frontmostApplication() {
            let pid = front.processIdentifier();
            if pid != own {
                FRONT.store(pid, Ordering::SeqCst);
            }
        }
    }

    /// Give the keyboard back to the app the reader was in. `deactivate` alone was tried first and
    /// left no app active: macOS does not pass activation on by itself, so typing went nowhere
    /// until the reader clicked their app. Since macOS 14 activation is cooperative: the active app
    /// yields to the other one, which is then asked to come forward.
    pub fn give_back() {
        let Some(mtm) = MainThreadMarker::new() else {
            return;
        };
        let pid = FRONT.swap(0, Ordering::SeqCst);
        let target = if pid > 0 { NSRunningApplication::runningApplicationWithProcessIdentifier(pid) } else { None };
        match target {
            Some(other) => {
                NSApplication::sharedApplication(mtm).yieldActivationToApplication(&other);
                #[allow(deprecated)]
                let _ = other.activateWithOptions(NSApplicationActivationOptions::empty());
            }
            None => NSApplication::sharedApplication(mtm).deactivate(),
        }
    }
}

#[cfg(not(target_os = "macos"))]
mod platform {
    use super::{Geometry, Rect};
    use tauri::{AppHandle, WebviewWindow};

    /// No notch: the left edge, vertically centred, on the primary monitor.
    pub fn geometry(app: &AppHandle) -> Option<Geometry> {
        let monitor = app.primary_monitor().ok().flatten()?;
        let scale = monitor.scale_factor();
        let height = monitor.size().height as f64 / scale;
        let mid = height / 2.0;
        Some(Geometry {
            edge: "left",
            inset: 0.0,
            screen_h: height,
            rest: Rect { x: 0.0, y: mid - 70.0, w: 5.0, h: 140.0 },
            hover: Rect { x: 0.0, y: mid - 60.0, w: 300.0, h: 120.0 },
            armed: Rect { x: 0.0, y: mid - 100.0, w: 400.0, h: 200.0 },
            note: Rect { x: 0.0, y: mid - 30.0, w: 460.0, h: 60.0 },
            listen: Rect { x: 0.0, y: mid - 75.0, w: 320.0, h: 150.0 },
        })
    }

    pub fn float_above_menu_bar(_app: &AppHandle, _window: &WebviewWindow) {}

    /// Elsewhere the window manager moves focus on the next click; nothing to hand back.
    pub fn remember_front() {}

    pub fn give_back() {}

    pub fn hide_pointer_until_it_moves() {}

    /// No portable drag-session signal here: a press that started off the island and moved is
    /// taken as a drag.
    pub fn drag_pasteboard() -> Option<i64> {
        None
    }

    pub fn drag_began_since(_at_press: Option<i64>) -> bool {
        true
    }

    pub fn pointer(app: &AppHandle) -> Option<(f64, f64)> {
        let at = app.cursor_position().ok()?;
        let scale = app.primary_monitor().ok().flatten()?.scale_factor();
        Some((at.x / scale, at.y / scale))
    }

    #[cfg(windows)]
    pub fn button_down() -> bool {
        use windows_sys::Win32::UI::Input::KeyboardAndMouse::{GetAsyncKeyState, VK_LBUTTON};
        // SAFETY: a plain read of the asynchronous key state; no pointers involved.
        unsafe { (GetAsyncKeyState(VK_LBUTTON as i32) as u16 & 0x8000) != 0 }
    }

    /// Linux has no portable, permission-free way to read the button state across X11 and Wayland,
    /// so the island opens on hover there and takes the drop when the pointer reaches it.
    #[cfg(not(windows))]
    pub fn button_down() -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::Rect;

    #[test]
    fn a_drag_opens_the_island_only_from_the_notch_row() {
        let rest = Rect { x: 663.0, y: 0.0, w: 185.0, h: 32.0 };
        let geo = super::Geometry {
            edge: "top", inset: 32.0, screen_h: 982.0, rest,
            hover: rest, armed: Rect { x: 585.0, y: 0.0, w: 340.0, h: 150.0 }, note: rest, listen: rest,
        };
        let target = super::drag_target(&geo);
        assert!(target.contains(755.0, 20.0, 0.0), "the notch itself");
        assert!(target.contains(640.0, 40.0, 0.0), "just beside and below it");
        assert!(!target.contains(755.0, 70.0, 0.0), "a tab bar under the menu bar is not the notch");
        assert!(!target.contains(560.0, 20.0, 0.0), "the menu bar farther out is not the notch");
    }

    #[test]
    fn a_rect_contains_its_margin() {
        let r = Rect { x: 10.0, y: 0.0, w: 100.0, h: 20.0 };
        assert!(r.contains(10.0, 0.0, 0.0));
        assert!(!r.contains(5.0, 10.0, 0.0));
        assert!(r.contains(5.0, 10.0, 6.0));
    }
}
