"""
TurboBond - Configuration & Profile Manager
Handles application settings, VPS credentials, adapter selections,
and 1-click import/export profiles for easy sharing with roommates.
"""

import os
import sys
import json
import copy
import tempfile
import threading
from typing import Dict, Any, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    # Mode: "local_dispatcher" (new, recommended) or "cloud_bonding" (legacy VPN)
    "mode": "local_dispatcher",

    # --- Local Dispatcher Settings ---
    "proxy_port": 8080,
    "distribution_strategy": "round_robin",  # "round_robin" or "weighted"
    "auto_system_proxy": True,
    "adapter_weights": {},  # {"Wi-Fi": 3, "Ethernet 2": 1}  — used in weighted mode

    # --- Cloud Bonding Settings (legacy) ---
    "server_host": "150.136.212.160",
    "server_port": 443,
    "auth_key": "",
    "scheduler": "wlb",
    "insecure": True,
    "dns": ["1.1.1.1", "8.8.8.8"],

    # --- Common Settings ---
    "kill_switch": False,
    "auto_reconnect": True,
    "auto_connect_on_launch": False,
    "selected_adapters": []
}


def get_default_config_path() -> str:
    """Determine cross-platform configuration storage path."""
    if sys.platform.startswith("win"):
        base_dir = os.environ.get("APPDATA", os.path.expanduser("~"))
        target_dir = os.path.join(base_dir, "TurboBond")
    else:
        target_dir = os.path.expanduser("~/.config/turbobond")
    
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, "config.json")


PROFILE_KEYS = ("server_host", "server_port", "auth_key", "scheduler", "dns", "insecure")


def validate_patch(patch):
    if not isinstance(patch, dict):
        raise ValueError("Configuration must be an object")
    for key, value in patch.items():
        if key not in DEFAULT_CONFIG:
            raise ValueError(f"Unknown setting: {key}")
        if type(value) is not type(DEFAULT_CONFIG[key]):
            raise ValueError(f"Invalid type for {key}")
        if key in ("proxy_port", "server_port") and not 1 <= value <= 65535:
            raise ValueError(f"{key} must be between 1 and 65535")
        if key == "mode" and value not in ("local_dispatcher", "cloud_bonding"):
            raise ValueError("Unsupported connection mode")
        if key == "distribution_strategy" and value not in ("round_robin", "weighted"):
            raise ValueError("Unsupported distribution strategy")
        if key == "scheduler" and value not in ("wlb", "minrtt"):
            raise ValueError("Unsupported cloud scheduler")
        if key in ("dns", "selected_adapters") and any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError(f"{key} must contain nonempty strings")
        if key == "adapter_weights" and any(not isinstance(k, str) or type(v) is not int or not 1 <= v <= 100 for k, v in value.items()):
            raise ValueError("Adapter weights must be integers from 1 to 100")
        if key == "kill_switch" and value:
            raise ValueError("Kill switch is not supported; disable it before connecting")
        if isinstance(value, str) and (len(value) > 4096 or any(c in value for c in ("\r", "\n", "\x00"))):
            raise ValueError(f"Invalid characters or length for {key}")


def atomic_write_json(path, value):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".tandem-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ConfigManager:
    """Validated, atomic configuration updates; failures never publish partial patches."""

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or get_default_config_path()
        self._lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, encoding="utf-8") as stream:
                    saved = json.load(stream)
                if not isinstance(saved, dict):
                    raise ValueError("Configuration must be an object")
                # Ignore obsolete keys, but preserve a previously requested kill switch
                # so connection can fail explicitly instead of silently bypassing it.
                for key, value in saved.items():
                    if key not in DEFAULT_CONFIG:
                        continue
                    try:
                        if key != "kill_switch" or value is not True:
                            validate_patch({key: value})
                        self.data[key] = copy.deepcopy(value)
                    except ValueError as exc:
                        print(f"[Config] {exc}; using default", file=sys.stderr)
            except (OSError, ValueError) as exc:
                print(f"[Config] Cannot load settings: {exc}", file=sys.stderr)
        return self.data

    def save(self):
        try:
            with self._lock:
                validate_patch(self.data)
                atomic_write_json(self.filepath, self.data)
            return True
        except (OSError, ValueError) as exc:
            print(f"[Config] Cannot save settings: {exc}", file=sys.stderr)
            return False

    def update(self, patch):
        validate_patch(patch)
        with self._lock:
            candidate = copy.deepcopy(self.data)
            candidate.update(copy.deepcopy(patch))
            atomic_write_json(self.filepath, candidate)
            self.data = candidate
        return True

    def export_profile(self, target_path):
        try:
            profile = {key: self.data[key] for key in PROFILE_KEYS}
            profile["turbobond_version"] = "1.0"
            atomic_write_json(target_path, profile)
            return True
        except (OSError, ValueError) as exc:
            print(f"[Config] Export failed: {exc}", file=sys.stderr)
            return False

    def import_profile(self, source_path):
        try:
            with open(source_path, encoding="utf-8") as stream:
                profile = json.load(stream)
            if not isinstance(profile, dict):
                raise ValueError("Profile must be an object")
            patch = {key: profile[key] for key in PROFILE_KEYS if key in profile}
            if not patch:
                raise ValueError("Profile contains no connection settings")
            return self.update(patch)
        except (OSError, ValueError) as exc:
            print(f"[Config] Import failed: {exc}", file=sys.stderr)
            return False

    def get(self, key, default=None):
        with self._lock:
            return copy.deepcopy(self.data.get(key, default))

    def set(self, key, value):
        return self.update({key: value})
