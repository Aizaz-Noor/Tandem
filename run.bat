@echo off
setlocal
cd /d "%~dp0"
if exist "tandem-ui\src-tauri\target\release\tandem.exe" (
    start "" "tandem-ui\src-tauri\target\release\tandem.exe"
    exit /b 0
)
echo [Tandem] Building the desktop app and bundled backend...
python build_exe.py
if errorlevel 1 (
    echo [Tandem] Build failed. See the error above.
    exit /b 1
)
if not exist "tandem-ui\src-tauri\target\release\tandem.exe" (
    echo [Tandem] Build output is in a custom target directory. Open its installer.
    exit /b 1
)
start "" "tandem-ui\src-tauri\target\release\tandem.exe"
