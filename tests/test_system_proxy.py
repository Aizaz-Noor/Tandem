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


class TestSystemProxyWindows:
    """Test Windows proxy configuration."""

    @patch("sys.platform", "win32")
    def test_windows_enable_and_disable_with_existing_values(self):
        proxy = SystemProxyConfig()

        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 1
        mock_winreg.KEY_READ = 2
        mock_winreg.KEY_SET_VALUE = 4
        mock_winreg.REG_DWORD = 4
        mock_winreg.REG_SZ = 1

        # Original registry values
        def mock_query(key, name):
            if name == "ProxyEnable":
                return (0, 4)
            elif name == "ProxyServer":
                return ("old.proxy.com:8080", 1)
            elif name == "ProxyOverride":
                return ("old-override", 1)
            raise FileNotFoundError()

        mock_winreg.QueryValueEx.side_effect = mock_query

        mock_ctypes = MagicMock()
        mock_wininet = MagicMock()
        mock_ctypes.windll.wininet = mock_wininet
        mock_wininet.InternetSetOptionW.return_value = 1

        with patch.dict("sys.modules", {"winreg": mock_winreg, "ctypes": mock_ctypes}):
            # Enable proxy
            assert proxy.enable_proxy(host="127.0.0.1", port=9090) is True

            # Verify backup saved
            assert proxy._windows_backup_saved is True
            assert proxy._orig_proxy_enable == 0
            assert proxy._orig_proxy_server == "old.proxy.com:8080"
            assert proxy._orig_proxy_override == "old-override"

            # Verify values set in registry
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyEnable", 0, mock_winreg.REG_DWORD, 1)
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyServer", 0, mock_winreg.REG_SZ, "127.0.0.1:9090")
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyOverride", 0, mock_winreg.REG_SZ, DEFAULT_PROXY_OVERRIDE)

            # Verify WinINet notifications
            assert mock_wininet.InternetSetOptionW.call_count == 2
            mock_wininet.InternetSetOptionW.assert_any_call(0, 39, 0, 0)
            mock_wininet.InternetSetOptionW.assert_any_call(0, 37, 0, 0)

            # Disable proxy
            mock_winreg.SetValueEx.reset_mock()
            mock_wininet.InternetSetOptionW.reset_mock()

            assert proxy.disable_proxy() is True

            # Verify original values restored
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyEnable", 0, mock_winreg.REG_DWORD, 0)
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyServer", 0, mock_winreg.REG_SZ, "old.proxy.com:8080")
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyOverride", 0, mock_winreg.REG_SZ, "old-override")
            assert mock_wininet.InternetSetOptionW.call_count == 2

    @patch("sys.platform", "win32")
    def test_windows_disable_deletes_when_no_prior_values(self):
        proxy = SystemProxyConfig()

        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 1
        mock_winreg.KEY_READ = 2
        mock_winreg.KEY_SET_VALUE = 4
        mock_winreg.REG_DWORD = 4
        mock_winreg.REG_SZ = 1

        # Original values did not exist
        def mock_query(key, name):
            raise FileNotFoundError()

        mock_winreg.QueryValueEx.side_effect = mock_query

        mock_ctypes = MagicMock()
        mock_wininet = MagicMock()
        mock_ctypes.windll.wininet = mock_wininet
        mock_wininet.InternetSetOptionW.return_value = 1

        with patch.dict("sys.modules", {"winreg": mock_winreg, "ctypes": mock_ctypes}):
            assert proxy.enable_proxy("127.0.0.1", 8080) is True
            assert proxy._proxy_server_existed is False
            assert proxy._proxy_override_existed is False

            assert proxy.disable_proxy() is True

            # Should set ProxyEnable=0 and delete ProxyServer, ProxyOverride
            mock_winreg.SetValueEx.assert_called_with(mock_key, "ProxyEnable", 0, mock_winreg.REG_DWORD, 0)
            mock_winreg.DeleteValue.assert_any_call(mock_key, "ProxyServer")
            mock_winreg.DeleteValue.assert_any_call(mock_key, "ProxyOverride")

    @patch("sys.platform", "win32")
    def test_windows_is_proxy_set(self):
        proxy = SystemProxyConfig()

        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            mock_winreg.QueryValueEx.return_value = (1, 4)
            assert proxy.is_proxy_set() is True

            mock_winreg.QueryValueEx.return_value = (0, 4)
            assert proxy.is_proxy_set() is False

            mock_winreg.QueryValueEx.side_effect = FileNotFoundError()
            assert proxy.is_proxy_set() is False

    @patch("sys.platform", "win32")
    def test_windows_error_handling(self):
        proxy = SystemProxyConfig()

        mock_winreg = MagicMock()
        mock_winreg.OpenKey.side_effect = PermissionError("Access denied")

        with patch.dict("sys.modules", {"winreg": mock_winreg}):
            # Must return False, not raise
            assert proxy.enable_proxy("127.0.0.1", 8080) is False
            assert proxy.disable_proxy() is False
            assert proxy.is_proxy_set() is False

    @patch("sys.platform", "win32")
    def test_windows_localhost_proxy_not_backed_up(self):
        """Pre-existing localhost proxy must NOT be treated as user's original proxy."""
        proxy = SystemProxyConfig()

        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 1
        mock_winreg.KEY_READ = 2
        mock_winreg.KEY_SET_VALUE = 4
        mock_winreg.REG_DWORD = 4
        mock_winreg.REG_SZ = 1

        def mock_query(key, name):
            if name == "ProxyEnable":
                return (1, 4)
            elif name == "ProxyServer":
                return ("127.0.0.1:8080", 1)
            elif name == "ProxyOverride":
                return (DEFAULT_PROXY_OVERRIDE, 1)
            raise FileNotFoundError()

        mock_winreg.QueryValueEx.side_effect = mock_query

        mock_ctypes = MagicMock()
        mock_wininet = MagicMock()
        mock_ctypes.windll.wininet = mock_wininet
        mock_wininet.InternetSetOptionW.return_value = 1

        with patch.dict("sys.modules", {"winreg": mock_winreg, "ctypes": mock_ctypes}):
            assert proxy.enable_proxy("127.0.0.1", 8080) is True

            # Localhost must be discarded from backup
            assert proxy._orig_proxy_enable == 0
            assert proxy._orig_proxy_server == ""
            assert proxy._proxy_server_existed is False

            # When disabled, must delete ProxyServer and set ProxyEnable=0
            assert proxy.disable_proxy() is True
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyEnable", 0, mock_winreg.REG_DWORD, 0)
            mock_winreg.DeleteValue.assert_any_call(mock_key, "ProxyServer")

    @patch("sys.platform", "win32")
    def test_cleanup_orphaned_proxy_windows(self):
        """cleanup_orphaned_proxy resets localhost proxy and notifies WinINet."""
        mock_winreg = MagicMock()
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
        mock_winreg.HKEY_CURRENT_USER = 1
        mock_winreg.KEY_READ = 2
        mock_winreg.KEY_SET_VALUE = 4
        mock_winreg.REG_DWORD = 4
        mock_winreg.REG_SZ = 1

        def mock_query(key, name):
            if name == "ProxyEnable":
                return (1, 4)
            elif name == "ProxyServer":
                return ("127.0.0.1:8080", 1)
            raise FileNotFoundError()

        mock_winreg.QueryValueEx.side_effect = mock_query

        mock_ctypes = MagicMock()
        mock_wininet = MagicMock()
        mock_ctypes.windll.wininet = mock_wininet
        mock_wininet.InternetSetOptionW.return_value = 1

        with patch.dict("sys.modules", {"winreg": mock_winreg, "ctypes": mock_ctypes}):
            assert SystemProxyConfig.cleanup_orphaned_proxy() is True
            mock_winreg.SetValueEx.assert_any_call(mock_key, "ProxyEnable", 0, mock_winreg.REG_DWORD, 0)
            mock_winreg.DeleteValue.assert_any_call(mock_key, "ProxyServer")
            assert mock_wininet.InternetSetOptionW.call_count == 2



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
