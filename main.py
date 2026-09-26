"""
Tandem - Multi-Link High-Speed Internet Aggregator
Entry point for Tandem Desktop.
"""

import os
import sys

# Ensure package root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from turbobond.ui.main_window import MainWindow
from turbobond.core.engine_manager import is_elevated, relaunch_as_admin


def main():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.tandem.network.aggregator.v1")
        except Exception:
            pass

    # If run with --admin flag, force elevation immediately
    if "--admin" in sys.argv:
        if not is_elevated():
            relaunch_as_admin()

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
