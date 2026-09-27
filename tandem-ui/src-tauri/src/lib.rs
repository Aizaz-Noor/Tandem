// Tandem — Tauri 2.0 Rust backend
// Launches the Python sidecar and exposes Tauri commands.
// The React frontend communicates with the sidecar directly via WebSocket (ws://127.0.0.1:7878).
// The Rust layer handles: window management, sidecar lifecycle, and system tray.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{AppHandle, Manager, State};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

// ─── Sidecar state ────────────────────────────────────────────────────────────

struct SidecarState(Mutex<Option<std::process::Child>>);

// ─── Tauri commands ───────────────────────────────────────────────────────────

/// Start the Python sidecar process (main.py --sidecar).
#[tauri::command]
fn start_sidecar(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(()); // already running
    }

    // Resolve the Python interpreter path and main.py location
    let python = find_python(&app);
    let main_script = find_main_script(&app);
    let script_dir = main_script.parent().unwrap_or(std::path::Path::new("."));

    #[cfg(target_os = "windows")]
    let child = {
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        std::process::Command::new(&python)
            .args([main_script.to_str().unwrap_or("main.py"), "--sidecar"])
            .current_dir(script_dir)
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .map_err(|e| format!("Failed to start Python sidecar: {e}"))?
    };

    #[cfg(not(target_os = "windows"))]
    let child = std::process::Command::new(&python)
        .args([main_script.to_str().unwrap_or("main.py"), "--sidecar"])
        .spawn()
        .map_err(|e| format!("Failed to start Python sidecar: {e}"))?;

    *guard = Some(child);
    Ok(())
}

/// Kill the Python sidecar.
#[tauri::command]
fn stop_sidecar(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = guard.take() {
        child.kill().ok();
    }
    Ok(())
}

/// Check whether the sidecar is alive.
#[tauri::command]
fn sidecar_alive(state: State<'_, SidecarState>) -> bool {
    let mut guard = match state.0.lock() {
        Ok(g) => g,
        Err(_) => return false,
    };
    if let Some(ref mut child) = *guard {
        match child.try_wait() {
            Ok(None) => return true,   // still running
            _ => { *guard = None; }     // exited or error
        }
    }
    false
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

fn find_main_script(app: &AppHandle) -> std::path::PathBuf {
    let resource_dir = app
        .path()
        .resource_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."));

    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| std::path::PathBuf::from("."));

    let candidates = [
        resource_dir.join("main.py"),
        exe_dir.join("main.py"),
        exe_dir.join("../../../main.py"),
        exe_dir.join("../../../../main.py"),
        std::path::PathBuf::from("main.py"),
        std::path::PathBuf::from("../../main.py"),
        std::path::PathBuf::from("../../../main.py"),
        std::path::PathBuf::from(r"E:\Projects\TurboBond\main.py"),
    ];

    for path in &candidates {
        if path.exists() {
            if let Ok(canon) = path.canonicalize() {
                return canon;
            }
            return path.clone();
        }
    }

    std::path::PathBuf::from("main.py")
}

fn find_python(app: &AppHandle) -> std::path::PathBuf {
    // Prefer a bundled sidecar exe named `tandem-sidecar` or `python`
    let resource_dir = app
        .path()
        .resource_dir()
        .unwrap_or_else(|_| std::path::PathBuf::from("."));

    let candidates = [
        resource_dir.join("python.exe"),
        resource_dir.join("tandem-sidecar.exe"),
        // Fall back to system Python on Windows
        std::path::PathBuf::from("C:/msys64/ucrt64/bin/python.exe"),
        std::path::PathBuf::from("python"),
    ];

    for path in &candidates {
        if path.exists() || path.file_name().is_some_and(|n| n == "python") {
            return path.clone();
        }
    }

    std::path::PathBuf::from("python")
}

// ─── Main ─────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            // System tray
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().cloned().unwrap())
                .tooltip("Tandem — Multi-Link Bonding")
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click { .. } = event {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // Auto-start the Python sidecar
            let handle = app.handle().clone();
            let state = app.state::<SidecarState>();
            if let Err(e) = start_sidecar(handle.clone(), state) {
                eprintln!("[Tandem] Sidecar start failed: {e}");
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Kill sidecar on window close
                let state = window.app_handle().state::<SidecarState>();
                let mut guard = state.0.lock().unwrap();
                if let Some(mut child) = guard.take() {
                    child.kill().ok();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![start_sidecar, stop_sidecar, sidecar_alive])
        .run(tauri::generate_context!())
        .expect("error while running Tandem application");
}
