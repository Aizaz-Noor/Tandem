"""
TurboBond - System Proxy Auto-Configurator
Manages OS-level proxy settings on Windows and Linux to route browser
and application traffic through TurboBond's local dispatcher proxy.
"""

import os
import sys
import shutil
import subprocess
from typing import Optional


WINDOWS_INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
DEFAULT_PROXY_OVERRIDE = "localhost;127.*;10.*;192.168.*;<local>"

GNOME_PROXY_SCHEMA = "org.gnome.system.proxy"
GNOME_HTTP_SCHEMA = "org.gnome.system.proxy.http"
GNOME_HTTPS_SCHEMA = "org.gnome.system.proxy.https"


class SystemProxyConfig:
    """Auto-configures OS proxy routing for TurboBond."""

    def __init__(self, proxy_env_path: Optional[str] = None):
        # Windows backup state
        self._windows_backup_saved: bool = False
        self._orig_proxy_enable: Optional[int] = None
        self._orig_proxy_server: Optional[str] = None
        self._orig_proxy_override: Optional[str] = None
        self._proxy_server_existed: bool = False
        self._proxy_override_existed: bool = False

        # Linux backup state
        self._linux_backup_saved: bool = False
        self._orig_gnome_mode: Optional[str] = None
        self._gnome_configured: bool = False
        self._fallback_configured: bool = False

        # Linux fallback file location
        if proxy_env_path:
            self._proxy_env_path = proxy_env_path
        else:
            self._proxy_env_path = os.path.expanduser("~/.config/turbobond/proxy_env")

    def enable_proxy(self, host: str = "127.0.0.1", port: int = 8080) -> bool:
        """
        Configure OS to route traffic through the specified proxy host and port.
        Returns True on success, False on failure.
        """
        try:
            if sys.platform.startswith("win"):
                return self._enable_windows(host, port)
            elif sys.platform.startswith("linux"):
                return self._enable_linux(host, port)
            else:
                print(f"[SystemProxy] Unsupported platform: {sys.platform}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"[SystemProxy] Failed to enable proxy: {e}", file=sys.stderr)
            return False

    def disable_proxy(self) -> bool:
        """
        Restore original proxy settings.
        Robust: always attempts all restoration steps even if errors occur.
        Returns True on success, False if any error was encountered.
        """
        try:
            if sys.platform.startswith("win"):
                return self._disable_windows()
            elif sys.platform.startswith("linux"):
                return self._disable_linux()
            else:
                print(f"[SystemProxy] Unsupported platform: {sys.platform}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"[SystemProxy] Failed to disable proxy: {e}", file=sys.stderr)
            return False

    def is_proxy_set(self) -> bool:
        """
        Check if the system proxy is currently configured.
        Returns True if configured, False otherwise.
        """
        try:
            if sys.platform.startswith("win"):
                return self._is_windows_proxy_set()
            elif sys.platform.startswith("linux"):
                return self._is_linux_proxy_set()
            else:
                return False
        except Exception as e:
            print(f"[SystemProxy] Error querying proxy state: {e}", file=sys.stderr)
            return False

    # -------------------------------------------------------------------------
    # Windows Implementation
    # -------------------------------------------------------------------------

    def _notify_windows(self) -> bool:
        """Notify WinINet that system proxy settings have changed."""
        try:
            import ctypes
            INTERNET_OPTION_SETTINGS_CHANGED = 39
            INTERNET_OPTION_REFRESH = 37
            wininet = ctypes.windll.wininet
            wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
            wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
            return True
        except Exception as e:
            print(f"[SystemProxy] Windows InternetSetOptionW notification error: {e}", file=sys.stderr)
            return False

    def _enable_windows(self, host: str, port: int) -> bool:
        """Enable proxy on Windows via registry and notify WinINet."""
        try:
            import winreg
        except ImportError as e:
            print(f"[SystemProxy] winreg module unavailable: {e}", file=sys.stderr)
            return False

        proxy_server = f"{host}:{port}"
        proxy_override = DEFAULT_PROXY_OVERRIDE

        try:
            # 1. Read and save original values if not already backed up
            if not self._windows_backup_saved:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        WINDOWS_INTERNET_SETTINGS_KEY,
                        0,
                        winreg.KEY_READ
                    ) as key:
                        try:
                            val, _ = winreg.QueryValueEx(key, "ProxyEnable")
                            self._orig_proxy_enable = int(val)
                        except FileNotFoundError:
                            self._orig_proxy_enable = 0

                        try:
                            val, _ = winreg.QueryValueEx(key, "ProxyServer")
                            self._orig_proxy_server = str(val)
                            self._proxy_server_existed = True
                        except FileNotFoundError:
                            self._orig_proxy_server = ""
                            self._proxy_server_existed = False

                        try:
                            val, _ = winreg.QueryValueEx(key, "ProxyOverride")
                            self._orig_proxy_override = str(val)
                            self._proxy_override_existed = True
                        except FileNotFoundError:
                            self._orig_proxy_override = ""
                            self._proxy_override_existed = False

                    self._windows_backup_saved = True
                except Exception as e:
                    print(f"[SystemProxy] Failed to backup Windows proxy settings: {e}", file=sys.stderr)
                    # Proceed to attempt setting proxy even if backup read failed

            # 2. Set ProxyEnable=1, ProxyServer, ProxyOverride
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                WINDOWS_INTERNET_SETTINGS_KEY,
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, proxy_override)

            # 3. Notify system
            self._notify_windows()
            return True

        except Exception as e:
            print(f"[SystemProxy] Windows proxy enable failed: {e}", file=sys.stderr)
            return False

    def _disable_windows(self) -> bool:
        """Restore original Windows proxy settings and notify WinINet."""
        try:
            import winreg
        except ImportError as e:
            print(f"[SystemProxy] winreg module unavailable: {e}", file=sys.stderr)
            return False

        success = True

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                WINDOWS_INTERNET_SETTINGS_KEY,
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                # 1. Restore ProxyEnable
                target_enable = (
                    self._orig_proxy_enable
                    if (self._windows_backup_saved and self._orig_proxy_enable is not None)
                    else 0
                )
                try:
                    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, target_enable)
                except Exception as e:
                    print(f"[SystemProxy] Failed to restore ProxyEnable: {e}", file=sys.stderr)
                    success = False

                # 2. Restore ProxyServer
                if self._windows_backup_saved:
                    if self._proxy_server_existed and self._orig_proxy_server is not None:
                        try:
                            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, self._orig_proxy_server)
                        except Exception as e:
                            print(f"[SystemProxy] Failed to restore ProxyServer: {e}", file=sys.stderr)
                            success = False
                    else:
                        try:
                            winreg.DeleteValue(key, "ProxyServer")
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            print(f"[SystemProxy] Failed to remove ProxyServer: {e}", file=sys.stderr)
                            success = False

                # 3. Restore ProxyOverride
                if self._windows_backup_saved:
                    if self._proxy_override_existed and self._orig_proxy_override is not None:
                        try:
                            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, self._orig_proxy_override)
                        except Exception as e:
                            print(f"[SystemProxy] Failed to restore ProxyOverride: {e}", file=sys.stderr)
                            success = False
                    else:
                        try:
                            winreg.DeleteValue(key, "ProxyOverride")
                        except FileNotFoundError:
                            pass
                        except Exception as e:
                            print(f"[SystemProxy] Failed to remove ProxyOverride: {e}", file=sys.stderr)
                            success = False

            self._windows_backup_saved = False

        except Exception as e:
            print(f"[SystemProxy] Windows proxy disable error: {e}", file=sys.stderr)
            success = False

        # Always notify system
        try:
            if not self._notify_windows():
                success = False
        except Exception as e:
            print(f"[SystemProxy] Windows notification error during disable: {e}", file=sys.stderr)
            success = False

        return success

    def _is_windows_proxy_set(self) -> bool:
        """Check if Windows proxy is currently enabled."""
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                WINDOWS_INTERNET_SETTINGS_KEY,
                0,
                winreg.KEY_READ
            ) as key:
                try:
                    val, _ = winreg.QueryValueEx(key, "ProxyEnable")
                    return bool(val == 1)
                except FileNotFoundError:
                    return False
        except Exception as e:
            print(f"[SystemProxy] Error querying Windows proxy status: {e}", file=sys.stderr)
            return False

    # -------------------------------------------------------------------------
    # Linux Implementation
    # -------------------------------------------------------------------------

    def _enable_linux(self, host: str, port: int) -> bool:
        """Enable proxy on Linux: try GNOME first, fallback to proxy_env."""
        # Try GNOME
        if self._try_enable_gnome(host, port):
            return True

        # Fallback to file-based environment configuration
        return self._enable_linux_fallback(host, port)

    def _try_enable_gnome(self, host: str, port: int) -> bool:
        """Attempt to configure GNOME proxy settings via gsettings."""
        if not shutil.which("gsettings"):
            return False

        try:
            # Save original mode if not saved yet
            if not self._linux_backup_saved:
                res = subprocess.run(
                    ["gsettings", "get", GNOME_PROXY_SCHEMA, "mode"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if res.returncode == 0:
                    self._orig_gnome_mode = res.stdout.strip().strip("'\"")
                else:
                    self._orig_gnome_mode = "none"
                self._linux_backup_saved = True

            # Configure GNOME proxy settings
            cmds = [
                ["gsettings", "set", GNOME_PROXY_SCHEMA, "mode", "manual"],
                ["gsettings", "set", GNOME_HTTP_SCHEMA, "host", host],
                ["gsettings", "set", GNOME_HTTP_SCHEMA, "port", str(port)],
                ["gsettings", "set", GNOME_HTTPS_SCHEMA, "host", host],
                ["gsettings", "set", GNOME_HTTPS_SCHEMA, "port", str(port)],
                [
                    "gsettings",
                    "set",
                    GNOME_PROXY_SCHEMA,
                    "ignore-hosts",
                    "['localhost', '127.0.0.0/8', '::1', '10.0.0.0/8', '192.168.0.0/16']"
                ]
            ]

            for cmd in cmds:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if p.returncode != 0:
                    print(
                        f"[SystemProxy] gsettings command failed: {' '.join(cmd)}: {p.stderr.strip()}",
                        file=sys.stderr
                    )
                    self._linux_backup_saved = False
                    return False

            self._gnome_configured = True
            return True

        except Exception as e:
            print(f"[SystemProxy] GNOME proxy configuration error: {e}", file=sys.stderr)
            self._linux_backup_saved = False
            return False

    def _enable_linux_fallback(self, host: str, port: int) -> bool:
        """Write proxy environment variables to ~/.config/turbobond/proxy_env."""
        try:
            os.makedirs(os.path.dirname(self._proxy_env_path), exist_ok=True)
            content = (
                f"http_proxy=http://{host}:{port}\n"
                f"https_proxy=http://{host}:{port}\n"
                f"HTTP_PROXY=http://{host}:{port}\n"
                f"HTTPS_PROXY=http://{host}:{port}\n"
                f"all_proxy=http://{host}:{port}\n"
                f"ALL_PROXY=http://{host}:{port}\n"
                f"no_proxy=localhost,127.0.0.1,10.0.0.0/8,192.168.0.0/16\n"
                f"NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,192.168.0.0/16\n"
            )
            with open(self._proxy_env_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Also set in current process environment
            os.environ["http_proxy"] = f"http://{host}:{port}"
            os.environ["https_proxy"] = f"http://{host}:{port}"
            os.environ["HTTP_PROXY"] = f"http://{host}:{port}"
            os.environ["HTTPS_PROXY"] = f"http://{host}:{port}"

            self._fallback_configured = True
            return True

        except Exception as e:
            print(f"[SystemProxy] Linux fallback proxy_env error: {e}", file=sys.stderr)
            return False

    def _disable_linux(self) -> bool:
        """Restore Linux proxy settings (GNOME mode and fallback proxy_env)."""
        success = True

        # 1. Restore GNOME proxy mode if GNOME was configured or if called without fallback
        should_restore_gnome = self._gnome_configured or (
            not self._fallback_configured and bool(shutil.which("gsettings"))
        )
        if should_restore_gnome and shutil.which("gsettings"):
            try:
                target_mode = (
                    self._orig_gnome_mode
                    if (self._linux_backup_saved and self._orig_gnome_mode)
                    else "none"
                )
                p = subprocess.run(
                    ["gsettings", "set", GNOME_PROXY_SCHEMA, "mode", target_mode],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if p.returncode != 0:
                    print(
                        f"[SystemProxy] Failed to restore GNOME proxy mode: {p.stderr.strip()}",
                        file=sys.stderr
                    )
                    success = False
            except Exception as e:
                print(f"[SystemProxy] Error restoring GNOME proxy: {e}", file=sys.stderr)
                success = False

        self._gnome_configured = False
        self._linux_backup_saved = False
        self._orig_gnome_mode = None

        # 2. Remove fallback proxy_env file
        try:
            if os.path.exists(self._proxy_env_path):
                os.remove(self._proxy_env_path)
            self._fallback_configured = False
        except Exception as e:
            print(f"[SystemProxy] Error removing proxy_env file: {e}", file=sys.stderr)
            success = False

        # 3. Clean process environment variables
        for env_var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]:
            if env_var in os.environ:
                try:
                    del os.environ[env_var]
                except Exception:
                    pass

        return success

    def _is_linux_proxy_set(self) -> bool:
        """Check if Linux proxy is configured via GNOME or fallback."""
        # 1. Check GNOME
        if shutil.which("gsettings"):
            try:
                p = subprocess.run(
                    ["gsettings", "get", GNOME_PROXY_SCHEMA, "mode"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if p.returncode == 0:
                    mode = p.stdout.strip().strip("'\"")
                    if mode == "manual":
                        return True
            except Exception as e:
                print(f"[SystemProxy] Error checking GNOME proxy status: {e}", file=sys.stderr)

        # 2. Check fallback proxy_env file
        try:
            if os.path.exists(self._proxy_env_path):
                with open(self._proxy_env_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "http_proxy=" in content:
                        return True
        except Exception as e:
            print(f"[SystemProxy] Error reading proxy_env file: {e}", file=sys.stderr)

        # 3. Check environment variables
        if os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY"):
            return True

        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable_proxy()


if __name__ == "__main__":
    cfg = SystemProxyConfig()
    print(f"[SystemProxy] Is proxy configured: {cfg.is_proxy_set()}")
