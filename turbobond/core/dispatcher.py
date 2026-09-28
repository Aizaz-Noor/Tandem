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
from urllib.parse import urlsplit
from typing import List, Dict, Optional, Tuple, Callable

class LocalDispatcher:
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 8080,
        adapter_ips: Optional[List[str]] = None,
        strategy: str = 'round_robin',
        on_stats_update: Optional[Callable] = None,
        adapter_weights: Optional[Dict[str, int]] = None
    ):
        self.host = host
        self.port = port
        self.adapter_ips = adapter_ips or []
        self.strategy = strategy
        self.on_stats_update = on_stats_update
        self.adapter_weights = adapter_weights or {}
        self._clients = set()
        self._client_writers = {}
        self._cancel_start = threading.Event()
        self._stopping = False
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

    def update_adapters(self, adapter_ips: List[str], adapter_weights=None):
        with self._lock:
            self.adapter_ips = list(adapter_ips)
            if adapter_weights is not None:
                self.adapter_weights = dict(adapter_weights)
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
            
            pool = self.adapter_ips
            if self.strategy == 'weighted':
                pool = [ip for ip in self.adapter_ips for _ in range(max(1, min(100, int(self.adapter_weights.get(ip, 1)))))]
            ip = pool[self._round_robin_index % len(pool)]
            self._round_robin_index += 1
            return ip

    async def start(self):
        self._stopping = False
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        try:
            self._server = await asyncio.start_server(
                self._handle_client, self.host, self.port
            )
            print(f"[Dispatcher] Started proxy server on {self.host}:{self.port}")
            self._started_event.set()
            if self._cancel_start.is_set():
                await self.stop()
            await self._stop_event.wait()
        except Exception as e:
            self._startup_error = e
            self._started_event.set()
            print(f"[Dispatcher] Failed to start server: {e}", file=sys.stderr)

    async def stop(self):
        self._stopping = True
        server, self._server = self._server, None
        if server:
            server.close()
        tasks = [t for t in self._clients if t is not asyncio.current_task()]
        writers = [self._client_writers.get(task) for task in tasks]
        for writer in writers:
            if writer is not None:
                writer.close()
        for task in tasks:
            task.cancel()
        if tasks:
            waiter = asyncio.gather(*tasks, return_exceptions=True)
            try:
                await asyncio.wait_for(waiter, timeout=1.0)
            except asyncio.TimeoutError:
                # A platform transport may leave a handler blocked after cancel;
                # retain the bounded shutdown and release our client references.
                pass
        self._clients.difference_update(tasks)
        for task in tasks:
            self._client_writers.pop(task, None)
        # StreamServer.wait_closed() also waits for active client callbacks.
        # They have already been cancelled and gathered above, so wait_closed
        # is unnecessary here and can hang on some asyncio implementations.
        if self._stop_event:
            self._stop_event.set()
        print("[Dispatcher] Server stopped")

    def start_in_thread(self, timeout: float = 3.0):
        if self._thread and self._thread.is_alive():
            return True

        self._cancel_start.clear()
        self._started_event.clear()
        self._startup_error = None
            
        def _run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()

        # Wait for the server socket to successfully bind or fail
        if not self._started_event.wait(timeout=timeout):
            self._cancel_start.set()
            self.stop_from_thread()
            raise TimeoutError("Timed out waiting for dispatcher proxy server to start.")
        if self._startup_error:
            raise self._startup_error
        return True

    def stop_from_thread(self):
        self._cancel_start.set()
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.stop(), self._loop)
            future.result(timeout=5)
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise TimeoutError("Dispatcher did not stop")
            self._thread = None
        return True

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self._stopping:
            writer.close()
            return
        task = asyncio.current_task()
        self._clients.add(task)
        self._client_writers[task] = writer
        try:
            # Read first byte to detect protocol
            initial_data = await asyncio.wait_for(reader.read(1), 30)
            if not initial_data:
                writer.close()
                await writer.wait_closed()
                return

            if initial_data[0] == 0x05:
                await self._handle_socks5(reader, writer, initial_data)
            else:
                # Might be HTTP CONNECT
                line = initial_data + await asyncio.wait_for(reader.readuntil(b'\r\n'), 30)
                await self._handle_http_connect(reader, writer, line)
        except Exception as e:
            print(f"[Dispatcher] Client handling error: {e}", file=sys.stderr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        finally:
            writer.close()
            self._clients.discard(task)
            self._client_writers.pop(task, None)

    async def _handle_socks5(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, initial_byte: bytes):
        try:
            # SOCKS5 greeting
            nmethods_data = await asyncio.wait_for(reader.readexactly(1), 30)
            nmethods = nmethods_data[0]
            methods = await asyncio.wait_for(reader.readexactly(nmethods), 30)
            
            if 0 not in methods:
                writer.write(b'\x05\xff')
                await writer.drain()
                return
            # Send NO AUTH (0x05, 0x00)
            writer.write(b'\x05\x00')
            await writer.drain()

            # Connect request
            req_header = await asyncio.wait_for(reader.readexactly(4), 30)
            version, cmd, rsv, atyp = req_header

            if version != 5 or rsv != 0:
                raise ValueError("Invalid SOCKS5 request")
            if cmd != 0x01: # Only CONNECT supported
                writer.write(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                raise Exception("Unsupported SOCKS5 command")

            # Parse destination
            dst_addr = ""
            if atyp == 0x01: # IPv4
                addr_data = await asyncio.wait_for(reader.readexactly(4), 30)
                dst_addr = socket.inet_ntoa(addr_data)
            elif atyp == 0x03: # Domain
                domain_len_data = await asyncio.wait_for(reader.readexactly(1), 30)
                domain_len = domain_len_data[0]
                addr_data = await asyncio.wait_for(reader.readexactly(domain_len), 30)
                dst_addr = addr_data.decode('utf-8')
            elif atyp == 0x04: # IPv6
                addr_data = await asyncio.wait_for(reader.readexactly(16), 30)
                dst_addr = socket.inet_ntop(socket.AF_INET6, addr_data)
            else:
                writer.write(b'\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00')
                await writer.drain()
                raise Exception("Unsupported SOCKS5 ATYP")

            port_data = await asyncio.wait_for(reader.readexactly(2), 30)
            dst_port = struct.unpack('!H', port_data)[0]

            await self._connect_and_relay(reader, writer, dst_addr, dst_port, is_socks=True)

        except Exception as e:
            print(f"[Dispatcher] SOCKS5 error: {e}", file=sys.stderr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_http_connect(self, reader, writer, initial_line):
        remote_writer = None
        adapter_ip = None
        try:
            method, target, version = initial_line.decode('ascii').strip().split(' ')
            if version not in ('HTTP/1.0', 'HTTP/1.1'):
                raise ValueError("Unsupported HTTP version")
            headers = []
            size = len(initial_line)
            while True:
                line = await asyncio.wait_for(reader.readuntil(b'\r\n'), 30)
                size += len(line)
                if size > 65536:
                    raise ValueError("HTTP headers too large")
                if line == b'\r\n':
                    break
                name, value = line.decode('latin1').rstrip('\r\n').split(':', 1)
                if not name or any(c not in "!#$%&'*+-.^_`|~0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in name):
                    raise ValueError("Invalid HTTP header")
                headers.append((name, value.strip()))
            if method == 'CONNECT':
                address = urlsplit('//' + target)
                if not address.hostname or address.path or address.query or address.fragment or address.username:
                    raise ValueError("Invalid CONNECT target")
                await self._connect_and_relay(reader, writer, address.hostname, address.port or 443, False)
                return
            url = urlsplit(target)
            if url.scheme != 'http' or not url.hostname or url.username or url.fragment:
                raise ValueError("Expected an absolute HTTP URL")
            lengths = [v for k, v in headers if k.lower() == 'content-length']
            transfers = [v.lower() for k, v in headers if k.lower() == 'transfer-encoding']
            if len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers):
                raise ValueError("Ambiguous request framing")
            if lengths and (not lengths[0].isascii() or not lengths[0].isdigit()):
                raise ValueError("Invalid Content-Length")
            if transfers and transfers != ['chunked']:
                raise ValueError("Unsupported transfer encoding")
            adapter_ip = self._select_adapter()
            if not adapter_ip:
                raise ValueError("No selected adapters available")
            remote_reader, remote_writer = await asyncio.wait_for(asyncio.open_connection(
                url.hostname, url.port or 80, local_addr=(adapter_ip, 0)), 15)
            self._update_stat(adapter_ip, 'connections_total', 1, True)
            self._update_stat(adapter_ip, 'connections_active', 1, True)
            connection_tokens = {v.strip().lower() for k, value in headers if k.lower() == 'connection' for v in value.split(',')}
            if connection_tokens & {'content-length', 'transfer-encoding', 'host'}:
                raise ValueError("Invalid connection header")
            drop = {'proxy-connection', 'proxy-authorization', 'connection', 'keep-alive', 'upgrade', 'host'} | connection_tokens
            clean = [(k, v) for k, v in headers if k.lower() not in drop]
            clean += [('Host', url.netloc), ('Connection', 'close')]
            path = url.path or '/'
            if url.query:
                path += '?' + url.query
            head = f"{method} {path} {version}\r\n" + ''.join(f"{k}: {v}\r\n" for k, v in clean) + '\r\n'
            remote_writer.write(head.encode('latin1'))
            await remote_writer.drain()

            async def upload():
                async def copy(count):
                    while count:
                        data = await asyncio.wait_for(reader.readexactly(min(count, 32768)), 30)
                        remote_writer.write(data)
                        await remote_writer.drain()
                        self._update_stat(adapter_ip, 'bytes_tx', len(data), True)
                        count -= len(data)
                if lengths:
                    await copy(int(lengths[0]))
                elif transfers:
                    while True:
                        line = await asyncio.wait_for(reader.readuntil(b'\r\n'), 30)
                        chunk_size = int(line.split(b';', 1)[0].strip(), 16)
                        if chunk_size < 0:
                            raise ValueError("Invalid chunk size")
                        remote_writer.write(line)
                        if chunk_size == 0:
                            # Forward bounded trailers; do not forward another request.
                            trailer_size = 0
                            while True:
                                trailer = await asyncio.wait_for(reader.readuntil(b'\r\n'), 30)
                                trailer_size += len(trailer)
                                if trailer_size > 65536:
                                    raise ValueError("Trailers too large")
                                remote_writer.write(trailer)
                                if trailer == b'\r\n':
                                    break
                            await remote_writer.drain()
                            break
                        await copy(chunk_size)
                        ending = await asyncio.wait_for(reader.readexactly(2), 30)
                        if ending != b'\r\n':
                            raise ValueError("Invalid chunk ending")
                        remote_writer.write(ending)
                        await remote_writer.drain()
            async def download():
                while True:
                    data = await asyncio.wait_for(remote_reader.read(32768), 60)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
                    self._update_stat(adapter_ip, 'bytes_rx', len(data), True)
            up, down = asyncio.create_task(upload()), asyncio.create_task(download())
            try:
                done, _ = await asyncio.wait((up, down), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
                if down not in done:
                    await down
            finally:
                for task in (up, down):
                    task.cancel()
                await asyncio.gather(up, down, return_exceptions=True)
        except Exception:
            if remote_writer is None:
                writer.write(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
                await writer.drain()
        finally:
            if remote_writer:
                self._update_stat(adapter_ip, 'connections_active', -1, True)
                remote_writer.close()
                await remote_writer.wait_closed()
            writer.close()

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
                remote_reader, remote_writer = await asyncio.wait_for(asyncio.open_connection(
                    host, port, local_addr=(adapter_ip, 0)
                ), 15)
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
                        if dst.can_write_eof():
                            dst.write_eof()
                            await dst.drain()
                        break
                    if is_tx:
                        self._update_stat(adapter_ip, 'bytes_tx', len(data), relative=True)
                    else:
                        self._update_stat(adapter_ip, 'bytes_rx', len(data), relative=True)
                    
                    dst.write(data)
                    await dst.drain()
            except Exception:
                dst.close()

        task1 = asyncio.create_task(forward(r1, w2, is_tx=True))
        task2 = asyncio.create_task(forward(r2, w1, is_tx=False))
        await asyncio.gather(task1, task2, return_exceptions=True)
