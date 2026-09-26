import os
import tempfile
import pytest
from turbobond.core.config import ConfigManager


def test_config_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        cfg = ConfigManager(filepath=cfg_path)
        
        # Test defaults
        assert cfg.get("server_host") == "150.136.212.160"
        assert cfg.get("server_port") == 443
        
        # Test update
        cfg.set("server_host", "1.2.3.4")
        assert cfg.get("server_host") == "1.2.3.4"
        
        # Reload from disk
        cfg2 = ConfigManager(filepath=cfg_path)
        assert cfg2.get("server_host") == "1.2.3.4"


def test_export_import_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        profile_path = os.path.join(tmpdir, "roommate.turbobond")
        
        cfg = ConfigManager(filepath=cfg_path)
        cfg.set("server_host", "vpn.example.com")
        cfg.set("auth_key", "secret-test-key-12345")
        
        assert cfg.export_profile(profile_path) is True
        assert os.path.exists(profile_path)
        
        # Import into another config instance
        cfg_other_path = os.path.join(tmpdir, "other_config.json")
        cfg_other = ConfigManager(filepath=cfg_other_path)
        assert cfg_other.import_profile(profile_path) is True
        assert cfg_other.get("server_host") == "vpn.example.com"
        assert cfg_other.get("auth_key") == "secret-test-key-12345"
