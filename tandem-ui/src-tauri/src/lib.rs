use std::{io::{BufRead, BufReader, Write}, process::{Child, Command, Stdio}, sync::{mpsc, Mutex}, time::{Duration, Instant}};
use tauri::{AppHandle, Manager, State};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use serde::{Deserialize, Serialize};
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[derive(Clone, Deserialize, Serialize)]
struct Connection { url: String, token: String }
struct Sidecar { child: Child, connection: Connection }
#[derive(Default)]
struct SidecarState(Mutex<Option<Sidecar>>);

fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    if cfg!(debug_assertions) {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let python = std::env::var_os("TANDEM_PYTHON").unwrap_or_else(|| "python".into());
        let mut cmd = Command::new(python);
        cmd.arg(root.join("main.py")).arg("--sidecar").current_dir(root);
        Ok(cmd)
    } else {
        let name = if cfg!(windows) { "tandem-sidecar.exe" } else { "tandem-sidecar" };
        let path = app.path().resource_dir().map_err(|e| e.to_string())?.join("sidecar").join(name);
        if !path.is_file() { return Err("Packaged backend is missing. Reinstall Tandem.".into()); }
        let mut cmd = Command::new(path);
        cmd.arg("--sidecar");
        Ok(cmd)
    }
}

fn stop_child(child: &mut Child) {
    if let Some(mut input) = child.stdin.take() { let _ = input.write_all(b"shutdown\n"); }
    let deadline = Instant::now() + Duration::from_secs(15);
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return,
            Err(_) => break,
            _ if Instant::now() >= deadline => break,
            _ => std::thread::sleep(Duration::from_millis(50)),
        }
    }
    let _ = child.kill();
    let _ = child.wait();
}

fn connect_sidecar(app: &AppHandle, state: &SidecarState) -> Result<Connection, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(sidecar) = guard.as_mut() {
        if sidecar.child.try_wait().map_err(|e| e.to_string())?.is_none() {
            return Ok(sidecar.connection.clone());
        }
        *guard = None;
    }
    let mut cmd = sidecar_command(app)?;
    cmd.env("TANDEM_RPC_PORT", "0").env("TANDEM_MANAGED", "1")
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit());
    #[cfg(target_os = "windows")]
    cmd.creation_flags(0x08000000);
    let mut child = cmd.spawn().map_err(|e| format!("Cannot launch backend: {e}"))?;
    let output = child.stdout.take().ok_or("Backend output pipe unavailable")?;
    let (tx, rx) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut sent = false;
        for line in BufReader::new(output).lines() {
            let Ok(line) = line else { break };
            if !sent {
                if let Ok(info) = serde_json::from_str::<Connection>(&line) {
                    let _ = tx.send(info);
                    sent = true;
                }
            }
            // Keep draining stdout; never print the readiness token.
        }
    });
    match rx.recv_timeout(Duration::from_secs(20)) {
        Ok(connection) => {
            *guard = Some(Sidecar { child, connection: connection.clone() });
            Ok(connection)
        }
        Err(_) => {
            stop_child(&mut child);
            Err("Backend did not become ready. Check Python dependencies or reinstall Tandem.".into())
        }
    }
}

#[tauri::command]
async fn sidecar_connection(app: AppHandle) -> Result<Connection, String> {
    tauri::async_runtime::spawn_blocking(move || connect_sidecar(&app, &app.state::<SidecarState>()))
        .await.map_err(|e| e.to_string())?
}

fn stop_sidecar(state: &SidecarState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut sidecar) = guard.take() { stop_child(&mut sidecar.child); }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(SidecarState::default())
        .setup(|app| {
            if let Some(icon) = app.default_window_icon().cloned() {
                TrayIconBuilder::new().icon(icon).tooltip("Tandem")
                    .on_tray_icon_event(|tray, event| {
                        if let TrayIconEvent::Click { .. } = event {
                            if let Some(window) = tray.app_handle().get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }).build(app)?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![sidecar_connection])
        .build(tauri::generate_context!())
        .expect("Cannot initialize Tandem");
    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { .. } = event {
            stop_sidecar(&app.state::<SidecarState>());
        }
    });
}
