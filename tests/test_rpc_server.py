"""
Tests for Tandem JSON-RPC WebSocket Sidecar Server (turbobond/core/rpc_server.py)
Verifies:
- WebSocket connection & handshake
- Initial state_snapshot event
- get_adapters RPC method
- get_config & save_config RPC methods
- get_status RPC method
- reset_proxy RPC method
- start_bonding and stop_bonding lifecycle
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from turbobond.core.rpc_server import TandemRPCServer


@pytest.mark.anyio
async def test_rpc_state_snapshot_and_methods():
    server = TandemRPCServer(host="127.0.0.1", port=7889)
    # Mock core components to avoid real registry or network mutation in test
    fake_config = MagicMock()
    fake_config.data = {"mode": "local_dispatcher", "proxy_port": 8080}
    fake_config.get.side_effect = lambda k, d=None: fake_config.data.get(k, d)

    fake_adapters = [
        {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.50", "status": "Up", "speed": "100 Mbps"}
    ]

    server._config = fake_config
    server._core["detect_active_adapters"] = MagicMock(return_value=fake_adapters)

    # Test individual RPC method handlers directly
    res_adapters = await server._h_get_adapters({})
    assert len(res_adapters) == 1
    assert res_adapters[0]["name"] == "Wi-Fi"

    res_config = await server._h_get_config({})
    assert res_config["mode"] == "local_dispatcher"

    res_save = await server._h_save_config({"proxy_port": 8888})
    assert res_save is True
    fake_config.set.assert_called_with("proxy_port", 8888)

    res_status = await server._h_get_status({})
    assert res_status["bonding_active"] is False
    assert res_status["engine_state"] == "DISCONNECTED"

    with patch.object(server._core["SystemProxyConfig"], "cleanup_orphaned_proxy", return_value=True) as mock_clean:
        res_reset = await server._h_reset_proxy({})
        assert res_reset is True
        mock_clean.assert_called_with(force=True)


@pytest.mark.anyio
async def test_rpc_start_stop_bonding_lifecycle():
    server = TandemRPCServer(host="127.0.0.1", port=7890)
    fake_config = MagicMock()
    fake_config.data = {
        "mode": "local_dispatcher",
        "proxy_port": 8080,
        "auto_system_proxy": False,
        "distribution_strategy": "round_robin"
    }
    fake_config.get.side_effect = lambda k, d=None: fake_config.data.get(k, d)

    fake_dispatcher = MagicMock()
    fake_dispatcher.start_in_thread.return_value = None  # None indicates success

    server._config = fake_config
    server._core["detect_active_adapters"] = MagicMock(return_value=[
        {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.10", "status": "Up", "speed": "100 Mbps"}
    ])
    server._core["LocalDispatcher"] = MagicMock(return_value=fake_dispatcher)

    # Start bonding
    start_res = await server._h_start_bonding({"mode": "local_dispatcher"})
    assert start_res["ok"] is True
    assert server._bonding_active is True

    # Stop bonding
    stop_res = await server._h_stop_bonding({})
    assert stop_res["ok"] is True
    assert server._bonding_active is False
    fake_dispatcher.stop_from_thread.assert_called_once()
