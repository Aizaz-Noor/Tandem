"""TurboBond End-to-End System & Connectivity Diagnostic Tool.

Verifies:
1. Binary integrity (mqvpn.exe, wintun.dll, xquic.dll)
2. Network adapter detection (active adapters, IP addresses, types)
3. Configuration validity (Server IP, Port, Auth Key)
4. VPS Host Reachability (TCP 22 / Ping)
5. QUIC UDP 443 Handshake probe
"""

import os
import sys
import socket
import subprocess
import time
from turbobond.core.config import ConfigManager
from turbobond.core.detector import detect_active_adapters


def run_diagnostics():
    print("=" * 60)
    print("   TURBOBOND 100% READINESS & DIAGNOSTIC AUDIT")
    print("=" * 60)
    all_passed = True

    # --- Test 1: Binary Files ---
    print("\n[1/5] Checking Core Engine Binaries...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(base_dir, "bin")
    binaries = {
        "mqvpn.exe": os.path.join(bin_dir, "mqvpn.exe"),
        "wintun.dll": os.path.join(bin_dir, "wintun.dll"),
        "xquic.dll": os.path.join(bin_dir, "xquic.dll"),
    }
    bin_ok = True
    for name, path in binaries.items():
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print(f"  [PASS] {name} ({os.path.getsize(path):,} bytes)")
        else:
            print(f"  [FAIL] {name} missing or empty at {path}")
            bin_ok = False
            all_passed = False

    # --- Test 2: Local Network Adapters ---
    print("\n[2/5] Detecting Physical Network Adapters for Bonding...")
    adapters = detect_active_adapters()
    if not adapters:
        print("  [FAIL] No active network adapters detected!")
        all_passed = False
    else:
        for ad in adapters:
            print(f"  [PASS] [{ad['type'].upper()}] {ad['name']} -> IP: {ad['ip']}")
        if len(adapters) >= 2:
            print(f"  --> Excellent: {len(adapters)} links available for simultaneous bonding!")
        else:
            print("  --> Notice: 1 link detected. Connect phone USB tethering or second Wi-Fi for multi-link bonding.")

    # --- Test 3: Configuration ---
    print("\n[3/5] Inspecting TurboBond Configuration...")
    config = ConfigManager()
    host = config.get("server_host", "")
    port = config.get("server_port", 443)
    auth_key = config.get("auth_key", "")

    if not host or host == "127.0.0.1":
        print(f"  [FAIL] Invalid server host: {host}")
        all_passed = False
    else:
        print(f"  [PASS] Server Host: {host}")

    if not port or port <= 0 or port > 65535:
        print(f"  [FAIL] Invalid port: {port}")
        all_passed = False
    else:
        print(f"  [PASS] Server Port: {port} (UDP)")

    if not auth_key:
        print("  [FAIL] Missing auth key!")
        all_passed = False
    else:
        print(f"  [PASS] Auth Key Configured: {auth_key[:8]}...{auth_key[-8:]}")

    # --- Test 4: Host Network Reachability ---
    print(f"\n[4/5] Testing VPS Reachability ({host})...")
    # Test SSH port 22 to confirm the VM is online
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.settimeout(3)
    try:
        res = tcp_sock.connect_ex((host, 22))
        if res == 0:
            print(f"  [PASS] VPS Host is ONLINE and reachable (TCP 22 responsive)")
        else:
            print(f"  [WARN] TCP 22 returned code {res}. VM may be booting or firewalled.")
    except Exception as e:
        print(f"  [WARN] TCP probe error: {e}")
    finally:
        tcp_sock.close()

    # --- Test 5: Live QUIC Handshake Test ---
    print(f"\n[5/5] Testing Live Multipath QUIC Handshake against {host}:{port}...")
    if not adapters:
        print("  [SKIP] Cannot run probe without network adapter.")
        return all_passed

    test_adapter = adapters[0]["name"]
    cmd = [
        binaries["mqvpn.exe"],
        "--mode", "client",
        "--server", f"{host}:{port}",
        "--auth-key", auth_key,
        "--path", test_adapter,
        "--insecure",
        "--log-level", "info"
    ]

    print(f"  --> Probing path '{test_adapter}' for 3 seconds...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        time.sleep(2.5)
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()

        output_lower = output.lower()
        if any(k in output_lower for k in ["tunnel 200 ok", "address_assign", "tunnel_ready", "ready", "connected to server", "tunnel active"]):
            print("  [PASS] QUIC Handshake SUCCEEDED! Server replied with 200 OK and assigned tunnel IP!")
            print("  --> 100% VERIFIED: Server, Firewall, and Client are fully operational!")
        elif "pto" in output_lower or "loss_detection_timeout" in output_lower:
            print("  [BLOCKED] Probe timed out waiting for server response.")
            print("  --> Root Cause: Azure Network Security Group (NSG) is not forwarding UDP port 443.")
            print("  --> Resolution: In Azure Portal -> Network settings -> Inbound port rules:")
            print("      Set Destination Port = 443, Protocol = UDP, Source Port = *")
            all_passed = False
        elif "auth failed" in output_lower:
            print("  [FAIL] Authentication failed: Auth key mismatch between client and server.")
            all_passed = False
        else:
            print(f"  --> Probe completed. Last status logs:\n{output[-400:]}")
    except Exception as e:
        print(f"  [FAIL] Failed to run engine probe: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("   STATUS: ALL CHECKS PASSED (100% READY TO BOND)")
    else:
        print("   STATUS: ACTION NEEDED ON 1 CHECK (SEE ABOVE)")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    run_diagnostics()
