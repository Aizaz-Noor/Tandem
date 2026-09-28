"""Frozen legacy UI entry point."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import run_legacy_ui
if __name__ == "__main__":
    run_legacy_ui()
