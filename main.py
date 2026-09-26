"""
Tandem - Multi-Link High-Speed Internet Aggregator
Entry point for Tandem Desktop.
"""

import os
import sys
import atexit
import signal

# Ensure package root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from turbobond.ui.main_window import MainWindow
from turbobond.core.engine_manager import is_elevated, relaunch_as_admin
from turbobond.core.system_proxy import SystemProxyConfig


def _emergency_cleanup(signum=None, frame=None):
    """Guaranteed fallback to restore direct internet on process exit or signal."""
    try:
        SystemProxyConfig.cleanup_orphaned_proxy()
    except Exception:
        pass
    if signum is not None:
        sys.exit(0)


# Register process exit and signal listeners
atexit.register(_emergency_cleanup)
try:
    signal.signal(signal.SIGINT, _emergency_cleanup)
    signal.signal(signal.SIGTERM, _emergency_cleanup)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _emergency_cleanup)
except Exception:
    pass


def main():
    # CLI command: python main.py --reset-proxy (or --clean)
    if "--reset-proxy" in sys.argv or "--clean" in sys.argv:
        print("[Tandem] Resetting system proxy to Direct Internet...")
        SystemProxyConfig.cleanup_orphaned_proxy(force=True)
        print("[Tandem] System proxy successfully disabled. Internet traffic is direct.")
        return

    # Clean any orphaned proxy from prior crashes before starting
    SystemProxyConfig.cleanup_orphaned_proxy()

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

    try:
        app = MainWindow()
        app.mainloop()
    finally:
        _emergency_cleanup()


if __name__ == "__main__":
    main()

