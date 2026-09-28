use std::{io::{BufRead, BufReader, Write}, process::{Child, Command, Stdio}, sync::{mpsc, Mutex}, time::{Duration, Instant}};
use tauri::{AppHandle, Manager};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use serde::{Deserialize, Serialize};
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

#[derive(Clone, Deserialize, Serialize)]
struct Connection { url: String, token: String }
struct Sidecar { child: Child, connection: Connection }
#[derive(Default)]
struct SidecarState(Mutex<Option<Sidecar>>);

#[cfg(target_os = "windows")]
fn ensure_direct_internet() {
    let _ = Command::new("cmd")
        .args(["/c", "reg add \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\" /v ProxyEnable /t REG_DWORD /d 0 /f"])
        .creation_flags(0x08000000)
        .output();
    let _ = Command::new("cmd")
        .args(["/c", "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\" /v TandemProxyBackup /f"])
        .creation_flags(0x08000000)
        .output();
}

fn sidecar_command(app: &AppHandle) -> Result<Command, String> {
    let name = if cfg!(windows) { "tandem-sidecar.exe" } else { "tandem-sidecar" };

    // Check candidate paths for pre-packaged sidecar binary
    let candidates = [
        app.path().resource_dir().ok().map(|d| d.join("sidecar").join(name)),
        std::env::current_exe().ok().and_then(|e| e.parent().map(|p| p.join(name))),
        std::env::current_exe().ok().and_then(|e| e.parent().map(|p| p.join("sidecar").join(name))),
    ];

    for candidate in candidates.into_iter().flatten() {
        if candidate.is_file() {
            let mut cmd = Command::new(candidate);
            cmd.arg("--sidecar");
            return Ok(cmd);
        }
    }

    // Fall back to python script
    let roots = [
        std::env::current_exe().ok().and_then(|e| e.parent().map(|p| p.to_path_buf())),
        std::env::current_exe().ok().and_then(|e| e.parent().and_then(|p| p.parent()).map(|p| p.to_path_buf())),
        std::env::current_exe().ok().and_then(|e| e.parent().and_then(|p| p.parent()).and_then(|p| p.parent()).map(|p| p.to_path_buf())),
        std::env::current_exe().ok().and_then(|e| e.parent().and_then(|p| p.parent()).and_then(|p| p.parent()).and_then(|p| p.parent()).map(|p| p.to_path_buf())),
        Some(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")),
    ];

    for root in roots.into_iter().flatten() {
        let script = root.join("main.py");
        if script.is_file() {
            let python = std::env::var_os("TANDEM_PYTHON").unwrap_or_else(|| "python".into());
            let mut cmd = Command::new(python);
            cmd.arg(&script).arg("--sidecar").current_dir(root);
            return Ok(cmd);
        }
    }

    Err("Packaged backend is missing. Reinstall Tandem.".into())
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
            #[cfg(target_os = "windows")]
            ensure_direct_internet();
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
            #[cfg(target_os = "windows")]
            ensure_direct_internet();
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
        match event {
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
                stop_sidecar(&app.state::<SidecarState>());
                #[cfg(target_os = "windows")]
                ensure_direct_internet();
            }
            _ => {}
        }
    });
}
