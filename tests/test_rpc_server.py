"""
Tests for Tandem JSON-RPC WebSocket Sidecar Server (turbobond/core/rpc_server.py)
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from turbobond.core.rpc_server import TandemRPCServer


@pytest.mark.anyio
async def test_rpc_state_snapshot_and_methods():
    fake_config = MagicMock()
    fake_config.data = {"mode": "local_dispatcher", "proxy_port": 8080}
    fake_config.get.side_effect = lambda k, d=None: fake_config.data.get(k, d)

    fake_adapters = [
        {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.50", "status": "Up", "speed": "100 Mbps"}
    ]

    server = TandemRPCServer(host="127.0.0.1", port=7889, config=fake_config)

    with patch("turbobond.core.rpc_server.detect_active_adapters", return_value=fake_adapters):
        res_adapters = await server._h_get_adapters({})
        assert len(res_adapters) == 1
        assert res_adapters[0]["name"] == "Wi-Fi"

    res_config = await server._h_get_config({})
    assert res_config["mode"] == "local_dispatcher"

    with patch("turbobond.core.rpc_server.validate_patch"):
        res_save = await server._h_save_config({"proxy_port": 8888})
        assert res_save is not None
        fake_config.update.assert_called_with({"proxy_port": 8888})

    res_status = await server._h_get_status({})
    assert res_status["bonding_active"] is False
    assert res_status["engine_state"] == "DISCONNECTED"

    with patch("turbobond.core.rpc_server.SystemProxyConfig.cleanup_orphaned_proxy", return_value=True) as mock_clean:
        res_reset = await server._h_reset_proxy({})
        assert res_reset is True
        mock_clean.assert_called_with(True)


@pytest.mark.anyio
async def test_rpc_start_stop_bonding_lifecycle():
    fake_config = MagicMock()
    fake_config.data = {
        "mode": "local_dispatcher",
        "proxy_port": 8080,
        "auto_system_proxy": False,
        "distribution_strategy": "round_robin"
    }
    fake_config.get.side_effect = lambda k, d=None: fake_config.data.get(k, d)

    fake_dispatcher = MagicMock()
    fake_dispatcher.start_in_thread.return_value = None

    server = TandemRPCServer(host="127.0.0.1", port=7890, config=fake_config)

    with patch("turbobond.core.rpc_server.detect_active_adapters", return_value=[
        {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.10", "status": "Up", "speed": "100 Mbps"}
    ]), patch("turbobond.core.rpc_server.LocalDispatcher", return_value=fake_dispatcher):
        start_res = await server._h_start_bonding({"mode": "local_dispatcher"})
        assert start_res["ok"] is True
        assert server._bonding_active is True

        stop_res = await server._h_stop_bonding({})
        assert stop_res["ok"] is True
        assert server._bonding_active is False
        fake_dispatcher.stop_from_thread.assert_called_once()
