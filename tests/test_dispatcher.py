import asyncio
import socket
import struct
import threading
import time
from typing import Optional

import pytest

from turbobond.core.dispatcher import LocalDispatcher


def test_select_adapter_round_robin():
    dispatcher = LocalDispatcher(adapter_ips=['192.168.1.2', '10.0.0.2', '172.16.0.2'])
    
    assert dispatcher._select_adapter() == '192.168.1.2'
    assert dispatcher._select_adapter() == '10.0.0.2'
    assert dispatcher._select_adapter() == '172.16.0.2'
    assert dispatcher._select_adapter() == '192.168.1.2'


def test_select_adapter_empty():
    dispatcher = LocalDispatcher(adapter_ips=[])
    assert dispatcher._select_adapter() is None


def test_update_adapters():
    dispatcher = LocalDispatcher(adapter_ips=['1.1.1.1', '2.2.2.2'])
    
    assert dispatcher._select_adapter() == '1.1.1.1'
    
    dispatcher.update_adapters(['3.3.3.3', '4.4.4.4'])
    
    # Index should be reset to 0
    assert dispatcher._select_adapter() == '3.3.3.3'
    assert dispatcher._select_adapter() == '4.4.4.4'


def test_get_stats_empty():
    dispatcher = LocalDispatcher(adapter_ips=['1.1.1.1'])
    stats = dispatcher.get_stats()
    
    assert '1.1.1.1' in stats['adapters']
    adapter_stats = stats['adapters']['1.1.1.1']
    assert adapter_stats['connections_total'] == 0
    assert adapter_stats['connections_active'] == 0
    assert adapter_stats['bytes_rx'] == 0
    assert adapter_stats['bytes_tx'] == 0
    
    total_stats = stats['total']
    assert total_stats['connections_total'] == 0
    assert total_stats['connections_active'] == 0
    assert total_stats['bytes_rx'] == 0
    assert total_stats['bytes_tx'] == 0


def test_get_stats_tracking():
    dispatcher = LocalDispatcher(adapter_ips=['1.1.1.1'])
    
    dispatcher._update_stat('1.1.1.1', 'connections_total', 5, relative=True)
    dispatcher._update_stat('1.1.1.1', 'connections_active', 2, relative=True)
    dispatcher._update_stat('1.1.1.1', 'bytes_rx', 1024, relative=True)
    dispatcher._update_stat('1.1.1.1', 'bytes_tx', 512, relative=True)
    
    stats = dispatcher.get_stats()
    
    adapter_stats = stats['adapters']['1.1.1.1']
    assert adapter_stats['connections_total'] == 5
    assert adapter_stats['connections_active'] == 2
    assert adapter_stats['bytes_rx'] == 1024
    assert adapter_stats['bytes_tx'] == 512
    
    total_stats = stats['total']
    assert total_stats['connections_total'] == 5
    assert total_stats['connections_active'] == 2
    assert total_stats['bytes_rx'] == 1024
    assert total_stats['bytes_tx'] == 512


def test_socks5_handshake(free_tcp_port):
    async def run_test():
        dispatcher = LocalDispatcher(host='127.0.0.1', port=free_tcp_port, adapter_ips=['127.0.0.1'])
        
        # Start dispatcher in the background task
        task = asyncio.create_task(dispatcher.start())
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', free_tcp_port)
            
            # SOCKS5 greeting
            writer.write(b'\x05\x01\x00') # version 5, 1 method, method 0 (NO AUTH)
            await writer.drain()
            
            response = await reader.readexactly(2)
            assert response == b'\x05\x00' # NO AUTH selected
            
            writer.close()
            await writer.wait_closed()
            
        finally:
            await dispatcher.stop()
            await task
    asyncio.run(run_test())


def test_http_connect(free_tcp_port):
    async def run_test():
        dispatcher = LocalDispatcher(host='127.0.0.1', port=free_tcp_port, adapter_ips=['127.0.0.1'])
        
        task = asyncio.create_task(dispatcher.start())
        await asyncio.sleep(0.1)
        
        # Simple echo server to act as a target
        target_server = await asyncio.start_server(
            lambda r, w: None, '127.0.0.1', 0
        )
        target_port = target_server.sockets[0].getsockname()[1]
        
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', free_tcp_port)
            
            writer.write(f'CONNECT 127.0.0.1:{target_port} HTTP/1.1\r\nHost: 127.0.0.1:{target_port}\r\n\r\n'.encode('utf-8'))
            await writer.drain()
            
            response = await reader.readuntil(b'\r\n\r\n')
            assert b'200 Connection Established' in response
            
            writer.close()
            await writer.wait_closed()
            
        finally:
            target_server.close()
            await target_server.wait_closed()
            await dispatcher.stop()
            await task
    asyncio.run(run_test())


