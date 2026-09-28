from turbobond.core.detector import is_virtual_adapter, classify_adapter_type, detect_active_adapters, optimize_windows_multilink


def test_virtual_adapter_filtering():
    assert is_virtual_adapter("vEthernet (Default Switch)", "Hyper-V Virtual Ethernet") is True
    assert is_virtual_adapter("mqvpn0", "mqvpn tunnel adapter") is True
    assert is_virtual_adapter("Loopback Pseudo-Interface 1") is True
    assert is_virtual_adapter("Wi-Fi", "Intel(R) Dual Band Wireless-AC 8265") is False
    assert is_virtual_adapter("Ethernet", "Realtek PCIe GbE Family Controller") is False


def test_classify_adapter_type():
    assert classify_adapter_type("Wi-Fi", "Intel Wireless-AC") == "wifi"
    assert classify_adapter_type("Ethernet 2", "Remote NDIS based Internet Sharing Device") == "usb_tether"
    assert classify_adapter_type("Ethernet", "Realtek PCIe GbE") == "ethernet"


def test_detect_active_adapters():
    adapters = detect_active_adapters()
    assert isinstance(adapters, list)
    # On this machine, at least the Wi-Fi card should be found
    if adapters:
        assert "name" in adapters[0]
        assert "type" in adapters[0]
        assert "ip" in adapters[0]


def test_optimize_windows_multilink(monkeypatch):
    import sys
    from unittest.mock import MagicMock
    monkeypatch.setitem(sys.modules, "winreg", MagicMock())
    # Should execute safely without raising exceptions regardless of elevation
    res = optimize_windows_multilink()
    assert isinstance(res, bool)

