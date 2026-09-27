"""
TurboBond - Real-Time Telemetry Monitor
Calculates instantaneous download/upload speeds (Mbps and MB/s) per physical adapter
and for aggregated total bandwidth using low-overhead native OS APIs.
"""

import sys
import time
from typing import Dict, Tuple, Optional


# Windows native ctypes definition for instant zero-dependency stats
if sys.platform.startswith("win"):
    import ctypes
    from ctypes import wintypes

    class MIB_IF_ROW2(ctypes.Structure):
        _fields_ = [
            ('InterfaceLuid', ctypes.c_uint64),
            ('InterfaceIndex', wintypes.ULONG),
            ('InterfaceGuid', ctypes.c_byte * 16),
            ('Alias', wintypes.WCHAR * 257),
            ('Description', wintypes.WCHAR * 257),
            ('PhysicalAddressLength', wintypes.ULONG),
            ('PhysicalAddress', ctypes.c_byte * 32),
            ('PermanentPhysicalAddress', ctypes.c_byte * 32),
            ('Mtu', wintypes.ULONG),
            ('Type', wintypes.ULONG),
            ('TunnelType', wintypes.ULONG),
            ('MediaType', wintypes.ULONG),
            ('PhysicalMediumType', wintypes.ULONG),
            ('AccessType', wintypes.ULONG),
            ('DirectionType', wintypes.ULONG),
            ('InterfaceAndOperStatusFlags', ctypes.c_byte),
            ('OperStatus', wintypes.ULONG),
            ('AdminStatus', wintypes.ULONG),
            ('MediaConnectState', wintypes.ULONG),
            ('NetworkGuid', ctypes.c_byte * 16),
            ('ConnectionType', wintypes.ULONG),
            ('Padding1', ctypes.c_byte * 4),
            ('TransmitLinkSpeed', ctypes.c_uint64),
            ('ReceiveLinkSpeed', ctypes.c_uint64),
            ('InOctets', ctypes.c_uint64),
            ('InUcastPkts', ctypes.c_uint64),
            ('InNUcastPkts', ctypes.c_uint64),
            ('InDiscards', ctypes.c_uint64),
            ('InErrors', ctypes.c_uint64),
            ('InUnknownProtos', ctypes.c_uint64),
            ('InUcastOctets', ctypes.c_uint64),
            ('InMulticastOctets', ctypes.c_uint64),
            ('InBroadcastOctets', ctypes.c_uint64),
            ('OutOctets', ctypes.c_uint64),
            ('OutUcastPkts', ctypes.c_uint64),
            ('OutNUcastPkts', ctypes.c_uint64),
            ('OutDiscards', ctypes.c_uint64),
            ('OutErrors', ctypes.c_uint64),
            ('OutUcastOctets', ctypes.c_uint64),
            ('OutMulticastOctets', ctypes.c_uint64),
            ('OutBroadcastOctets', ctypes.c_uint64),
            ('OutQLen', ctypes.c_uint64)
        ]

    class MIB_IF_TABLE2(ctypes.Structure):
        _fields_ = [
            ('NumEntries', wintypes.ULONG),
            ('Padding', ctypes.c_byte * 4),
            ('Table', MIB_IF_ROW2 * 1)
        ]


def get_windows_counters() -> Dict[str, Tuple[int, int]]:
    """Query byte counters on Windows via Iphlpapi.GetIfTable2."""
    counters = {}
    try:
        iphlpapi = ctypes.windll.iphlpapi
        pTable = ctypes.POINTER(MIB_IF_TABLE2)()
        if iphlpapi.GetIfTable2(ctypes.byref(pTable)) == 0:
            for i in range(pTable.contents.NumEntries):
                row_ptr = ctypes.cast(
                    ctypes.addressof(pTable.contents.Table) + i * ctypes.sizeof(MIB_IF_ROW2),
                    ctypes.POINTER(MIB_IF_ROW2)
                )
                row = row_ptr.contents
                alias = str(row.Alias)
                # Keep exact interface alias (filter sub-layer filter drivers containing '-')
                if alias and row.OperStatus == 1:
                    counters[alias] = (int(row.InOctets), int(row.OutOctets))
            iphlpapi.FreeMibTable(pTable)
    except Exception as e:
        print(f"[Telemetry] Windows counter error: {e}", file=sys.stderr)
    return counters


