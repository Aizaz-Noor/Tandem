"""
TurboBond - Configuration & Profile Manager
Handles application settings, VPS credentials, adapter selections,
and 1-click import/export profiles for easy sharing with roommates.
"""

import os
import sys
import json
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
    "auto_connect_on_launch": True,
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


class ConfigManager:
    """Manages reading, writing, and sharing TurboBond settings."""

    def __init__(self, filepath: Optional[str] = None):
        self.filepath = filepath or get_default_config_path()
        self.data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load settings from JSON file if available."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Config] Error reading {self.filepath}: {e}", file=sys.stderr)
        return self.data

    def save(self) -> bool:
        """Save current settings to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            return True
        except Exception as e:
            print(f"[Config] Error writing {self.filepath}: {e}", file=sys.stderr)
            return False

    def export_profile(self, target_path: str) -> bool:
        """Export connection profile (server, port, key, dns) for sharing with friends."""
        try:
            profile = {
                "turbobond_version": "1.0",
                "server_host": self.data.get("server_host"),
                "server_port": self.data.get("server_port"),
                "auth_key": self.data.get("auth_key"),
                "scheduler": self.data.get("scheduler", "wlb"),
                "dns": self.data.get("dns", ["1.1.1.1", "8.8.8.8"]),
                "insecure": self.data.get("insecure", True)
            }
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=4)
            return True
        except Exception as e:
            print(f"[Config] Export error: {e}", file=sys.stderr)
            return False

    def import_profile(self, source_path: str) -> bool:
        """Import connection profile from a shared file."""
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                profile = json.load(f)

            # Validate profile structure
            if not isinstance(profile, dict):
                print("[Config] Import error: profile is not a JSON object", file=sys.stderr)
                return False

            # Validate field types if present
            validators = {
                "server_host": str,
                "server_port": int,
                "auth_key": str,
                "scheduler": str,
                "dns": list,
                "insecure": bool
            }
            for key, expected_type in validators.items():
                if key in profile:
                    if not isinstance(profile[key], expected_type):
                        print(f"[Config] Import error: '{key}' must be {expected_type.__name__}", file=sys.stderr)
                        return False
                    self.data[key] = profile[key]

            self.save()
            return True
        except json.JSONDecodeError as e:
            print(f"[Config] Import error: invalid JSON - {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"[Config] Import error: {e}", file=sys.stderr)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value
        self.save()
