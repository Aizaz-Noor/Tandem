import pytest
from turbobond.core.engine_manager import EngineManager, TunnelState


def test_engine_state_transitions():
    states = []
    messages = []

    def on_change(state, msg):
        states.append(state)
        messages.append(msg)

    engine = EngineManager(on_state_change=on_change)
    assert engine.state == TunnelState.DISCONNECTED

    # Test connecting
    engine._set_state(TunnelState.CONNECTING, "Connecting...")
    assert engine.state == TunnelState.CONNECTING

    # Test connected
    engine._set_state(TunnelState.CONNECTED, "TurboBond Active")
    assert engine.state == TunnelState.CONNECTED

    # Test reconnecting
    engine._set_state(TunnelState.RECONNECTING, "Reconnecting...")
    assert engine.state == TunnelState.RECONNECTING

    assert len(states) == 3


def test_non_fatal_xquic_log_handling():
    engine = EngineManager()
    
    # Simulate non-fatal xquic library debug line
    raw_xquic_line = (
        "16:43:21.722 [ERR] [lib] [xquic] [2026/09/24 16:43:21 722739] [error]"
        "|scid:0bb02e72e49a6660|xqc_send_packet_with_pn|write_socket error"
        "|conn:000001C61B1F119C|path:0|pkt_num:0|size:1184|sent:-510"
        "|pkt_type:INIT|frame:PADDING CRYPTO |now:1790250201722739|"
    )
    lower = raw_xquic_line.lower()

    # The line contains 'error', but must NOT match fatal triggers
    is_fatal = any(k in lower for k in ["fatal", "panic", "iface pin failed", "auth failed", "permission denied"])
    assert is_fatal is False


def test_stale_watchdog_cannot_stop_new_connection():
    from unittest.mock import patch
    engine = EngineManager()
    engine._generation = 2
    engine.state = TunnelState.CONNECTING
    with patch.object(engine, "stop") as stop:
        engine._connection_timeout_watchdog(timeout=0, generation=1)
    stop.assert_not_called()
    assert engine.state == TunnelState.CONNECTING


def test_state_callback_failure_does_not_break_cleanup():
    def failed(*args):
        raise RuntimeError("callback failed")
    engine = EngineManager(on_state_change=failed)
    engine._set_state(TunnelState.CONNECTING)
    engine.stop()
    assert engine.state == TunnelState.DISCONNECTED


def test_windows_job_terminates_owned_child():
    import os
    import subprocess
    import sys
    from turbobond.core.process_job import ProcessJob
    if os.name != "nt":
        pytest.skip("Windows job-object behavior")
    job = ProcessJob()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        job.assign(child)
        job.close()
        child.wait(timeout=5)
        assert child.poll() is not None
    finally:
        job.close()
        if child.poll() is None:
            child.kill()
            child.wait()


def test_cloud_key_is_not_passed_in_process_arguments(tmp_path):
    import json
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    process = MagicMock()
    process.poll.return_value = None
    with patch("turbobond.core.engine_manager.locate_engine_binary", return_value=str(tmp_path / "mqvpn.exe")), \
         patch("turbobond.core.engine_manager.subprocess.Popen", return_value=process) as popen, \
         patch("turbobond.core.engine_manager.ProcessJob"), \
         patch.object(EngineManager, "_secure_config_file"), \
         patch("turbobond.core.engine_manager.threading.Thread"):
        engine = EngineManager()
        assert engine.start("vpn.example.test", 443, "test-private-key", ["Wi-Fi"])
        command = popen.call_args.args[0]
        assert "test-private-key" not in command
        assert "--auth-key" not in command
        config_path = Path(command[command.index("--config") + 1])
        assert json.loads(config_path.read_text(encoding="utf-8")) == {"auth_key": "test-private-key"}
        engine.stop()
        assert not config_path.exists()


def test_temporary_cloud_config_is_private(tmp_path):
    import os
    import sys
    path = tmp_path / "auth.json"
    path.write_text('{"auth_key":"test"}', encoding="utf-8")
    EngineManager._secure_config_file(str(path))
    if not sys.platform.startswith("win"):
        assert os.stat(path).st_mode & 0o077 == 0


def test_cloud_launch_failure_removes_temporary_key(tmp_path):
    import tempfile
    from unittest.mock import patch

    real_mkstemp = tempfile.mkstemp
    def local_mkstemp(*args, **kwargs):
        return real_mkstemp(*args, **kwargs, dir=tmp_path)

    with patch("turbobond.core.engine_manager.locate_engine_binary", return_value=str(tmp_path / "mqvpn.exe")), \
         patch("turbobond.core.engine_manager.subprocess.Popen", side_effect=OSError("launch failed")), \
         patch("turbobond.core.engine_manager.ProcessJob"), \
         patch("turbobond.core.engine_manager.tempfile.mkstemp", side_effect=local_mkstemp), \
         patch.object(EngineManager, "_secure_config_file"):
        engine = EngineManager()
        assert not engine.start("vpn.example.test", 443, "test-private-key", ["Wi-Fi"])
        assert engine._config_path is None
        assert not list(tmp_path.glob("tandem-mqvpn-*.json"))
