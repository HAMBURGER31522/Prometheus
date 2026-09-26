// Prevents an extra console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Write;
use std::net::TcpListener;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Child;
use std::sync::Mutex;

use tauri::Manager;

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

struct Backend {
    port: u16,
    token: String,
    child: Mutex<Option<Child>>,
}

fn free_port() -> u16 {
    TcpListener::bind("127.0.0.1:0")
        .expect("bind ephemeral port")
        .local_addr()
        .expect("local addr")
        .port()
}

fn random_token() -> String {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).expect("os randomness");
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

fn spawn_backend(app: &tauri::AppHandle, port: u16, token: &str) -> Child {
    let resource_dir = app
        .path()
        .resource_dir()
        .expect("resource dir")
        .join("resources");
    let runtime = resource_dir.join("runtime");
    let python = runtime.join("python").join("python.exe");
    let mut path = std::env::var("PATH").unwrap_or_default();
    path = format!(
        "{}\\node;{}\\ffmpeg;{}",
        runtime.display(),
        runtime.display(),
        path
    );

    let config_dir = app.path().app_config_dir().expect("config dir");

    std::process::Command::new(&python)
        .args([
            "-m",
            "prometheus.server",
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--token",
            token,
            "--config-dir",
            &config_dir.display().to_string(),
            "--runtime-dir",
            &runtime.display().to_string(),
        ])
        .env("PYTHONUTF8", "1")
        .env("PATH", &path)
        .creation_flags(CREATE_NO_WINDOW) // children inherit the hidden console
        .spawn()
        .expect("failed to spawn the bundled backend")
}

#[tauri::command]
fn backend_info(backend: tauri::State<'_, Backend>) -> serde_json::Value {
    serde_json::json!({ "port": backend.port, "token": backend.token })
}

fn kill_tree(child: &mut Option<Child>) {
    if let Some(process) = child.as_mut() {
        let pid = process.id();
        let _ = std::process::Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        let _ = process.wait();
    }
}

fn main() {
    let port = free_port();
    let token = random_token();
    let backend = Backend { port, token, child: Mutex::new(None) };

    tauri::Builder::default()
        .manage(backend)
        .invoke_handler(tauri::generate_handler![backend_info])
        .setup(|app| {
            let handle = app.handle().clone();
            let state: tauri::State<'_, Backend> = handle.state();
            let child = spawn_backend(&handle, state.port, &state.token);
            *state.child.lock().expect("backend lock") = Some(child);

            // Port hand-off for acceptance scripts (PLAN 8.1).
            if let Ok(dir) = std::env::var("PROMETHEUS_TEST_DATA_DIR") {
                let logs = PathBuf::from(dir).join("logs");
                let _ = std::fs::create_dir_all(&logs);
                if let Ok(mut file) = std::fs::File::create(logs.join("backend.port")) {
                    let _ = writeln!(file, "{}", state.port);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let state: tauri::State<'_, Backend> = app_handle.state();
                kill_tree(&mut state.child.lock().expect("backend lock"));
            }
        });
}
