"""
TurboBond - Engine Process Supervisor
Manages lifecycle of the underlying mqvpn binary, handles elevation checks,
and parses real-time tunnel status events.
"""

import os
import sys
import time
import shutil
import threading
import subprocess
from enum import Enum
from typing import List, Callable, Optional


class TunnelState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


def is_elevated() -> bool:
    """Check if current process has Administrator/root privileges."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except Exception:
        return False


def relaunch_as_admin():
    """Relaunch current script/executable with elevated privileges."""
    if sys.platform.startswith("win"):
        import ctypes
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{ arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        sys.exit(0)
    else:
        # Linux: re-exec with pkexec or sudo
        exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        args = sys.argv[1:]
        for elevate_cmd in ["pkexec", "sudo"]:
            if shutil.which(elevate_cmd):
                os.execvp(elevate_cmd, [elevate_cmd, exe, script] + args)
        print("[Engine] No elevation method found. Please run as root.", file=sys.stderr)


def locate_engine_binary() -> Optional[str]:
    """Find mqvpn executable in project bin/, PyInstaller bundle, or system PATH."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = []
    
    # Check PyInstaller bundle directory
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, "_MEIPASS", exe_dir)
        candidates.extend([
            os.path.join(meipass, "bin", "mqvpn.exe"),
            os.path.join(exe_dir, "_internal", "bin", "mqvpn.exe"),
            os.path.join(exe_dir, "bin", "mqvpn.exe"),
            os.path.join(meipass, "bin", "mqvpn"),
            os.path.join(exe_dir, "_internal", "bin", "mqvpn")
        ])

    if sys.platform.startswith("win"):
        candidates.extend([
            os.path.join(base_dir, "bin", "mqvpn.exe"),
            os.path.join(os.getcwd(), "bin", "mqvpn.exe"),
            shutil.which("mqvpn.exe")
        ])
    else:
        candidates.extend([
            os.path.join(base_dir, "bin", "mqvpn"),
            "/usr/local/bin/mqvpn",
            "/usr/bin/mqvpn",
            shutil.which("mqvpn")
        ])

    for candidate in candidates:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK if not sys.platform.startswith("win") else os.R_OK):
            return os.path.abspath(candidate)
    return None


