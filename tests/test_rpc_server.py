import asyncio
import json
from unittest.mock import MagicMock, patch
import pytest
import websockets
from turbobond.core.config import ConfigManager
from turbobond.core.rpc_server import TandemRPCServer
from turbobond.core.engine_manager import TunnelState

ADAPTERS = [{"name": "Wi-Fi", "ip": "192.0.2.2"}, {"name": "Phone", "ip": "192.0.2.3"}]

@pytest.fixture
def server(tmp_path):
    cfg = ConfigManager(str(tmp_path / "config.json"))
    cfg.update({"auto_connect_on_launch": False, "auto_system_proxy": False})
    instance = TandemRPCServer(port=0, token="test-token", config=cfg)
    with patch("turbobond.core.rpc_server.is_elevated", return_value=True), \
         patch("turbobond.core.rpc_server.detect_active_adapters", return_value=ADAPTERS), \
         patch("turbobond.core.rpc_server.LocalDispatcher") as dispatcher, \
         patch("turbobond.core.rpc_server.SystemProxyConfig") as proxy, \
         patch("turbobond.core.rpc_server.EngineManager") as engine:
        instance.fake_dispatcher = dispatcher.return_value
        instance.fake_proxy = proxy.return_value
        instance.fake_engine = engine.return_value
        instance.fake_engine.state = TunnelState.CONNECTING
        yield instance


def test_start_stop_and_repeat(server):
    async def run():
        result = await server._h_start_bonding({})
        assert result["ok"] and server._bonding_active
        await server._h_start_bonding({})
        server.fake_dispatcher.start_in_thread.assert_called_once()
        await server._h_stop_bonding({})
        await server._h_stop_bonding({})
        server.fake_dispatcher.stop_from_thread.assert_called_once()
        server.fake_proxy.disable_proxy.assert_not_called()
        assert server._dispatcher is None
    asyncio.run(run())


def test_failed_proxy_rolls_back(server):
    server._config.update({"auto_system_proxy": True})
    server.fake_proxy.enable_proxy.return_value = False
    async def run():
        with pytest.raises(RuntimeError, match="system proxy"):
            await server._h_start_bonding({})
        assert server._mode is None and not server._bonding_active
        server.fake_dispatcher.stop_from_thread.assert_called_once()
        server.fake_proxy.disable_proxy.assert_called_once()
    asyncio.run(run())


def test_start_failure_stops_partial_dispatcher(server):
    server.fake_dispatcher.start_in_thread.side_effect = TimeoutError("bind timed out")
    async def run():
        with pytest.raises(TimeoutError):
            await server._h_start_bonding({})
        server.fake_dispatcher.stop_from_thread.assert_called_once()
        assert server._mode is None
    asyncio.run(run())


def test_unavailable_selected_adapter_does_not_fallback(server):
    async def run():
        with pytest.raises(ValueError, match="selected adapters"):
            await server._h_start_bonding({"selected_adapters": ["Missing"]})
        server.fake_dispatcher.start_in_thread.assert_not_called()
    asyncio.run(run())


def test_invalid_mode_and_kill_switch(server):
    async def run():
        with pytest.raises(ValueError):
            await server._h_start_bonding({"mode": "invalid"})
        server._config.data["kill_switch"] = True
        with pytest.raises(ValueError, match="Kill switch"):
            await server._h_start_bonding({})
        assert server._mode is None
    asyncio.run(run())


def test_cloud_arguments_and_truthful_state(server):
    server._config.update({"server_host": "vpn.example.test", "auth_key": "test-secret", "auto_reconnect": False})
    async def run():
        await server._h_start_cloud({"selected_adapters": ["Phone"]})
        assert not server._bonding_active
        args = server.fake_engine.start.call_args.kwargs
        assert args["adapter_names"] == ["Phone"] and args["auth_key"] == "test-secret"
        await server._engine_changed(server.fake_engine, TunnelState.CONNECTED, "connected")
        assert server._bonding_active
        await server._engine_changed(server.fake_engine, TunnelState.ERROR, "bad test-secret")
        assert not server._bonding_active and server._engine is None
        assert "test-secret" not in json.dumps(list(server._logs))
    asyncio.run(run())


def test_settings_rejected_while_connected(server):
    async def run():
        await server._h_start_bonding({})
        with pytest.raises(ValueError, match="Disconnect"):
            await server._h_save_config({"proxy_port": 8081})
        await server._h_stop_bonding({})
    asyncio.run(run())


def test_concurrent_start_is_idempotent(server):
    async def run():
        await asyncio.gather(server._h_start_bonding({}), server._h_start_bonding({}))
        server.fake_dispatcher.start_in_thread.assert_called_once()
        await server._h_stop_bonding({})
    asyncio.run(run())


def test_rpc_auth_origin_validation_and_shutdown(server):
    async def run():
        ready = asyncio.Event()
        task = asyncio.create_task(server.run(ready=lambda _: ready.set()))
        await asyncio.wait_for(ready.wait(), 5)
        url = f"ws://127.0.0.1:{server.port}"
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({"token": "wrong"}))
                with pytest.raises(websockets.ConnectionClosed):
                    await ws.recv()
            with pytest.raises(Exception):
                async with websockets.connect(url, origin="https://untrusted.example"):
                    pytest.fail("Untrusted origin accepted")
            async with websockets.connect(url, origin="http://tauri.localhost") as ws:
                await ws.send(json.dumps({"token": server.token}))
                snapshot = json.loads(await ws.recv())
                assert snapshot["event"] == "state_snapshot"
                for msg in ([], {"id": 1, "method": "get_status", "params": []}, {"id": 2, "method": "export_profile", "params": {"path": "anything"}}):
                    await ws.send(json.dumps(msg))
                    while True:
                        reply = json.loads(await ws.recv())
                        if "id" in reply:
                            assert "error" in reply
                            break
                await ws.send(json.dumps({"id": 3, "method": "get_status"}))
                while True:
                    reply = json.loads(await ws.recv())
                    if reply.get("id") == 3:
                        assert reply["result"]["bonding_active"] is False
                        break
        finally:
            server.request_shutdown()
            await asyncio.wait_for(task, 5)
    asyncio.run(run())


def test_default_server_never_allows_unauthenticated_clients(tmp_path):
    config = ConfigManager(str(tmp_path / "config.json"))
    first = TandemRPCServer(config=config)
    second = TandemRPCServer(config=config)
    assert isinstance(first.token, str) and len(first.token) >= 32
    assert first.token != second.token
