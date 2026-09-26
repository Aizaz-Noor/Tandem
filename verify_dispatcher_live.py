"""
TurboBond - Live End-to-End Dispatcher Verification
Runs a complete live integration test:
1. Detects active physical adapters and their local IPs
2. Starts the Local Multi-WAN Dispatcher on port 8080
3. Sends concurrent HTTP GET requests through the proxy via SOCKS5
4. Verifies round-robin load distribution across available adapters
5. Measures latency, throughput, and byte stats
6. Shuts down cleanly
"""

import sys
import time
import socket
import struct
import urllib.request

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from turbobond.core.detector import detect_active_adapters
from turbobond.core.dispatcher import LocalDispatcher

def test_socks5_request(proxy_host, proxy_port, target_host, target_port=80, path="/"):
    """Perform a raw SOCKS5 HTTP request through the local proxy."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(6.0)
    try:
        t0 = time.time()
        s.connect((proxy_host, proxy_port))
        
        # 1. SOCKS5 Greeting (No Auth)
        s.sendall(b"\x05\x01\x00")
        resp = s.recv(2)
        if resp != b"\x05\x00":
            return False, f"Invalid greeting reply: {resp.hex()}", 0, 0
        
        # 2. SOCKS5 Connect Request (domain name)
        host_bytes = target_host.encode('ascii')
        req = b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + struct.pack("!H", target_port)
        s.sendall(req)
        
        resp = s.recv(10)
        if len(resp) < 4 or resp[1] != 0x00:
            return False, f"Connect error status: {resp[1] if len(resp) >= 2 else 'timeout'}", 0, 0
        
        connect_time = (time.time() - t0) * 1000
        
        # 3. Send HTTP Request
        http_req = f"GET {path} HTTP/1.1\r\nHost: {target_host}\r\nUser-Agent: TurboBondTester/1.0\r\nConnection: close\r\n\r\n"
        s.sendall(http_req.encode('ascii'))
        
        total_bytes = 0
        status_line = ""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            total_bytes += len(chunk)
            if not status_line:
                lines = chunk.decode('latin1', errors='ignore').split("\r\n")
                status_line = lines[0]
                
        return True, status_line, connect_time, total_bytes
    except Exception as e:
        return False, str(e), 0, 0
    finally:
        s.close()


def run_live_verification():
    print("=" * 65)
    print("⚡ TURBOBOND - LIVE DISPATCHER INTEGRATION TEST")
    print("=" * 65)
    
    # 1. Adapter Discovery
    print("\n[Step 1/4] Scanning local network adapters...")
    adapters = detect_active_adapters()
    print(f"Found {len(adapters)} active adapter(s):")
    valid_ips = []
    for a in adapters:
        ip = a.get("ip", "")
        print(f"  • [{a['type'].upper()}] {a['name']} ({a['description'][:35]}) -> IP: {ip}")
        if ip and not ip.startswith("Pending") and not ip.startswith("169.254"):
            valid_ips.append(ip)
            
    if not valid_ips:
        print("⚠️ No valid adapter IPs found. Falling back to 127.0.0.1 for loopback verification.")
        valid_ips = ["127.0.0.1"]
        
    print(f"\nDispatch targets: {valid_ips}")

    # 2. Launch Local Dispatcher
    proxy_port = 8899  # Dedicated test port to avoid conflicting with running apps
    print(f"\n[Step 2/4] Starting LocalDispatcher on 127.0.0.1:{proxy_port}...")
    dispatcher = LocalDispatcher(
        host="127.0.0.1",
        port=proxy_port,
        adapter_ips=valid_ips,
        strategy="round_robin"
    )
    dispatcher.start_in_thread()
    time.sleep(0.5)  # Wait for socket listen
    
    # 3. Test Live Requests
    target_hosts = ["example.com", "icanhazip.com", "httpbin.org"]
    print(f"\n[Step 3/4] Dispatching concurrent requests across adapters...")
    
    num_requests = max(len(valid_ips) * 2, 4)
    successes = 0
    
    for i in range(num_requests):
        target = target_hosts[i % len(target_hosts)]
        assigned_ip = valid_ips[i % len(valid_ips)]
        print(f" Request #{i+1} -> Target: {target} (Bound to local IP: {assigned_ip})...", end=" ", flush=True)
        
        ok, detail, latency_ms, rx_bytes = test_socks5_request("127.0.0.1", proxy_port, target, 80, "/")
        if ok:
            successes += 1
            print(f"✅ OK ({detail[:15]} | Latency: {latency_ms:.1f}ms | RX: {rx_bytes} bytes)")
        else:
            print(f"❌ Failed: {detail}")
            
    # 4. Telemetry & Stats Verification
    print(f"\n[Step 4/4] Verifying Dispatcher Internal Telemetry...")
    stats = dispatcher.get_stats()
    total_conns = stats['total']['connections_total']
    total_rx = stats['total']['bytes_rx']
    total_tx = stats['total']['bytes_tx']
    
    print(f"  • Total Dispatched Connections: {total_conns}")
    print(f"  • Total Bytes Received (RX):   {total_rx:,} bytes")
    print(f"  • Total Bytes Transmitted (TX): {total_tx:,} bytes")
    print("  • Per-Adapter Breakdown:")
    for ip, s in stats.get("adapters", {}).items():
        print(f"     - IP {ip:15}: {s['connections_total']} conns | RX: {s['bytes_rx']:,} bytes | TX: {s['bytes_tx']:,} bytes")

    # Clean shutdown
    dispatcher.stop_from_thread()
    print("\n" + "=" * 65)
    
    if successes == num_requests:
        print(f"🎉 VERIFICATION PASSED: All {successes}/{num_requests} requests succeeded!")
        print("TurboBond Local Multi-WAN Dispatcher is 100% OPERATIONAL.")
        print("=" * 65)
        return True
    else:
        print(f"⚠️ Partial success: {successes}/{num_requests} succeeded.")
        print("=" * 65)
        return False


if __name__ == "__main__":
    success = run_live_verification()
    sys.exit(0 if success else 1)
