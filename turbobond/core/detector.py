"""
TurboBond - Network Interface Detector
Detects physical network adapters across Windows and Linux, identifying
Wi-Fi cards, USB dongles, and USB tethering interfaces while filtering virtual NICs.
"""

import os
import sys
import json
import subprocess
from typing import List, Dict, Optional


VIRTUAL_KEYWORDS = [
    "loopback", "wintun", "tap-", "tun", "mqvpn", "vethernet",
    "hyper-v", "virtualbox", "vmware", "teredo", "isatap",
    "wireguard", "tailscale", "zerotier", "bluetooth", "npcap"
]


def is_virtual_adapter(name: str, description: str = "") -> bool:
    """Check if an adapter is a virtual or loopback interface."""
    combined = f"{name} {description}".lower()
    return any(keyword in combined for keyword in VIRTUAL_KEYWORDS)


def classify_adapter_type(name: str, description: str = "") -> str:
    """Classify the interface into 'wifi', 'usb_tether', 'ethernet', or 'other'."""
    combined = f"{name} {description}".lower()
    if any(k in combined for k in ["rndis", "tether", "remote ndis", "android", "iphone", "mobile device"]):
        return "usb_tether"
    if any(k in combined for k in ["wi-fi", "wifi", "wireless", "802.11", "wlan"]):
        return "wifi"
    if any(k in combined for k in ["ethernet", "gigabit", "pcie", "lan", "realtek pcie", "intel ethernet"]):
        return "ethernet"
    return "other"


def optimize_windows_multilink() -> bool:
    """
    Configures Windows Connection Manager (WcmSvc) to allow simultaneous active connections
    on Wi-Fi and USB Tethering/Ethernet without Windows deprioritizing or dropping Wi-Fi.
    """
    if not sys.platform.startswith("win"):
        return True
    try:
        import winreg
        key_path = r"Software\Policies\Microsoft\Windows\WcmSvc\GroupPolicy"
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
            # fMinimizeConnections = 0: Allows simultaneous connections (no suppression)
            winreg.SetValueEx(key, "fMinimizeConnections", 0, winreg.REG_DWORD, 0)
            # fBlockNonDomain = 0: Allows simultaneous connections across distinct networks
            winreg.SetValueEx(key, "fBlockNonDomain", 0, winreg.REG_DWORD, 0)
        return True
    except Exception:
        # Fails gracefully if not running elevated yet
        return False


def get_windows_adapters() -> List[Dict[str, str]]:
    """Enumerate network adapters on Windows using PowerShell."""
    adapters = []
    try:
        # Query active adapters
        cmd = (
            "Get-NetAdapter | Where-Object Status -eq 'Up' | "
            "Select-Object Name, InterfaceDescription, Status, MacAddress, LinkSpeed | "
            "ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []

        raw_data = json.loads(proc.stdout.strip())
        if isinstance(raw_data, dict):
            raw_data = [raw_data]

        # Query IPv4 addresses for mapping
        ip_cmd = (
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Select-Object InterfaceAlias, IPAddress, PrefixLength | "
            "ConvertTo-Json -Compress"
        )
        ip_proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ip_cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        ip_map = {}
        if ip_proc.returncode == 0 and ip_proc.stdout.strip():
            try:
                ip_data = json.loads(ip_proc.stdout.strip())
                if isinstance(ip_data, dict):
                    ip_data = [ip_data]
                for item in ip_data:
                    alias = item.get("InterfaceAlias", "")
                    ip = item.get("IPAddress", "")
                    if alias and ip and not ip.startswith("169.254.") and not ip.startswith("127."):
                        ip_map[alias] = ip
            except Exception:
                pass

        for item in raw_data:
            name = item.get("Name", "")
            desc = item.get("InterfaceDescription", "")
            if is_virtual_adapter(name, desc):
                continue

            adapter_type = classify_adapter_type(name, desc)
            ip = ip_map.get(name, "Pending IP...")

            adapters.append({
                "name": name,
                "description": desc,
                "type": adapter_type,
                "ip": ip,
                "status": item.get("Status", "Up"),
                "speed": item.get("LinkSpeed", "Unknown")
            })

    except Exception as e:
        print(f"[Detector] Windows error: {e}", file=sys.stderr)

    return adapters


def get_linux_adapters() -> List[Dict[str, str]]:
    """Enumerate network adapters on Linux using `ip` command."""
    adapters = []
    try:
        proc = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            return []

        data = json.loads(proc.stdout)
        for item in data:
            name = item.get("ifname", "")
            operstate = item.get("operstate", "").upper()
            if operstate != "UP" or name == "lo" or is_virtual_adapter(name):
                continue

            # Extract IPv4
            ip = "Pending IP..."
            for addr_info in item.get("addr_info", []):
                if addr_info.get("family") == "inet":
                    ip = addr_info.get("local", "")
                    break

            # Detect adapter type from sysfs
            adapter_type = _classify_linux_adapter(name)

            # Read link speed from sysfs
            speed = _get_linux_speed(name)

            adapters.append({
                "name": name,
                "description": name,
                "type": adapter_type,
                "ip": ip,
                "status": "Up",
                "speed": speed
            })
    except Exception as e:
        print(f"[Detector] Linux error: {e}", file=sys.stderr)

    return adapters


def _classify_linux_adapter(ifname: str) -> str:
    """Classify Linux adapter type using sysfs and interface name."""
    try:
        # Check if it's wireless
        wireless_path = f"/sys/class/net/{ifname}/wireless"
        if os.path.exists(wireless_path):
            return "wifi"
        # Check if USB device (indicative of tethering/dongle)
        device_path = os.path.realpath(f"/sys/class/net/{ifname}/device")
        if "/usb" in device_path:
            # Check driver for RNDIS (tethering)
            try:
                driver_path = os.path.realpath(f"/sys/class/net/{ifname}/device/driver")
                driver_name = os.path.basename(driver_path).lower()
                if driver_name in ["rndis_host", "cdc_ether", "cdc_ncm"]:
                    return "usb_tether"
            except Exception:
                pass
            return "usb_tether"  # USB network = likely tethering
    except Exception:
        pass
    # Fallback to name-based classification
    return classify_adapter_type(ifname)


def _get_linux_speed(ifname: str) -> str:
    """Read link speed from sysfs, return human-readable string."""
    try:
        speed_path = f"/sys/class/net/{ifname}/speed"
        with open(speed_path, "r") as f:
            speed_mbps = int(f.read().strip())
            if speed_mbps > 0:
                if speed_mbps >= 1000:
                    return f"{speed_mbps / 1000:.0f} Gbps"
                return f"{speed_mbps} Mbps"
    except (FileNotFoundError, ValueError, PermissionError, OSError):
        pass
    return "Active"


def detect_active_adapters() -> List[Dict[str, str]]:
    """Cross-platform detection of active physical/usable network adapters."""
    if sys.platform.startswith("win"):
        return get_windows_adapters()
    else:
        return get_linux_adapters()


if __name__ == "__main__":
    detected = detect_active_adapters()
    print(f"Found {len(detected)} active adapters:")
    for a in detected:
        print(f" - [{a['type'].upper()}] {a['name']} ({a['description']}) -> IP: {a['ip']} ({a['speed']})")