class EngineManager:
    """Supervises the mqvpn background tunnel process."""

    def __init__(self, on_state_change: Optional[Callable[[TunnelState, str], None]] = None):
        self.on_state_change = on_state_change
        self.state = TunnelState.DISCONNECTED
        self.process: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self._timeout_thread: Optional[threading.Thread] = None
        self._stop_requested = False
        self.last_log_line = ""
        self.auto_reconnect = False
        self._last_start_args = None
        from collections import deque
        self.log_buffer = deque(maxlen=200)

    def _set_state(self, new_state: TunnelState, message: str = ""):
        self.state = new_state
        if self.on_state_change:
            self.on_state_change(new_state, message)

    def start(
        self,
        server_host: str,
        server_port: int,
        auth_key: str,
        adapter_names: List[str],
        scheduler: str = "wlb",
        insecure: bool = True,
        dns_servers: Optional[List[str]] = None
    ) -> bool:
        """Start the mqvpn bonding tunnel."""
        if self.process and self.process.poll() is None:
            return True  # Already running

        bin_path = locate_engine_binary()
        if not bin_path:
            self._set_state(TunnelState.ERROR, "Engine binary (mqvpn) not found in bin/")
            return False

        if not adapter_names:
            self._set_state(TunnelState.ERROR, "No active network adapters selected for bonding")
            return False

        cmd = [
            bin_path,
            "--mode", "client",
            "--server", f"{server_host}:{server_port}",
            "--auth-key", auth_key,
            "--scheduler", scheduler
        ]

        for adapter in adapter_names:
            cmd.extend(["--path", adapter])

        if insecure:
            cmd.append("--insecure")

        if dns_servers:
            for d in dns_servers:
                cmd.extend(["--dns", d])

        self._last_start_args = {
            'server_host': server_host, 'server_port': server_port,
            'auth_key': auth_key, 'adapter_names': adapter_names,
            'scheduler': scheduler, 'insecure': insecure, 'dns_servers': dns_servers
        }
        self._stop_requested = False
        self._set_state(TunnelState.CONNECTING, f"Connecting via {len(adapter_names)} adapters...")

        creationflags = 0
        if sys.platform.startswith("win"):
            # Hide console window if spawning detached
            creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

        try:
            bin_dir = os.path.dirname(bin_path)
            self.process = subprocess.Popen(
                cmd,
                cwd=bin_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creationflags
            )

            self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self.reader_thread.start()

            # Start connection timeout watchdog
            self._timeout_thread = threading.Thread(target=self._connection_timeout_watchdog, daemon=True)
            self._timeout_thread.start()

            return True

        except Exception as e:
            self._set_state(TunnelState.ERROR, f"Launch failed: {str(e)}")
            return False

    def _connection_timeout_watchdog(self, timeout: int = 30):
        """Transition to ERROR if not connected within timeout seconds."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_requested or self.state == TunnelState.CONNECTED:
                return
            if self.state in [TunnelState.ERROR, TunnelState.DISCONNECTED]:
                return
            time.sleep(1)
        # Timed out
        if self.state == TunnelState.CONNECTING:
            self._set_state(TunnelState.ERROR, f"Connection timed out after {timeout}s. Check server address and firewall.")
            self.stop()

    def stop(self):
        """Gracefully terminate the tunnel process."""
        self._stop_requested = True
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception as e:
                print(f"[Engine] Stop error: {e}", file=sys.stderr)
            finally:
                self.process = None

        self._set_state(TunnelState.DISCONNECTED, "Disconnected")

    def _read_output(self):
        """Continuously read process stdout/stderr to detect connection status."""
        proc = self.process
        if proc is None:
            return
        while proc.poll() is None:
            try:
                line = proc.stdout.readline()
            except Exception:
                break
            if not line:
                break
            line_str = line.strip()
            self.last_log_line = line_str
            self.log_buffer.append(line_str)

            lower = line_str.lower()
            # 1. Successful connection indicators
            if any(k in lower for k in ["ready", "connected to server", "interface up", "tunnel active"]):
                if self.state != TunnelState.CONNECTED:
                    self._set_state(TunnelState.CONNECTED, "TurboBond Active")
            # 2. Reconnecting state indicators
            elif "reconnecting" in lower:
                if self.state != TunnelState.RECONNECTING:
                    self._set_state(TunnelState.RECONNECTING, "Reconnecting...")
            # 3. Fatal initialization or abort errors (ignore non-fatal library transport logs like [lib] [xquic])
            elif any(k in lower for k in ["fatal", "panic", "iface pin failed", "auth failed", "permission denied"]):
                if not self._stop_requested:
                    self._set_state(TunnelState.ERROR, line_str)

        exit_code = proc.poll()
        if not self._stop_requested:
            if exit_code and exit_code != 0:
                # Provide a human-friendly error message based on logs
                log_summary = " ".join(list(self.log_buffer)[-5:]).lower()
                if "iface pin failed" in log_summary:
                    err = "Could not bind to selected network adapter. Verify the adapter is active and connected."
                elif "10022" in log_summary:
                    err = "Network adapter interface error (WSAEINVAL). Make sure the adapter has a valid IP address."
                elif "write_socket error" in log_summary or "reconnecting" in log_summary:
                    err = "Cannot establish connection to VPS server. Check server IP, port 443 UDP, and ensure Oracle Cloud VCN Ingress Rules allow UDP 443."
                else:
                    err = f"Bonding engine terminated (code {exit_code}). Open 'Logs' for details."
                self._set_state(TunnelState.ERROR, err)
            elif self.state != TunnelState.DISCONNECTED:
                self._set_state(TunnelState.DISCONNECTED, "Disconnected")

        # Auto-reconnect if enabled and not user-initiated stop
        if not self._stop_requested and self.auto_reconnect and self._last_start_args:
            self._set_state(TunnelState.RECONNECTING, "Auto-reconnecting in 5s...")
            time.sleep(5)
            if not self._stop_requested:
                self.start(**self._last_start_args)
