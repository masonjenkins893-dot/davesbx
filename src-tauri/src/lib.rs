// DAVESBX — Tauri library entry point

use std::process::{Command, Child};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[tauri::command]
fn restart_backend(state: tauri::State<BackendProcess>) -> String {
    let mut backend = state.0.lock().unwrap();
    if let Some(ref mut child) = *backend {
        let _ = child.kill();
    }
    match Command::new("davesbx-backend.exe").spawn() {
        Ok(new_child) => {
            *backend = Some(new_child);
            "Backend restarted".to_string()
        }
        Err(e) => format!("Failed to restart: {}", e),
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let resource_path = app
                .path()
                .resolve("davesbx-backend.exe", tauri::path::BaseDirectory::Resource)
                .expect("Failed to find backend executable");

            let child = Command::new(&resource_path)
                .spawn()
                .expect("Failed to start DAVESBX backend");

            let state: tauri::State<BackendProcess> = app.state();
            *state.0.lock().unwrap() = Some(child);

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state: tauri::State<BackendProcess> = window.app_handle().state();
                let mut backend = state.0.lock().unwrap();
                if let Some(ref mut child) = *backend {
                    let _ = child.kill();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![restart_backend])
        .run(tauri::generate_context!())
        .expect("Error running DAVESBX");
}
