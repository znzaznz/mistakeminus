#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProc(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendProc(Mutex::new(None)))
        .setup(|app| {
            let script = app
                .path()
                .resource_dir()
                .ok()
                .and_then(|d| {
                    let p = d.join("desktop").join("start-backend.ps1");
                    if p.exists() { Some(p) } else { None }
                });

            // 开发模式：从仓库 desktop/ 脚本启动
            let dev_script = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
                .join("desktop")
                .join("start-backend.ps1");

            let ps1 = script.filter(|p| p.exists()).unwrap_or(dev_script);
            if ps1.exists() {
                if let Ok(child) = Command::new("powershell")
                    .args([
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        ps1.to_str().unwrap_or(""),
                    ])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn()
                {
                    if let Some(state) = app.try_state::<BackendProc>() {
                        *state.0.lock().unwrap() = Some(child);
                    }
                }
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.app_handle().try_state::<BackendProc>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn main() {
    run();
}
