"""Authenticated desktop sidecar. Network mutations are serialized and reversible."""
from __future__ import annotations
import asyncio
from collections import deque
import ipaddress
import json
import logging
import os
import secrets
import sys
import threading
from datetime import datetime, timezone
from typing import Any
import websockets
from turbobond.core.config import ConfigManager, validate_patch
from turbobond.core.detector import detect_active_adapters
from turbobond.core.dispatcher import LocalDispatcher
from turbobond.core.engine_manager import EngineManager, TunnelState, is_elevated
from turbobond.core.system_proxy import SystemProxyConfig
from turbobond.core.telemetry import BandwidthMonitor

BASE_PORT = 7878
logger = logging.getLogger("tandem.rpc")
ALLOWED_ORIGINS = [None, "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost", "http://localhost:1420", "http://127.0.0.1:1420"]

class TandemRPCServer:
    def __init__(self, host="127.0.0.1", port=BASE_PORT, token=None, config=None):
        if host != "127.0.0.1":
            raise ValueError("The desktop RPC server must bind to loopback")
        self.host, self.port = host, port
        self.token = token or secrets.token_urlsafe(32)
        self._config = config
        self._clients = set()
        self._lock = asyncio.Lock()
        self._detector_lock = asyncio.Lock()
        self._shutdown = asyncio.Event()
        self._dispatcher = self._engine = self._proxy = None
        self._telemetry_task = None
        self._adapter_task = None
        self._loop = None
        self._bonding_active = False
        self._mode = None
        self._active_names = []
        self._selected = []
        self._adapters = []
        self._logs = deque(maxlen=500)

    def _ensure_config(self):
        if self._config is None:
            self._config = ConfigManager()
        return self._config

    async def _log(self, level, message):
        # Credentials must never appear in events or retained diagnostics.
        key = self._ensure_config().get("auth_key", "")
        message = str(message)
        if key:
            message = message.replace(key, "[redacted]")
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": message}
        self._logs.append(entry)
        await self._broadcast("log", entry)

    async def _broadcast(self, event, data):
        payload = json.dumps({"event": event, "data": data})
        async def send(ws):
            try:
                await asyncio.wait_for(ws.send(payload), 2)
            except Exception:
                self._clients.discard(ws)
        await asyncio.gather(*(send(ws) for ws in list(self._clients)))

    async def _detect(self):
        async with self._detector_lock:
            self._adapters = await asyncio.to_thread(detect_active_adapters)
            return self._adapters

    async def _handler(self, ws):
        try:
            if self.token:
                raw = await asyncio.wait_for(ws.recv(), 5)
                auth = json.loads(raw)
                supplied = auth.get("token") if isinstance(auth, dict) else None
                if not isinstance(supplied, str) or not secrets.compare_digest(supplied, self.token):
                    await ws.close(code=1008, reason="Authentication required")
                    return
            if not self._adapters:
                await self._detect()
            await ws.send(json.dumps({"event": "state_snapshot", "data": {
                "config": self._ensure_config().data, "adapters": self._adapters,
                "bonding_active": self._bonding_active,
                "engine_state": self._engine.state.name if self._engine else "DISCONNECTED",
                "logs": list(self._logs),
            }}))
            self._clients.add(ws)
            async for raw in ws:
                try:
                    await self._dispatch(ws, json.loads(raw))
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"id": None, "error": "Invalid JSON"}))
        except (websockets.ConnectionClosed, asyncio.TimeoutError, ValueError):
            pass
        finally:
            self._clients.discard(ws)

    async def _dispatch(self, ws, msg):
        rpc_id = msg.get("id") if isinstance(msg, dict) else None
        try:
            if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
                raise ValueError("Request must contain a method")
            if type(rpc_id) not in (str, int):
                raise ValueError("Request must contain a string or integer id")
            params = msg.get("params")
            if params is None:
                params = {}
            if not isinstance(params, dict):
                raise ValueError("Parameters must be an object")
            methods = {
                "get_adapters": self._h_get_adapters, "get_config": self._h_get_config,
                "save_config": self._h_save_config, "start_bonding": self._h_start_bonding,
                "stop_bonding": self._h_stop_bonding, "get_status": self._h_get_status,
                "start_cloud": self._h_start_cloud, "stop_cloud": self._h_stop_bonding,
                "reset_proxy": self._h_reset_proxy,
            }
            handler = methods.get(msg["method"])
            if handler is None:
                raise ValueError("Unknown method")
            result = await handler(params)
            response = {"id": rpc_id, "result": result}
        except Exception as exc:
            # No caller-controlled filesystem operations are exposed over RPC.
            await self._log("error", str(exc))
            response = {"id": rpc_id, "error": str(exc)}
        await ws.send(json.dumps(response))

    async def _h_get_config(self, params):
        return self._ensure_config().data

    async def _h_save_config(self, params):
        validate_patch(params)
        async with self._lock:
            if self._mode is not None:
                raise ValueError("Disconnect before changing settings")
            await asyncio.to_thread(self._ensure_config().update, params)
            await self._broadcast("config", self._ensure_config().data)
            return self._ensure_config().data

    @staticmethod
    def _usable(adapters, selected):
        result = []
        for adapter in adapters:
            if selected and adapter.get("name") not in selected:
                continue
            try:
                ip = ipaddress.ip_address(adapter.get("ip", ""))
                if ip.version == 4 and not ip.is_unspecified and not ip.is_link_local:
                    result.append(adapter)
            except ValueError:
                pass
        return result

    async def _h_get_adapters(self, params):
        adapters = await self._detect()
        async with self._lock:
            if self._dispatcher:
                usable = self._usable(adapters, self._selected)
                self._active_names = [a["name"] for a in usable]
                self._dispatcher.update_adapters([a["ip"] for a in usable],
                    {a["ip"]: self._ensure_config().get("adapter_weights", {}).get(a["name"], 1) for a in usable})
        await self._broadcast("adapters", adapters)
        return adapters

    async def _h_start_bonding(self, params):
        async with self._lock:
            if self._mode is not None:
                return {"ok": True, "mode": self._mode, "message": "Already started"}
            cfg = self._ensure_config()
            mode = params.get("mode", cfg.get("mode"))
            validate_patch({"mode": mode})
            if cfg.get("kill_switch"):
                raise ValueError("Kill switch is unsupported. Disable it in settings before connecting.")
            selected = params.get("selected_adapters", cfg.get("selected_adapters", []))
            validate_patch({"selected_adapters": selected})
            adapters = self._usable(await self._detect(), selected)
            if not adapters:
                raise ValueError("No selected adapters have a usable IPv4 address")
            self._active_names = [a["name"] for a in adapters]
            self._selected = list(selected)
            self._loop = asyncio.get_running_loop()
            self._mode = mode
            try:
                if mode == "local_dispatcher":
                    self._dispatcher = LocalDispatcher(
                        host="127.0.0.1", port=cfg.get("proxy_port"),
                        adapter_ips=[a["ip"] for a in adapters], strategy=cfg.get("distribution_strategy"),
                        adapter_weights={a["ip"]: cfg.get("adapter_weights", {}).get(a["name"], 1) for a in adapters})
                    await asyncio.to_thread(self._dispatcher.start_in_thread)
                    if cfg.get("auto_system_proxy"):
                        self._proxy = SystemProxyConfig()
                        if not await asyncio.to_thread(self._proxy.enable_proxy, "127.0.0.1", cfg.get("proxy_port")):
                            raise RuntimeError("Cannot configure system proxy")
                    self._bonding_active = True
                else:
                    cloud = {k: params.get(k, cfg.get(k)) for k in ("server_host", "server_port", "auth_key")}
                    validate_patch(cloud)
                    if not cloud["server_host"].strip() or not cloud["auth_key"].strip():
                        raise ValueError("Cloud bonding requires a server host and auth key")
                    if sys.platform.startswith("win") and not is_elevated():
                        raise RuntimeError("Cloud bonding requires Administrator rights. Close Tandem and run it as Administrator.")
                    engine = EngineManager()
                    self._engine = engine
                    engine.auto_reconnect = cfg.get("auto_reconnect")
                    def changed(state, message=""):
                        if self._loop and not self._loop.is_closed():
                            asyncio.run_coroutine_threadsafe(self._engine_changed(engine, state, message), self._loop)
                    engine.on_state_change = changed
                    started = await asyncio.to_thread(engine.start, **cloud, adapter_names=self._active_names,
                        scheduler=cfg.get("scheduler"), insecure=cfg.get("insecure"), dns_servers=cfg.get("dns"))
                    if not started:
                        raise RuntimeError("Cloud engine failed to start; check engine installation and adapters")
                self._telemetry_task = asyncio.create_task(self._telemetry_loop())
                await self._broadcast("bonding_state", {"active": self._bonding_active, "mode": mode})
                await self._log("info", f"Started {mode}")
                return {"ok": True, "mode": mode}
            except Exception:
                await self._stop()
                raise

    async def _engine_changed(self, engine, state, message):
        async with self._lock:
            if self._engine is not engine:
                return
            self._bonding_active = state == TunnelState.CONNECTED
            await self._broadcast("engine_state", {"state": state.name, "message": message})
            await self._broadcast("bonding_state", {"active": self._bonding_active, "mode": self._mode})
            await self._log("error" if state == TunnelState.ERROR else "info", message or state.name)
            if state in (TunnelState.ERROR, TunnelState.DISCONNECTED) and not engine.auto_reconnect:
                await self._stop()

    async def _h_start_cloud(self, params):
        return await self._h_start_bonding({**params, "mode": "cloud_bonding"})

    async def _stop(self):
        errors = []
        task, self._telemetry_task = self._telemetry_task, None
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # Restore routing before stopping the listener. Keep failed resources for retry.
        for attr, method in (("_proxy", "disable_proxy"), ("_engine", "stop"), ("_dispatcher", "stop_from_thread")):
            obj = getattr(self, attr)
            if obj is None:
                continue
            if attr == "_engine":
                obj.on_state_change = None
            try:
                result = await asyncio.to_thread(getattr(obj, method))
                if result is False:
                    raise RuntimeError(f"Failed to restore {attr[1:]}")
                setattr(self, attr, None)
            except Exception as exc:
                errors.append(str(exc))
        self._bonding_active = False
        self._mode = None if not errors else self._mode
        self._active_names = []
        await self._broadcast("bonding_state", {"active": False})
        await self._broadcast("engine_state", {"state": "DISCONNECTED"})
        if errors:
            raise RuntimeError("; ".join(errors))

    async def _h_stop_bonding(self, params):
        async with self._lock:
            await self._stop()
            await self._log("info", "Disconnected")
            return {"ok": True}

    async def _h_get_status(self, params):
        return {"bonding_active": self._bonding_active, "mode": self._mode,
                "engine_state": self._engine.state.name if self._engine else "DISCONNECTED"}

    async def _h_reset_proxy(self, params):
        async with self._lock:
            await self._stop()
            if not await asyncio.to_thread(SystemProxyConfig.cleanup_orphaned_proxy, True):
                raise RuntimeError("Unable to reset system proxy")
            return True

    async def _telemetry_loop(self):
        monitor = await asyncio.to_thread(BandwidthMonitor)
        while self._mode is not None:
            await asyncio.sleep(1)
            try:
                stats = await asyncio.to_thread(monitor.sample, list(self._active_names))
                await self._broadcast("telemetry", stats)
            except Exception as exc:
                await self._log("warn", f"Telemetry unavailable: {exc}")

    async def _watch_adapters(self):
        while not self._shutdown.is_set():
            try:
                await self._h_get_adapters({})
            except Exception as exc:
                await self._log("warn", f"Adapter refresh failed: {exc}")
            await asyncio.sleep(5)

    async def run(self, ready=None):
        self._loop = asyncio.get_running_loop()
        try:
            async with websockets.serve(self._handler, self.host, self.port,
                    origins=ALLOWED_ORIGINS, max_size=65536, max_queue=16) as server:
                self.port = server.sockets[0].getsockname()[1]
                if ready:
                    ready({"url": f"ws://127.0.0.1:{self.port}", "token": self.token})
                self._adapter_task = asyncio.create_task(self._watch_adapters())
                if self._ensure_config().get("auto_connect_on_launch"):
                    try:
                        await self._h_start_bonding({})
                    except Exception as exc:
                        await self._log("error", f"Auto-connect failed: {exc}")
                await self._shutdown.wait()
                await self._h_stop_bonding({})
        finally:
            if self._adapter_task:
                self._adapter_task.cancel()
                await asyncio.gather(self._adapter_task, return_exceptions=True)
            await self._h_stop_bonding({})

    def request_shutdown(self):
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._shutdown.set)

    def start_in_thread(self):
        thread = threading.Thread(target=lambda: asyncio.run(self.run()), daemon=True)
        thread.start()
        return thread

if __name__ == "__main__":
    asyncio.run(TandemRPCServer().run())
