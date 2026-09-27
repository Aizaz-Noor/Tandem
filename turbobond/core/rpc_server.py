"""
Tandem - JSON-RPC WebSocket Sidecar Server
Exposes the Python core (detector, dispatcher, proxy, telemetry, config,
engine manager) over a WebSocket channel so the Tauri frontend can reach it.

Listens on 127.0.0.1:7878 by default.
All messages follow a minimal JSON-RPC 2.0 envelope:
  Request:  {"id": <str|int>, "method": <str>, "params": <dict|null>}
  Response: {"id": <str|int>, "result": <any>}  |  {"id": <str|int>, "error": <str>}
  Event:    {"event": <str>, "data": <any>}      (server-initiated push)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import time
from typing import Any, Dict, Optional, Set

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
except ImportError:
    websockets = None  # type: ignore

BASE_PORT = 7878
logger = logging.getLogger("tandem.rpc")


# ---------------------------------------------------------------------------
# Lazy imports of core modules (so they can still be unit-tested without the
# full Tauri environment running)
# ---------------------------------------------------------------------------

def _import_core():
    """Import all core modules and return them as a namespace dict."""
    from turbobond.core.config import ConfigManager
    from turbobond.core.detector import detect_active_adapters
    from turbobond.core.dispatcher import LocalDispatcher
    from turbobond.core.engine_manager import EngineManager, TunnelState
    from turbobond.core.system_proxy import SystemProxyConfig
    from turbobond.core.telemetry import BandwidthMonitor
    return {
        "ConfigManager": ConfigManager,
        "detect_active_adapters": detect_active_adapters,
        "LocalDispatcher": LocalDispatcher,
        "EngineManager": EngineManager,
        "TunnelState": TunnelState,
        "SystemProxyConfig": SystemProxyConfig,
        "BandwidthMonitor": BandwidthMonitor,
    }


# ---------------------------------------------------------------------------
# RPC Server
# ---------------------------------------------------------------------------

class TandemRPCServer:
    """
    Manages state (dispatcher, engine, config, telemetry) and handles
    JSON-RPC messages from connected WebSocket clients.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = BASE_PORT):
        self.host = host
        self.port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._lock = asyncio.Lock()

        # Core objects — loaded lazily on first use
        self._core = _import_core()
        self._config: Optional[Any] = None
        self._dispatcher: Optional[Any] = None
        self._proxy: Optional[Any] = None
        self._engine: Optional[Any] = None
        self._telemetry: Optional[Any] = None
        self._bonding_active = False
        self._telemetry_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Startup helpers
    # ------------------------------------------------------------------

    def _ensure_config(self):
        if self._config is None:
            self._config = self._core["ConfigManager"]()
        return self._config

    def _ensure_proxy(self):
        if self._proxy is None:
            self._proxy = self._core["SystemProxyConfig"]()
        return self._proxy

    def _ensure_telemetry(self):
        if self._telemetry is None:
            self._telemetry = self._core["BandwidthMonitor"]()
        return self._telemetry

    # ------------------------------------------------------------------
    # WebSocket connection lifecycle
    # ------------------------------------------------------------------

    async def _handler(self, ws: "WebSocketServerProtocol"):
        self._clients.add(ws)
        logger.info("Client connected: %s", ws.remote_address)
        try:
            # Send initial state snapshot immediately on connect
            await self._send_state_snapshot(ws)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    await self._dispatch(ws, msg)
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"id": None, "error": "invalid JSON"}))
        except Exception as exc:  # connection dropped
            logger.debug("Client disconnected: %s", exc)
        finally:
            self._clients.discard(ws)

    async def _send_state_snapshot(self, ws: "WebSocketServerProtocol"):
        """Push current config + adapter list to a freshly connected client."""
        cfg = self._ensure_config()
        adapters = self._core["detect_active_adapters"]()
        payload = {
            "event": "state_snapshot",
            "data": {
                "config": cfg.data,
                "adapters": adapters,
                "bonding_active": self._bonding_active,
            }
        }
        await ws.send(json.dumps(payload))

    async def _broadcast(self, event: str, data: Any):
        """Push an event to every connected client."""
        if not self._clients:
            return
        msg = json.dumps({"event": event, "data": data})
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(self, ws: "WebSocketServerProtocol", msg: Dict):
        rpc_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}

        handler = {
            "get_adapters": self._h_get_adapters,
            "get_config": self._h_get_config,
            "save_config": self._h_save_config,
            "start_bonding": self._h_start_bonding,
            "stop_bonding": self._h_stop_bonding,
            "get_status": self._h_get_status,
            "reset_proxy": self._h_reset_proxy,
            "start_cloud": self._h_start_cloud,
            "stop_cloud": self._h_stop_cloud,
            "export_profile": self._h_export_profile,
            "import_profile": self._h_import_profile,
        }.get(method)

        if handler is None:
            await ws.send(json.dumps({"id": rpc_id, "error": f"unknown method: {method}"}))
            return

        try:
            result = await handler(params)
            await ws.send(json.dumps({"id": rpc_id, "result": result}))
        except Exception as exc:
            logger.exception("RPC error in %s", method)
            await ws.send(json.dumps({"id": rpc_id, "error": str(exc)}))

    # ------------------------------------------------------------------
    # RPC method handlers
    # ------------------------------------------------------------------

    async def _h_get_adapters(self, _params) -> list:
        return self._core["detect_active_adapters"]()

    async def _h_get_config(self, _params) -> dict:
        return self._ensure_config().data

    async def _h_save_config(self, params: dict) -> bool:
        cfg = self._ensure_config()
        for key, value in params.items():
            cfg.set(key, value)
        return True

    async def _h_start_bonding(self, params: dict) -> dict:
        if self._bonding_active:
            return {"ok": True, "message": "already running"}

        cfg = self._ensure_config()
        mode = params.get("mode", cfg.get("mode", "local_dispatcher"))

        if mode == "local_dispatcher":
            adapters = self._core["detect_active_adapters"]()
            ips = [a["ip"] for a in adapters if a.get("ip") and a["ip"] != "Pending IP..."]
            if not ips:
                return {"ok": False, "message": "no adapters with valid IP found"}

            selected = params.get("selected_adapters") or cfg.get("selected_adapters") or []
            if selected:
                selected_ips = [a["ip"] for a in adapters if a["name"] in selected and a.get("ip") and a["ip"] != "Pending IP..."]
                if selected_ips:
                    ips = selected_ips

            port = int(cfg.get("proxy_port", 8080))
            strategy = cfg.get("distribution_strategy", "round_robin")

            self._dispatcher = self._core["LocalDispatcher"](
                host="127.0.0.1",
                port=port,
                adapter_ips=ips,
                strategy=strategy,
            )
            try:
                self._dispatcher.start_in_thread(timeout=3.0)
            except Exception as exc:
                self._dispatcher = None
                return {"ok": False, "message": f"dispatcher failed to start: {exc}"}

            if cfg.get("auto_system_proxy", True):
                self._ensure_proxy().enable_proxy("127.0.0.1", port)

        elif mode == "cloud_bonding":
            adapters = self._core["detect_active_adapters"]()
            selected = params.get("selected_adapters") or cfg.get("selected_adapters") or [a["name"] for a in adapters]
            server_host = params.get("server_host", cfg.get("server_host", ""))
            server_port = int(params.get("server_port", cfg.get("server_port", 443)))
            auth_key = params.get("auth_key", cfg.get("auth_key", ""))
            scheduler = cfg.get("scheduler", "wlb")
            insecure = cfg.get("insecure", True)
            dns_servers = cfg.get("dns", ["1.1.1.1", "8.8.8.8"])

            self._engine = self._core["EngineManager"]()

            def _on_state(state, message=""):
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._broadcast("engine_state", {
                            "state": state.name if hasattr(state, "name") else str(state),
                            "message": message
                        }),
                        self._loop,
                    )

            self._engine.on_state_change = _on_state
            started = self._engine.start(
                server_host=server_host,
                server_port=server_port,
                auth_key=auth_key,
                adapter_names=selected,
                scheduler=scheduler,
                insecure=insecure,
                dns_servers=dns_servers,
            )
            if not started:
                self._engine = None
                return {"ok": False, "message": "cloud bonding engine failed to start"}

        self._bonding_active = True
        await self._broadcast("bonding_state", {"active": True, "mode": mode})
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        return {"ok": True, "mode": mode}

    async def _h_stop_bonding(self, _params) -> dict:
        if not self._bonding_active:
            return {"ok": True, "message": "already stopped"}

        if self._dispatcher is not None:
            self._dispatcher.stop_from_thread()
            self._dispatcher = None

        if self._engine is not None:
            self._engine.stop()
            self._engine = None

        self._ensure_proxy().disable_proxy()
        self._bonding_active = False

        if self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()

        await self._broadcast("bonding_state", {"active": False})
        return {"ok": True}

    async def _h_get_status(self, _params) -> dict:
        engine_state = "DISCONNECTED"
        if self._engine:
            try:
                engine_state = self._engine.state.name
            except Exception:
                pass
        return {
            "bonding_active": self._bonding_active,
            "engine_state": engine_state,
        }

    async def _h_reset_proxy(self, _params) -> bool:
        self._core["SystemProxyConfig"].cleanup_orphaned_proxy(force=True)
        return True

    async def _h_start_cloud(self, params: dict) -> dict:
        params["mode"] = "cloud_bonding"
        return await self._h_start_bonding(params)

    async def _h_stop_cloud(self, _params) -> dict:
        return await self._h_stop_bonding(None)

    async def _h_export_profile(self, params: dict) -> bool:
        path = params.get("path", "")
        if not path:
            raise ValueError("path is required")
        return self._ensure_config().export_profile(path)

    async def _h_import_profile(self, params: dict) -> bool:
        path = params.get("path", "")
        if not path:
            raise ValueError("path is required")
        return self._ensure_config().import_profile(path)

    # ------------------------------------------------------------------
    # Telemetry push loop
    # ------------------------------------------------------------------

    async def _telemetry_loop(self):
        monitor = self._ensure_telemetry()
        while self._bonding_active:
            try:
                await asyncio.sleep(1.0)
                stats = monitor.sample()
                await self._broadcast("telemetry", stats)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Telemetry loop error: %s", exc)

    # ------------------------------------------------------------------
    # Server start
    # ------------------------------------------------------------------

    async def run(self):
        if websockets is None:
            raise RuntimeError("websockets package not installed — run: pip install websockets")
        self._loop = asyncio.get_running_loop()
        logger.info("Tandem RPC server listening on ws://%s:%d", self.host, self.port)
        async with websockets.serve(self._handler, self.host, self.port):
            await asyncio.Future()  # run forever

    def start_in_thread(self) -> threading.Thread:
        """Start the async server in a background daemon thread."""
        def _run():
            asyncio.run(self.run())

        t = threading.Thread(target=_run, daemon=True, name="tandem-rpc")
        t.start()
        return t


# ---------------------------------------------------------------------------
# CLI entry-point (python -m turbobond.core.rpc_server)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = TandemRPCServer()
    asyncio.run(server.run())
