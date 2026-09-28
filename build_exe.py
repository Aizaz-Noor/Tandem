"""Build a self-contained desktop installer, including the Python sidecar."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
UI = ROOT / "tandem-ui"


def build_sidecar():
    separator = ";" if os.name == "nt" else ":"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir",
        "--name", "tandem-sidecar", "--console", "--collect-all", "websockets",
        "--add-data", f"{ROOT / 'bin'}{separator}bin", str(ROOT / "main.py")], cwd=ROOT, check=True)
    directory = ROOT / "dist" / "tandem-sidecar"
    config = {"bundle": {"resources": {str(directory).replace("\\", "/") + "/": "sidecar/"}}}
    path = UI / "src-tauri" / "tauri.release.generated.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    executable = directory / ("tandem-sidecar.exe" if os.name == "nt" else "tandem-sidecar")
    subprocess.run([str(executable), "--check"], cwd=ROOT, check=True)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidecar-only", action="store_true")
    parser.add_argument("--legacy", "--pyinstaller", action="store_true", dest="legacy")
    args = parser.parse_args()
    if args.legacy:
        separator = ";" if os.name == "nt" else ":"
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--name", "Tandem-Legacy",
            "--add-data", f"{ROOT / 'bin'}{separator}bin", "--add-data", f"{ROOT / 'turbobond/assets'}{separator}turbobond/assets",
            str(ROOT / "scripts/legacy_main.py")], cwd=ROOT, check=True)
        return
    config = build_sidecar()
    if args.sidecar_only:
        return
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("Node.js/npm is required to build the desktop")
    subprocess.run([npm, "run", "tauri", "--", "build", "--config", str(config)], cwd=UI, check=True)

if __name__ == "__main__":
    main()
