"""
Tandem - Automated Build Script
Builds the standalone Tauri 2.0 executable (recommended) or legacy PyInstaller bundle.
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TAURI_DIR = os.path.join(BASE_DIR, "tandem-ui")
SEP = ";" if sys.platform.startswith("win") else ":"


def build_tauri():
    print("=== Building Tandem (Tauri 2.0 + React + Tailwind) ===")
    env = os.environ.copy()
    cargo_bin = os.path.expanduser(r"~\.cargo\bin")
    ucrt_bin = r"C:\msys64\ucrt64\bin"
    extra_paths = [p for p in [cargo_bin, ucrt_bin] if os.path.exists(p)]
    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

    cmd = ["npm", "run", "tauri", "build", "--", "--no-bundle"]
    print(f"Running: {' '.join(cmd)} in {TAURI_DIR}")
    res = subprocess.run(cmd, cwd=TAURI_DIR, env=env, shell=True)
    if res.returncode == 0:
        exe_path = os.path.join(TAURI_DIR, "src-tauri", "target", "release", "tandem.exe")
        print("\n[OK] Tauri 2.0 Build Successful!")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Binary: {exe_path} ({size_mb:.2f} MB)")
    else:
        print(f"\n[FAILED] Tauri build failed with exit code: {res.returncode}")


def build_pyinstaller():
    print("=== Building Tandem Legacy Executable (PyInstaller) ===")
    bin_dir = os.path.join(BASE_DIR, "bin")
    assets_dir = os.path.join(BASE_DIR, "turbobond", "assets")
    icon_ico = os.path.join(assets_dir, "icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Tandem",
        "--windowed",
        f"--add-data={bin_dir}{SEP}bin",
        f"--add-data={assets_dir}{SEP}turbobond/assets",
        "--hidden-import=customtkinter",
        "--hidden-import=pystray",
        "--hidden-import=PIL",
        "--hidden-import=websockets",
        "--clean",
        "--noconfirm",
        "main.py"
    ]

    if sys.platform.startswith("win"):
        cmd.insert(4, "--uac-admin")
        if os.path.exists(icon_ico):
            cmd.insert(4, f"--icon={icon_ico}")

    print("Running PyInstaller command:")
    print(" ".join(cmd))
    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        print(f"\n[OK] Build Successful!")
        print(f"Output: {os.path.join(BASE_DIR, 'dist', 'Tandem')}")
    else:
        print(f"\n[FAILED] PyInstaller build failed with exit code: {res.returncode}")


def main():
    if "--pyinstaller" in sys.argv or "--legacy" in sys.argv:
        build_pyinstaller()
    else:
        build_tauri()


if __name__ == "__main__":
    main()
