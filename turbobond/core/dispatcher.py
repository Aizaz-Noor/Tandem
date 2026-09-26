"""
TurboBond - Local Multi-WAN Dispatcher
Async SOCKS5 + HTTP CONNECT proxy that distributes outgoing TCP connections
across multiple network adapters using socket.bind() for bandwidth aggregation.
"""

import asyncio
import socket
import sys
import threading
import struct
from typing import List, Dict, Optional, Tuple, Callable

class LocalDispatcher:
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 8080,
        adapter_ips: Optional[List[str]] = None,
        strategy: str = 'round_robin',
        on_stats_update: Optional[Callable] = None
    ):
        self.host = host
        self.port = port
        self.adapter_ips = adapter_ips or []
        self.strategy = strategy
        self.on_stats_update = on_stats_update
        self._server = None
        self._loop = None
        self._thread = None
        self._stop_event = None
        self._started_event = threading.Event()
        self._startup_error: Optional[Exception] = None
        self._round_robin_index = 0
        self._lock = threading.Lock()
        
        # Stats dictionary
        self._stats = {}
        self._init_stats()

    def _init_stats(self):
        with self._lock:
            for ip in self.adapter_ips:
                if ip not in self._stats:
                    self._stats[ip] = {
                        'connections_total': 0,
                        'connections_active': 0,
                        'bytes_rx': 0,
                        'bytes_tx': 0
                    }

    def update_adapters(self, adapter_ips: List[str]):
        with self._lock:
            self.adapter_ips = list(adapter_ips)
            # Initialize stats for new adapters
            for ip in self.adapter_ips:
                if ip not in self._stats:
                    self._stats[ip] = {
                        'connections_total': 0,
                        'connections_active': 0,
                        'bytes_rx': 0,
                        'bytes_tx': 0
                    }
            self._round_robin_index = 0

    def get_stats(self) -> Dict:
        with self._lock:
            total_active = 0
            total_total = 0
            total_rx = 0
            total_tx = 0
            
            per_adapter = {}
            for ip, stat in self._stats.items():
                per_adapter[ip] = dict(stat)
                total_active += stat['connections_active']
                total_total += stat['connections_total']
                total_rx += stat['bytes_rx']
                total_tx += stat['bytes_tx']
                
            return {
                'adapters': per_adapter,
                'total': {
                    'connections_total': total_total,
                    'connections_active': total_active,
                    'bytes_rx': total_rx,
                    'bytes_tx': total_tx
                }
            }

    def _notify_stats(self):
        if self.on_stats_update:
            try:
                self.on_stats_update(self.get_stats())
            except Exception as e:
                print(f"[Dispatcher] Stats update callback failed: {e}", file=sys.stderr)

    def _update_stat(self, adapter_ip: str, key: str, value: int, relative: bool = False):
        with self._lock:
            if adapter_ip not in self._stats:
                return
            if relative:
                self._stats[adapter_ip][key] += value
            else:
                self._stats[adapter_ip][key] = value
        self._notify_stats()

    def _select_adapter(self) -> Optional[str]:
        with self._lock:
            if not self.adapter_ips:
                return None
            
            if self.strategy == 'round_robin':
                ip = self.adapter_ips[self._round_robin_index % len(self.adapter_ips)]
                self._round_robin_index += 1
                return ip
            else:
                # Default fallback is round robin
                ip = self.adapter_ips[self._round_robin_index % len(self.adapter_ips)]
                self._round_robin_index += 1
                return ip

    async def start(self):
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        try:
            self._server = await asyncio.start_server(
                self._handle_client, self.host, self.port
            )
            print(f"[Dispatcher] Started proxy server on {self.host}:{self.port}")
            self._started_event.set()
            await self._stop_event.wait()
        except Exception as e:
            self._startup_error = e
            self._started_event.set()
            print(f"[Dispatcher] Failed to start server: {e}", file=sys.stderr)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._stop_event:
            self._stop_event.set()
        print("[Dispatcher] Server stopped")

    def start_in_thread(self, timeout: float = 3.0):
        if self._thread and self._thread.is_alive():
            return

        self._started_event.clear()
        self._startup_error = None
            
        def _run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
            loop.close()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()

        # Wait for the server socket to successfully bind or fail
        if not self._started_event.wait(timeout=timeout):
            raise TimeoutError("Timed out waiting for dispatcher proxy server to start.")
        if self._startup_error:
            raise self._startup_error

    def stop_from_thread(self):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.stop(), self._loop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # Read first byte to detect protocol
            initial_data = await reader.read(1)
            if not initial_data:
                writer.close()
                await writer.wait_closed()
                return

            if initial_data[0] == 0x05:
                await self._handle_socks5(reader, writer, initial_data)
            else:
                # Might be HTTP CONNECT
                line = initial_data + await reader.readuntil(b'\r\n')
                await self._handle_http_connect(reader, writer, line)
        except Exception as e:
            print(f"[Dispatcher] Client handling error: {e}", file=sys.stderr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_socks5(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, initial_byte: bytes):
        try:
            # SOCKS5 greeting
            nmethods_data = await reader.readexactly(1)
            nmethods = nmethods_data[0]
            methods = await reader.readexactly(nmethods)
            
            # Send NO AUTH (0x05, 0x00)
            writer.write(b'\x05\x00')
            await writer.drain()

            # Connect request
            req_header = await reader.readexactly(4)
            version, cmd, rsv, atyp = req_header

            if cmd != 0x01: # Only CONNECT supported
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                raise Exception("Unsupported SOCKS5 command")

            # Parse destination
            dst_addr = ""
            if atyp == 0x01: # IPv4
                addr_data = await reader.readexactly(4)
                dst_addr = socket.inet_ntoa(addr_data)
            elif atyp == 0x03: # Domain
                domain_len_data = await reader.readexactly(1)
                domain_len = domain_len_data[0]
                addr_data = await reader.readexactly(domain_len)
                dst_addr = addr_data.decode('utf-8')
            elif atyp == 0x04: # IPv6
                addr_data = await reader.readexactly(16)
                dst_addr = socket.inet_ntop(socket.AF_INET6, addr_data)
            else:
                writer.write(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                raise Exception("Unsupported SOCKS5 ATYP")

            port_data = await reader.readexactly(2)
            dst_port = struct.unpack('!H', port_data)[0]

            await self._connect_and_relay(reader, writer, dst_addr, dst_port, is_socks=True)

        except Exception as e:
            print(f"[Dispatcher] SOCKS5 error: {e}", file=sys.stderr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_http_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, initial_line: bytes):
        try:
            line_str = initial_line.decode('utf-8', errors='ignore')
            if not line_str.startswith('CONNECT'):
                raise Exception("Only HTTP CONNECT is supported")

            parts = line_str.split(' ')
            if len(parts) < 2:
                raise Exception("Invalid HTTP CONNECT request")
                
            target = parts[1]
            if ':' in target:
                host, port_str = target.split(':', 1)
                port = int(port_str)
            else:
                host = target
                port = 443

            # Read remaining headers until \r\n\r\n
            while True:
                line = await reader.readuntil(b'\r\n')
                if line == b'\r\n':
                    break

            await self._connect_and_relay(reader, writer, host, port, is_socks=False)

        except Exception as e:
            print(f"[Dispatcher] HTTP CONNECT error: {e}", file=sys.stderr)
            # Send 502 Bad Gateway
            writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _connect_and_relay(self, client_reader, client_writer, host, port, is_socks):
        adapter_ip = self._select_adapter()
        if not adapter_ip:
            raise Exception("No active adapters available")

        self._update_stat(adapter_ip, 'connections_total', 1, relative=True)
        self._update_stat(adapter_ip, 'connections_active', 1, relative=True)

        remote_reader = None
        remote_writer = None
        try:
            # Try to connect via adapter
            try:
                remote_reader, remote_writer = await asyncio.open_connection(
                    host, port, local_addr=(adapter_ip, 0)
                )
            except Exception as e:
                print(f"[Dispatcher] Connection via {adapter_ip} failed: {e}", file=sys.stderr)
                # Could attempt fallback to other adapters here if needed
                if is_socks:
                    client_writer.write(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
                    await client_writer.drain()
                else:
                    client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                    await client_writer.drain()
                return

            if is_socks:
                # Reply SOCKS5 success
                bind_addr, bind_port = remote_writer.get_extra_info('sockname')[:2]
                try:
                    bind_ip_bytes = socket.inet_aton(bind_addr)
                    reply = b'\x05\x00\x00\x01' + bind_ip_bytes + struct.pack('!H', bind_port)
                except Exception:
                    # fallback zero addr
                    reply = b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                client_writer.write(reply)
                await client_writer.drain()
            else:
                # Reply HTTP success
                client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                await client_writer.drain()

            await self._relay(client_reader, client_writer, remote_reader, remote_writer, adapter_ip)

        finally:
            self._update_stat(adapter_ip, 'connections_active', -1, relative=True)
            if remote_writer:
                remote_writer.close()
                try:
                    await remote_writer.wait_closed()
                except Exception:
                    pass
            client_writer.close()
            try:
                await client_writer.wait_closed()
            except Exception:
                pass

    async def _relay(self, r1: asyncio.StreamReader, w1: asyncio.StreamWriter, r2: asyncio.StreamReader, w2: asyncio.StreamWriter, adapter_ip: str):
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter, is_tx: bool):
            try:
                while True:
                    data = await src.read(32768)
                    if not data:
                        break
                    if is_tx:
                        self._update_stat(adapter_ip, 'bytes_tx', len(data), relative=True)
                    else:
                        self._update_stat(adapter_ip, 'bytes_rx', len(data), relative=True)
                    
                    dst.write(data)
                    await dst.drain()
            except Exception:
                pass
            finally:
                dst.close()

        task1 = asyncio.create_task(forward(r1, w2, is_tx=True))
        task2 = asyncio.create_task(forward(r2, w1, is_tx=False))
        await asyncio.gather(task1, task2, return_exceptions=True)
