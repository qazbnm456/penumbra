// Hide the console window a release build would otherwise open next to the app on Windows.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    penumbra_desktop_lib::run()
}
