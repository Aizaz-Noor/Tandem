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
