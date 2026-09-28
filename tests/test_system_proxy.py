"""
Tests for SystemProxyConfig (Windows & Linux).
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, call
import pytest

from turbobond.core.system_proxy import (
    SystemProxyConfig,
    WINDOWS_INTERNET_SETTINGS_KEY,
    DEFAULT_PROXY_OVERRIDE,
    GNOME_PROXY_SCHEMA,
    GNOME_HTTP_SCHEMA,
    GNOME_HTTPS_SCHEMA
)


@pytest.fixture
def registry(monkeypatch):
    import json
    from turbobond.core.system_proxy import BACKUP_VALUE
    values = {"ProxyEnable": (1, 4), "ProxyServer": ("127.0.0.1:9999", 1), "ProxyOverride": ("<local>", 1)}
    reg = MagicMock()
    reg.HKEY_CURRENT_USER = 1
    reg.KEY_READ, reg.KEY_SET_VALUE = 2, 4
    reg.REG_DWORD, reg.REG_SZ = 4, 1
    def query(key, name):
        if name not in values:
            raise FileNotFoundError(name)
        return values[name]
    def set_value(key, name, reserved, kind, value):
        values[name] = (value, kind)
    def delete_value(key, name):
        if name not in values:
            raise FileNotFoundError(name)
        del values[name]
    reg.QueryValueEx.side_effect = query
    reg.SetValueEx.side_effect = set_value
    reg.DeleteValue.side_effect = delete_value
    monkeypatch.setitem(sys.modules, "winreg", reg)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(SystemProxyConfig, "_notify_windows", lambda self: True)
    return values, reg


def test_windows_preserves_third_party_local_proxy(registry):
    values, reg = registry
    before = values.copy()
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy("127.0.0.1", 8080)
    assert values["ProxyServer"][0] == "127.0.0.1:8080"
    assert proxy.disable_proxy()
    assert values == before
    assert proxy.disable_proxy()
    assert values == before


def test_windows_absent_values_restored(registry):
    values, reg = registry
    values.clear()
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy()
    assert proxy.disable_proxy()
    assert values == {}


def test_windows_cleanup_leaves_unowned_proxy_alone(registry):
    values, reg = registry
    before = values.copy()
    assert SystemProxyConfig.cleanup_orphaned_proxy()
    assert values == before
    assert SystemProxyConfig().disable_proxy()
    assert values == before


def test_windows_recovers_dead_owner(registry, monkeypatch):
    values, reg = registry
    before = values.copy()
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy()
    monkeypatch.setattr("turbobond.core.system_proxy._pid_alive", lambda pid: False)
    assert SystemProxyConfig.cleanup_orphaned_proxy()
    assert values == before


def test_windows_leaves_live_owner_alone(registry):
    values, reg = registry
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy()
    before = values.copy()
    assert SystemProxyConfig.cleanup_orphaned_proxy()
    assert values == before
    assert proxy.disable_proxy()


def test_windows_clean_current_restores_live_owner(registry):
    values, reg = registry
    before = values.copy()
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy()
    assert values != before
    assert SystemProxyConfig.cleanup_orphaned_proxy(clean_current=True)
    assert values == before



def test_windows_external_change_is_preserved(registry):
    values, reg = registry
    proxy = SystemProxyConfig()
    assert proxy.enable_proxy()
    values["ProxyServer"] = ("corporate.proxy:80", 1)
    assert proxy.disable_proxy()
    assert values["ProxyServer"] == ("corporate.proxy:80", 1)


def test_windows_read_failure_does_not_mutate(registry):
    values, reg = registry
    before = values.copy()
    reg.QueryValueEx.side_effect = PermissionError("denied")
    assert not SystemProxyConfig().enable_proxy()
    assert values == before


def test_windows_force_reset(registry):
    values, reg = registry
    assert SystemProxyConfig.cleanup_orphaned_proxy(force=True)
    assert values == {"ProxyEnable": (0, 4)}


class TestSystemProxyLinux:
    """Test Linux proxy configuration (GNOME and fallback)."""

    @patch("sys.platform", "linux")
    def test_linux_gnome_success(self):
        proxy = SystemProxyConfig()

        with patch("shutil.which", return_value="/usr/bin/gsettings"), \
             patch("subprocess.run") as mock_run:
            # Mock gsettings get org.gnome.system.proxy mode -> 'none'
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "'none'\n"

            assert proxy.enable_proxy("127.0.0.1", 8080) is True
            assert proxy._gnome_configured is True
            assert proxy._orig_gnome_mode == "none"

            # Check that gsettings set commands were called
            assert mock_run.call_count >= 6

            # Disable proxy
            mock_run.reset_mock()
            mock_run.return_value.returncode = 0

            assert proxy.disable_proxy() is True
            mock_run.assert_any_call(
                ["gsettings", "set", GNOME_PROXY_SCHEMA, "mode", "none"],
                capture_output=True,
                text=True,
                timeout=5
            )

    @patch("sys.platform", "linux")
    def test_linux_fallback_when_gsettings_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, "proxy_env")
            proxy = SystemProxyConfig(proxy_env_path=env_file)

            with patch("shutil.which", return_value=None):
                assert proxy.enable_proxy("127.0.0.1", 8080) is True
                assert proxy._fallback_configured is True
                assert os.path.exists(env_file)

                # Check file contents
                with open(env_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "http_proxy=http://127.0.0.1:8080" in content
                    assert "https_proxy=http://127.0.0.1:8080" in content

                # Check is_proxy_set
                assert proxy.is_proxy_set() is True

                # Disable proxy
                assert proxy.disable_proxy() is True
                assert not os.path.exists(env_file)
                assert proxy.is_proxy_set() is False

    @patch("sys.platform", "linux")
    def test_linux_fallback_when_gsettings_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, "proxy_env")
            proxy = SystemProxyConfig(proxy_env_path=env_file)

            with patch("shutil.which", return_value="/usr/bin/gsettings"), \
                 patch("subprocess.run") as mock_run:
                # gsettings fails with non-zero returncode
                mock_run.return_value.returncode = 1
                mock_run.return_value.stderr = "dconf-WARNING: failed to commit changes"

                assert proxy.enable_proxy("127.0.0.1", 8080) is True
                assert proxy._fallback_configured is True
                assert os.path.exists(env_file)

                assert proxy.disable_proxy() is True
                assert not os.path.exists(env_file)


class TestSystemProxyGeneral:
    """Test general SystemProxyConfig features."""

    def test_context_manager(self):
        proxy = SystemProxyConfig()
        with patch.object(proxy, "disable_proxy") as mock_disable:
            with proxy:
                pass
            mock_disable.assert_called_once()

    @patch("sys.platform", "darwin")
    def test_unsupported_platform(self):
        proxy = SystemProxyConfig()
        assert proxy.enable_proxy() is False
        assert proxy.disable_proxy() is False
        assert proxy.is_proxy_set() is False
