"""
TurboBond - PyInstaller Automated Build Script
Builds a standalone executable with embedded engine binaries and app icons.
Supports both Windows and Linux.
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEP = ";" if sys.platform.startswith("win") else ":"


def build():
    platform_name = "Windows" if sys.platform.startswith("win") else "Linux"
    print(f"=== Building TurboBond for {platform_name} ===")

    bin_dir = os.path.join(BASE_DIR, "bin")
    assets_dir = os.path.join(BASE_DIR, "turbobond", "assets")
    icon_ico = os.path.join(assets_dir, "icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=TurboBond",
        "--windowed",
        f"--add-data={bin_dir}{SEP}bin",
        f"--add-data={assets_dir}{SEP}turbobond/assets",
        "--hidden-import=customtkinter",
        "--hidden-import=pystray",
        "--hidden-import=PIL",
        "--clean",
        "--noconfirm",
        "main.py"
    ]

    # Windows-specific options
    if sys.platform.startswith("win"):
        cmd.insert(4, "--uac-admin")
        if os.path.exists(icon_ico):
            cmd.insert(4, f"--icon={icon_ico}")

    print("Running PyInstaller command:")
    print(" ".join(cmd))

    res = subprocess.run(cmd, cwd=BASE_DIR)
    if res.returncode == 0:
        print(f"\n[OK] Build Successful!")
        print(f"Output located at: {os.path.join(BASE_DIR, 'dist', 'TurboBond')}")
    else:
        print(f"\n[FAILED] Build failed with exit code: {res.returncode}")


if __name__ == "__main__":
    build()
