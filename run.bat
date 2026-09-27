@echo off
setlocal
cd /d "%~dp0"

echo [Tandem] Starting application...
if exist "tandem-ui\src-tauri\target\release\tandem.exe" (
    start "" "tandem-ui\src-tauri\target\release\tandem.exe"
) else (
    echo [Tandem] Binary not found. Building release executable...
    C:\msys64\ucrt64\bin\python.exe build_exe.py
    if exist "tandem-ui\src-tauri\target\release\tandem.exe" (
        start "" "tandem-ui\src-tauri\target\release\tandem.exe"
    )
)
