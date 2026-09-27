"""
Tandem - Multi-Link High-Speed Internet Aggregator
Entry point.

  python main.py               — launches Tauri sidecar (RPC server only)
  python main.py --sidecar     — same as above (explicit)
  python main.py --legacy-ui   — CustomTkinter UI (fallback)
  python main.py --reset-proxy — clear orphaned proxy and exit
  python main.py --clean       — same as --reset-proxy
"""

import os
import sys
import atexit
import signal

# Ensure package root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

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
    signal.signal(signal.SIGINT,  _emergency_cleanup)
    signal.signal(signal.SIGTERM, _emergency_cleanup)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _emergency_cleanup)
except Exception:
    pass


def run_sidecar():
    """Start the JSON-RPC WebSocket sidecar server (no GUI)."""
    import asyncio
    from turbobond.core.rpc_server import TandemRPCServer

    # Promote AppUserModelID so the Tauri window groups correctly
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "com.tandem.network.aggregator.v1"
            )
        except Exception:
            pass

    SystemProxyConfig.cleanup_orphaned_proxy()

    server = TandemRPCServer()
    try:
        asyncio.run(server.run())
    finally:
        _emergency_cleanup()


def run_legacy_ui():
    """Launch the CustomTkinter UI (fallback / development)."""
    from turbobond.core.engine_manager import is_elevated, relaunch_as_admin

    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "com.tandem.network.aggregator.v1"
            )
        except Exception:
            pass

    if "--admin" in sys.argv:
        if not is_elevated():
            relaunch_as_admin()

    SystemProxyConfig.cleanup_orphaned_proxy()

    from turbobond.ui.main_window import MainWindow
    try:
        app = MainWindow()
        app.mainloop()
    finally:
        _emergency_cleanup()


def main():
    # CLI flag handling
    args = sys.argv[1:]

    if "--reset-proxy" in args or "--clean" in args:
        print("[Tandem] Resetting system proxy to Direct Internet…")
        SystemProxyConfig.cleanup_orphaned_proxy(force=True)
        print("[Tandem] Done. Internet traffic is direct.")
        return

    if "--legacy-ui" in args:
        run_legacy_ui()
        return

    # Default: sidecar mode (--sidecar flag is optional)
    run_sidecar()


if __name__ == "__main__":
    main()
