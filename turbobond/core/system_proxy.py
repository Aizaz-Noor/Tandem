"""Own, restore, and recover Tandem proxy settings without modifying other apps' proxies."""
import atexit
import ipaddress
import json
import os
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

WINDOWS_INTERNET_SETTINGS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
DEFAULT_PROXY_OVERRIDE = "localhost;127.*;10.*;192.168.*;<local>"
BACKUP_VALUE = "TandemProxyBackup"
GNOME_PROXY_SCHEMA = "org.gnome.system.proxy"
GNOME_HTTP_SCHEMA = "org.gnome.system.proxy.http"
GNOME_HTTPS_SCHEMA = "org.gnome.system.proxy.https"
ENV_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")


def is_localhost_proxy(proxy_str):
    for endpoint in (proxy_str or "").lower().split(';'):
        endpoint = endpoint.split('=', 1)[-1].strip()
        try:
            host = urlsplit(endpoint if '://' in endpoint else '//' + endpoint).hostname
            if host == 'localhost' or (host and ipaddress.ip_address(host).is_loopback):
                return True
        except ValueError:
            pass
    return False


def _pid_alive(pid):
    if type(pid) is not int or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class SystemProxyConfig:
    def __init__(self, proxy_env_path=None):
        self._windows_backup_saved = False
        self._registry_backup = None
        self._owned_endpoint = None
        self._orig_proxy_enable = self._orig_proxy_server = self._orig_proxy_override = None
        self._proxy_server_existed = self._proxy_override_existed = False
        self._gnome_configured = self._linux_backup_saved = self._fallback_configured = False
        self._orig_gnome_mode = None
        self._gnome_backup = {}
        self._gnome_owned = {}
        self._orig_env = None
        self._fallback_backup = None
        self._fallback_content = None
        self._proxy_env_path = proxy_env_path or os.path.expanduser("~/.config/turbobond/proxy_env")
        atexit.register(self.disable_proxy)

    def enable_proxy(self, host="127.0.0.1", port=8080):
        try:
            if sys.platform.startswith("win"):
                return self._enable_windows(host, port)
            if sys.platform.startswith("linux"):
                return self._try_enable_gnome(host, port) or self._enable_linux_fallback(host, port)
            return False
        except Exception as exc:
            print(f"[SystemProxy] Enable failed: {exc}", file=sys.stderr)
            return False

    def disable_proxy(self):
        try:
            if sys.platform.startswith("win"):
                return self._disable_windows()
            if sys.platform.startswith("linux"):
                return self._disable_linux()
            return False
        except Exception as exc:
            print(f"[SystemProxy] Restore failed: {exc}", file=sys.stderr)
            return False

    @classmethod
    def _notify_windows(cls, _self=None):
        try:
            import ctypes
            api = ctypes.windll.wininet
            return bool(api.InternetSetOptionW(0, 39, 0, 0) and api.InternetSetOptionW(0, 37, 0, 0))
        except Exception:
            return False

    @staticmethod
    def _read_value(key, name):
        import winreg
        try:
            return list(winreg.QueryValueEx(key, name))
        except FileNotFoundError:
            return None

    def _enable_windows(self, host, port):
        import winreg
        endpoint = f"{host}:{port}"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_INTERNET_SETTINGS_KEY, 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                if not self._windows_backup_saved:
                    existing = self._read_value(key, BACKUP_VALUE)
                    if existing:
                        raise RuntimeError("Proxy belongs to another Tandem session; restart to recover it")
                    previous = {name: self._read_value(key, name) for name in ("ProxyEnable", "ProxyServer", "ProxyOverride")}
                    record = {"pid": os.getpid(), "endpoint": endpoint, "previous": previous}
                    winreg.SetValueEx(key, BACKUP_VALUE, 0, winreg.REG_SZ, json.dumps(record))
                    self._registry_backup, self._owned_endpoint = record, endpoint
                    self._windows_backup_saved = True
                elif endpoint != self._owned_endpoint:
                    raise RuntimeError("Restore the current proxy before changing its port")
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, endpoint)
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, DEFAULT_PROXY_OVERRIDE)
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            if not self._notify_windows():
                raise RuntimeError("Windows proxy notification failed")
            return True
        except Exception as exc:
            print(f"[SystemProxy] Cannot enable: {exc}", file=sys.stderr)
            if self._windows_backup_saved:
                self._disable_windows()
            return False

    @staticmethod
    def _delete_value(key, name):
        import winreg
        try:
            winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass

    @classmethod
    def _restore_record(cls, key, record):
        import winreg
        for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
            value = record["previous"][name]
            if value is None:
                cls._delete_value(key, name)
            else:
                winreg.SetValueEx(key, name, 0, value[1], value[0])
        cls._delete_value(key, BACKUP_VALUE)

    def _disable_windows(self):
        if not self._windows_backup_saved:
            return True
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_INTERNET_SETTINGS_KEY, 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                current = self._read_value(key, "ProxyServer")
                if current and current[0] == self._owned_endpoint:
                    self._restore_record(key, self._registry_backup)
                else:
                    self._delete_value(key, BACKUP_VALUE)
            self._windows_backup_saved = False
            self._registry_backup = self._owned_endpoint = None
            return self._notify_windows()
        except Exception as exc:
            print(f"[SystemProxy] Cannot restore: {exc}", file=sys.stderr)
            return False

    @classmethod
    def cleanup_orphaned_proxy(cls, force=False, clean_current=False):
        try:
            if sys.platform.startswith("win"):
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_INTERNET_SETTINGS_KEY, 0,
                                    winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                    if force:
                        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                        for name in ("ProxyServer", "ProxyOverride", BACKUP_VALUE):
                            cls._delete_value(key, name)
                    else:
                        saved = cls._read_value(key, BACKUP_VALUE)
                        if saved is None:
                            return True
                        record = json.loads(saved[0])
                        owner_pid = record.get("pid")
                        if not clean_current and _pid_alive(owner_pid):
                            return True
                        current = cls._read_value(key, "ProxyServer")
                        if current and current[0] == record.get("endpoint"):
                            cls._restore_record(key, record)
                        else:
                            cls._delete_value(key, BACKUP_VALUE)
                return cls._notify_windows(None)
            if sys.platform.startswith("linux") and force:
                if shutil.which("gsettings"):
                    subprocess.run(["gsettings", "set", GNOME_PROXY_SCHEMA, "mode", "none"],
                                   check=True, capture_output=True, timeout=5)
                path = os.path.expanduser("~/.config/turbobond/proxy_env")
                if os.path.exists(path):
                    os.remove(path)
            return True
        except Exception as exc:
            print(f"[SystemProxy] Recovery failed: {exc}", file=sys.stderr)
            return False

    def _try_enable_gnome(self, host, port):
        if not shutil.which("gsettings"):
            return False
        updates = [(GNOME_HTTP_SCHEMA, "host", repr(host)), (GNOME_HTTP_SCHEMA, "port", str(port)),
                   (GNOME_HTTPS_SCHEMA, "host", repr(host)), (GNOME_HTTPS_SCHEMA, "port", str(port)),
                   (GNOME_PROXY_SCHEMA, "ignore-hosts", "['localhost', '127.0.0.0/8', '::1']"),
                   (GNOME_PROXY_SCHEMA, "mode", "'manual'")]
        try:
            for schema, key, value in updates:
                result = subprocess.run(["gsettings", "get", schema, key], capture_output=True, text=True, timeout=5)
                if result.returncode:
                    return False
                self._gnome_backup[(schema, key)] = result.stdout.strip()
            self._orig_gnome_mode = self._gnome_backup[(GNOME_PROXY_SCHEMA, "mode")].strip("'\"")
            self._linux_backup_saved = self._gnome_configured = True
            for schema, key, value in updates:
                result = subprocess.run(["gsettings", "set", schema, key, value], capture_output=True, text=True, timeout=5)
                if result.returncode:
                    raise RuntimeError("GNOME proxy update failed")
                self._gnome_owned[(schema, key)] = value
            return True
        except Exception:
            self._disable_linux()
            return False

    def _enable_linux_fallback(self, host, port):
        try:
            if not self._fallback_configured:
                self._orig_env = {key: os.environ.get(key) for key in ENV_KEYS}
                if os.path.exists(self._proxy_env_path):
                    with open(self._proxy_env_path) as stream:
                        self._fallback_backup = stream.read()
            os.makedirs(os.path.dirname(os.path.abspath(self._proxy_env_path)), exist_ok=True)
            self._fallback_content = ''.join(f"{key}=http://{host}:{port}\n" for key in ENV_KEYS)
            with open(self._proxy_env_path, "w") as stream:
                stream.write(self._fallback_content)
            for key in ENV_KEYS:
                os.environ[key] = f"http://{host}:{port}"
            self._fallback_configured = True
            return True
        except OSError:
            return False

    def _disable_linux(self):
        success = True
        if self._gnome_configured:
            for (schema, key), value in list(self._gnome_backup.items()):
                try:
                    result = subprocess.run(["gsettings", "set", schema, key, value.strip("'") if key == "mode" else value],
                                            capture_output=True, text=True, timeout=5)
                    if result.returncode:
                        success = False
                except Exception:
                    success = False
            if success:
                self._gnome_configured = self._linux_backup_saved = False
                self._gnome_backup.clear()
        if self._fallback_configured:
            try:
                if self._fallback_backup is not None:
                    with open(self._proxy_env_path, "w") as stream:
                        stream.write(self._fallback_backup)
                elif os.path.exists(self._proxy_env_path):
                    os.remove(self._proxy_env_path)
                self._fallback_configured = False
            except OSError:
                success = False
        if self._orig_env is not None:
            for key, value in self._orig_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            self._orig_env = None
        return success

    def is_proxy_set(self):
        try:
            if sys.platform.startswith("win"):
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_INTERNET_SETTINGS_KEY, 0, winreg.KEY_READ) as key:
                    current = self._read_value(key, "ProxyEnable")
                    return bool(current and current[0] == 1)
            if sys.platform.startswith("linux"):
                if shutil.which("gsettings"):
                    result = subprocess.run(["gsettings", "get", GNOME_PROXY_SCHEMA, "mode"], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and result.stdout.strip().strip("'\"") == "manual":
                        return True
                return os.path.exists(self._proxy_env_path) or any(os.environ.get(k) for k in ENV_KEYS)
        except Exception:
            pass
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disable_proxy()
