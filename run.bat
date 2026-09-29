@echo off
setlocal
cd /d "%~dp0"

set "APP="
if exist "tandem-ui\src-tauri\target\release\tandem.exe" set "APP=tandem-ui\src-tauri\target\release\tandem.exe"
if not defined APP if exist "tandem-ui\src-tauri\target\x86_64-pc-windows-gnu\release\tandem.exe" set "APP=tandem-ui\src-tauri\target\x86_64-pc-windows-gnu\release\tandem.exe"

if not defined APP (
    echo [Tandem] Building the desktop app and bundled backend...
    python build_exe.py
    if errorlevel 1 exit /b 1
)

if not defined APP if exist "tandem-ui\src-tauri\target\release\tandem.exe" set "APP=tandem-ui\src-tauri\target\release\tandem.exe"
if not defined APP if exist "tandem-ui\src-tauri\target\x86_64-pc-windows-gnu\release\tandem.exe" set "APP=tandem-ui\src-tauri\target\x86_64-pc-windows-gnu\release\tandem.exe"
if not defined APP (
    echo [Tandem] No executable found in the standard release targets.
    echo [Tandem] Open the installer under tandem-ui\src-tauri\target instead.
    exit /b 1
)

start "" "%APP%"
