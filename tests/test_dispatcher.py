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