def test_start_stop_thread(free_tcp_port):
    dispatcher = LocalDispatcher(host='127.0.0.1', port=free_tcp_port, adapter_ips=['127.0.0.1'])
    
    dispatcher.start_in_thread()
    time.sleep(0.2)
    
    assert dispatcher._thread is not None
    assert dispatcher._thread.is_alive()
    
    dispatcher.stop_from_thread()
    
    assert dispatcher._thread is None


def test_weighted_distribution():
    d = LocalDispatcher(adapter_ips=["a", "b"], strategy="weighted", adapter_weights={"a": 3, "b": 1})
    selected = [d._select_adapter() for _ in range(40)]
    assert selected.count("a") == 30
    assert selected.count("b") == 10


def test_plain_http_body_and_headers():
    async def run():
        received = []
        async def origin(reader, writer):
            try:
                head = await reader.readuntil(b"\r\n\r\n")
                body = await reader.readexactly(4)
                received.append((head, body))
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK")
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
        target = await asyncio.start_server(origin, "127.0.0.1", 0)
        port = target.sockets[0].getsockname()[1]
        d = LocalDispatcher(port=0, adapter_ips=["127.0.0.1"])
        task = asyncio.create_task(d.start())
        await asyncio.to_thread(d._started_event.wait, 3)
        proxy_port = d._server.sockets[0].getsockname()[1]
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
            writer.write(f"POST http://127.0.0.1:{port}/upload?q=1 HTTP/1.1\r\nHost: wrong\r\nProxy-Authorization: secret\r\nContent-Length: 4\r\n\r\ndata".encode())
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), 3)
            assert response.endswith(b"OK")
            assert received[0][0].startswith(b"POST /upload?q=1 HTTP/1.1")
            assert b"Proxy-Authorization" not in received[0][0]
            assert f"Host: 127.0.0.1:{port}".encode() in received[0][0]
            assert received[0][1] == b"data"
            writer.close()
            await writer.wait_closed()
        finally:
            await d.stop()
            await task
            target.close()
            await target.wait_closed()
    asyncio.run(run())


def test_stop_cancels_idle_clients():
    async def run():
        d = LocalDispatcher(port=0, adapter_ips=["127.0.0.1"])
        task = asyncio.create_task(d.start())
        await asyncio.to_thread(d._started_event.wait, 3)
        reader, writer = await asyncio.open_connection("127.0.0.1", d._server.sockets[0].getsockname()[1])
        await asyncio.sleep(0)
        await asyncio.wait_for(d.stop(), 3)
        await task
        assert not d._clients
        assert not d._client_writers
        writer.close()
        await writer.wait_closed()
    asyncio.run(run())


def test_socks_rejects_unoffered_auth():
    async def run():
        d = LocalDispatcher(port=0, adapter_ips=["127.0.0.1"])
        task = asyncio.create_task(d.start())
        await asyncio.to_thread(d._started_event.wait, 3)
        reader, writer = await asyncio.open_connection("127.0.0.1", d._server.sockets[0].getsockname()[1])
        writer.write(b"\x05\x01\x02")
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(2), 1) == b"\x05\xff"
        writer.close()
        await writer.wait_closed()
        await d.stop()
        await task
    asyncio.run(run())


def test_connect_preserves_response_after_client_half_close():
    async def run():
        async def origin(reader, writer):
            data = await reader.read()
            writer.write(b"reply:" + data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        target = await asyncio.start_server(origin, "127.0.0.1", 0)
        d = LocalDispatcher(port=0, adapter_ips=["127.0.0.1"])
        task = asyncio.create_task(d.start())
        await asyncio.to_thread(d._started_event.wait, 3)
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", d._server.sockets[0].getsockname()[1])
            writer.write(f"CONNECT 127.0.0.1:{target.sockets[0].getsockname()[1]} HTTP/1.1\r\n\r\n".encode())
            await writer.drain()
            assert b"200" in await reader.readuntil(b"\r\n\r\n")
            writer.write(b"payload")
            writer.write_eof()
            assert await asyncio.wait_for(reader.read(), 3) == b"reply:payload"
            writer.close()
            await writer.wait_closed()
        finally:
            await d.stop()
            await task
            target.close()
            await target.wait_closed()
    asyncio.run(run())