def get_linux_counters() -> Dict[str, Tuple[int, int]]:
    """Query byte counters on Linux from /proc/net/dev."""
    counters = {}
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if ":" in line:
                    iface, data = line.split(":", 1)
                    iface = iface.strip()
                    fields = data.split()
                    if len(fields) >= 9:
                        rx = int(fields[0])
                        tx = int(fields[8])
                        counters[iface] = (rx, tx)
    except Exception as e:
        print(f"[Telemetry] Linux counter error: {e}", file=sys.stderr)
    return counters


def get_raw_counters() -> Dict[str, Tuple[int, int]]:
    """Cross-platform raw byte counters: returns {interface_name: (rx_bytes, tx_bytes)}."""
    if sys.platform.startswith("win"):
        return get_windows_counters()
    else:
        return get_linux_counters()


class BandwidthMonitor:
    """Tracks byte deltas over time to calculate real-time speeds in Mbps."""

    def __init__(self):
        self.last_time = time.monotonic()
        self.last_counters = get_raw_counters()

    def sample(self, active_interfaces: Optional[list] = None) -> Dict[str, any]:
        """
        Calculates instantaneous speeds since last sample.
        Returns detailed stats per adapter and total aggregate speed.
        """
        now = time.monotonic()
        elapsed = now - self.last_time
        if elapsed <= 0:
            elapsed = 0.001

        current_counters = get_raw_counters()
        adapter_stats = {}
        total_rx_mbps = 0.0
        total_tx_mbps = 0.0

        target_ifaces = active_interfaces if active_interfaces is not None else list(current_counters.keys())

        for iface in target_ifaces:
            curr_rx, curr_tx = current_counters.get(iface, (0, 0))
            prev_rx, prev_tx = self.last_counters.get(iface, (curr_rx, curr_tx))

            # Handle counter overflow or interface reset
            rx_delta = curr_rx - prev_rx if curr_rx >= prev_rx else 0
            tx_delta = curr_tx - prev_tx if curr_tx >= prev_tx else 0

            # Convert to Mbps (Megabits/sec) and MB/s (Megabytes/sec)
            rx_rate_bytes_sec = rx_delta / elapsed
            tx_rate_bytes_sec = tx_delta / elapsed

            rx_mbps = (rx_rate_bytes_sec * 8) / 1_000_000.0
            tx_mbps = (tx_rate_bytes_sec * 8) / 1_000_000.0
            rx_mb_s = rx_rate_bytes_sec / 1_000_000.0
            tx_mb_s = tx_rate_bytes_sec / 1_000_000.0

            adapter_stats[iface] = {
                "rx_mbps": round(rx_mbps, 2),
                "tx_mbps": round(tx_mbps, 2),
                "rx_mb_s": round(rx_mb_s, 2),
                "tx_mb_s": round(tx_mb_s, 2)
            }

            total_rx_mbps += rx_mbps
            total_tx_mbps += tx_mbps

        self.last_time = now
        self.last_counters = current_counters

        return {
            "elapsed_seconds": round(elapsed, 2),
            "adapters": adapter_stats,
            "total": {
                "rx_mbps": round(total_rx_mbps, 2),
                "tx_mbps": round(total_tx_mbps, 2),
                "rx_mb_s": round(total_rx_mbps / 8.0, 2),
                "tx_mb_s": round(total_tx_mbps / 8.0, 2)
            }
        }


if __name__ == "__main__":
    monitor = BandwidthMonitor()
    print("Monitoring network speeds for 3 seconds...")
    for _ in range(3):
        time.sleep(1.0)
        stats = monitor.sample(["Wi-Fi"])
        wifi = stats["adapters"].get("Wi-Fi", {})
        print(f"Wi-Fi -> Down: {wifi.get('rx_mbps', 0)} Mbps ({wifi.get('rx_mb_s', 0)} MB/s) | Up: {wifi.get('tx_mbps', 0)} Mbps")
