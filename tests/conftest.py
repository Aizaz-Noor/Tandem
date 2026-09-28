"""Keep test runs isolated from user preferences and process-exit OS mutations."""
import atexit
from unittest.mock import MagicMock
import pytest

@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch, tmp_path, request):
    import turbobond.core.config as config
    monkeypatch.setattr(config, "get_default_config_path", lambda: str(tmp_path / "config.json"))
    register = atexit.register
    def isolated_register(callback, *args, **kwargs):
        if getattr(callback, "__module__", "") == "turbobond.core.system_proxy":
            return callback
        return register(callback, *args, **kwargs)
    monkeypatch.setattr(atexit, "register", isolated_register)
    if request.node.path.name == "test_ui_responsiveness.py":
        import turbobond.ui.main_window as ui
        import turbobond.ui.settings_dialog as settings
        monkeypatch.setattr(ui, "SystemProxyConfig", MagicMock())
        monkeypatch.setattr(settings, "SystemProxyConfig", MagicMock())
        monkeypatch.setattr(ui, "RouteManager", MagicMock())
        monkeypatch.setattr(ui, "optimize_windows_multilink", lambda: True)
        monkeypatch.setattr(ui, "is_elevated", lambda: False)
        monkeypatch.setattr(ui, "LocalDispatcher", MagicMock())
        monkeypatch.setattr(ui, "EngineManager", MagicMock())
