import time
import pytest
from turbobond.core.telemetry import BandwidthMonitor


def test_telemetry_sample():
    monitor = BandwidthMonitor()
    time.sleep(0.1)
    stats = monitor.sample()
    assert "adapters" in stats
    assert "total" in stats
    assert "rx_mbps" in stats["total"]
    assert "tx_mbps" in stats["total"]
    assert isinstance(stats["total"]["rx_mbps"], float)
    assert isinstance(stats["total"]["tx_mbps"], float)


def test_selected_interfaces_and_consistent_units(monkeypatch):
    monkeypatch.setattr("turbobond.core.telemetry.time.monotonic", lambda: 1)
    monkeypatch.setattr("turbobond.core.telemetry.get_raw_counters", lambda: {"wifi": (0, 0), "vpn": (0, 0)})
    monitor = BandwidthMonitor()
    monkeypatch.setattr("turbobond.core.telemetry.time.monotonic", lambda: 2)
    monkeypatch.setattr("turbobond.core.telemetry.get_raw_counters", lambda: {"wifi": (1000000, 500000), "vpn": (1000000, 500000)})
    stats = monitor.sample(["wifi"])
    assert stats["total"]["rx_mbps"] == 8
    assert stats["total"]["rx_mb_s"] == stats["adapters"]["wifi"]["rx_mb_s"] == 1
    assert monitor.sample([])["total"]["rx_mbps"] == 0
