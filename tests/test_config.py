import os
import tempfile
import pytest
from turbobond.core.config import ConfigManager


def test_config_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "config.json")
        cfg = ConfigManager(filepath=cfg_path)
        
        # Test defaults
        assert cfg.get("server_host") == ""
        assert cfg.get("insecure") is False
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


def test_import_is_transactional(tmp_path):
    import json
    cfg = ConfigManager(str(tmp_path / "config.json"))
    cfg.set("server_host", "old.example")
    before = (tmp_path / "config.json").read_bytes()
    profile = tmp_path / "invalid.turbobond"
    profile.write_text(json.dumps({"server_host": "new.example", "server_port": "invalid"}))
    assert not cfg.import_profile(str(profile))
    assert cfg.get("server_host") == "old.example"
    assert (tmp_path / "config.json").read_bytes() == before


@pytest.mark.parametrize("patch", [{"proxy_port": 0}, {"server_port": True}, {"mode": "bad"}, {"adapter_weights": {"Wi-Fi": -1}}, {"dns": [1]}, {"kill_switch": True}])
def test_invalid_patch_rejected(tmp_path, patch):
    cfg = ConfigManager(str(tmp_path / "config.json"))
    with pytest.raises(ValueError):
        cfg.update(patch)
    assert not (tmp_path / "config.json").exists()


def test_write_failure_preserves_disk_and_memory(tmp_path, monkeypatch):
    cfg = ConfigManager(str(tmp_path / "config.json"))
    cfg.set("server_host", "old.example")
    before = cfg.data.copy()
    def fail(*args):
        raise PermissionError("disk denied")
    monkeypatch.setattr("turbobond.core.config.os.replace", fail)
    with pytest.raises(PermissionError):
        cfg.update({"server_host": "new.example"})
    assert cfg.data == before
    assert ConfigManager(cfg.filepath).data == before
    assert not list(tmp_path.glob(".tandem-*"))


def test_defaults_are_independent(tmp_path):
    a = ConfigManager(str(tmp_path / "a.json"))
    b = ConfigManager(str(tmp_path / "b.json"))
    a.data["adapter_weights"]["Wi-Fi"] = 9
    assert b.get("adapter_weights") == {}
