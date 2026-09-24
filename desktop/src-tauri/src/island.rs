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
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    Rest,
    Hover,
    Armed,
    Swallow,
}

impl State {
    fn name(self) -> &'static str {
        match self {
            State::Rest => "collapsed",
            State::Hover => "hover",
            State::Armed => "armed",
            State::Swallow => "swallow",
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

/// The page asks for the island to close (after a swallow). Picked up by the pointer loop.
pub fn request_rest() {
    REST_REQUESTED.store(true, Ordering::SeqCst);
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
        let next = match state {
            _ if rest_asked => State::Rest,
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
            _ if dragging && geo.armed.contains(px, py, 70.0) => State::Armed,
            State::Armed | State::Hover => {
                let region = if state == State::Armed { geo.armed } else { geo.hover };
                if region.contains(px, py, 6.0) {
                    away_since = None;
                    state
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
        tick = if next == State::Rest && !pressed && !geo.armed.contains(px, py, 300.0) { IDLE_TICK } else { TICK };
        if next == state {
            continue;
        }
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
                place(&app, padded(geo.hover, geo.edge));
                tell(&app, State::Hover, &geo);
            }
            State::Armed => {
                place(&app, padded(geo.armed, geo.edge));
                tell(&app, State::Armed, &geo);
            }
            // The page already put itself in the swallow state when it received the drop; telling it
            // again would only race its own words.
            State::Swallow => {}
        }
        state = next;
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
    use objc2_app_kit::{
        NSEvent, NSPasteboard, NSPasteboardNameDrag, NSScreen, NSStatusWindowLevel, NSWindow,
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
        // Icons only, so the hover shape only has to fit the ring below the notch; the armed one
        // stays wide because it is a drop target, and a bigger target is easier to hit.
        let hover_w = rest.w + 40.0;
        let armed_w = (rest.w + 160.0).max(340.0);
        Some(Geometry {
            edge: "top",
            inset: if top > 0.0 { top } else { 0.0 },
            screen_h: frame.size.height,
            rest,
            hover: Rect { x: centre - hover_w / 2.0, y: 0.0, w: hover_w, h: bar + 52.0 },
            armed: Rect { x: centre - armed_w / 2.0, y: 0.0, w: armed_w, h: bar + 118.0 },
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
        })
    }

    pub fn float_above_menu_bar(_app: &AppHandle, _window: &WebviewWindow) {}

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
    fn a_rect_contains_its_margin() {
        let r = Rect { x: 10.0, y: 0.0, w: 100.0, h: 20.0 };
        assert!(r.contains(10.0, 0.0, 0.0));
        assert!(!r.contains(5.0, 10.0, 0.0));
        assert!(r.contains(5.0, 10.0, 6.0));
    }
}
