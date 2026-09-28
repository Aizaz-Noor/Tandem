import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from turbobond.core.route_manager import RouteManager

@pytest.fixture(autouse=True, params=["Windows", "Linux"])
def operating_system(request):
    with patch("turbobond.core.route_manager.platform.system", return_value=request.param):
        yield


@patch("turbobond.core.route_manager.subprocess.run")
def test_get_adapter_gateways(mock_run):
    rm = RouteManager()
    
    if rm.os_type == 'windows':
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_data = [
            {"InterfaceAlias": "Wi-Fi", "Gateway": "192.168.1.1", "InterfaceIndex": 10},
            {"InterfaceAlias": "Ethernet", "Gateway": "10.0.0.1", "InterfaceIndex": 12}
        ]
        mock_result.stdout = json.dumps(mock_data)
        mock_run.return_value = mock_result
        
        gateways = rm.get_adapter_gateways()
        
        assert "Wi-Fi" in gateways
        assert gateways["Wi-Fi"] == "192.168.1.1"
        assert "Ethernet" in gateways
        assert gateways["Ethernet"] == "10.0.0.1"
        
    elif rm.os_type == 'linux':
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "default via 192.168.1.1 dev wlan0 proto dhcp metric 600\ndefault via 10.0.0.1 dev eth0 proto dhcp metric 100"
        mock_run.return_value = mock_result
        
        gateways = rm.get_adapter_gateways()
        
        assert "wlan0" in gateways
        assert gateways["wlan0"] == "192.168.1.1"
        assert "eth0" in gateways
        assert gateways["eth0"] == "10.0.0.1"


@patch("turbobond.core.route_manager.RouteManager.is_admin")
def test_setup_routes_not_admin(mock_is_admin):
    mock_is_admin.return_value = False
    
    rm = RouteManager()
    adapters = [{"name": "Wi-Fi", "ip": "192.168.1.5"}]
    
    # Should return False immediately when not admin
    assert rm.setup_routes(adapters) is False


@patch("turbobond.core.route_manager.RouteManager.is_admin")
@patch("turbobond.core.route_manager.subprocess.run")
def test_cleanup_routes_clears_state(mock_run, mock_is_admin):
    mock_is_admin.return_value = True
    
    rm = RouteManager()
    
    # Inject fake state to verify it gets cleared
    rm.added_routes = [{'alias': 'Wi-Fi', 'gateway': '192.168.1.1', 'prefix': '0.0.0.0/0'}]
    rm.modified_metrics = {'Wi-Fi': 50}
    rm.linux_tables = {'wlan0': {'table': 100, 'ip': '192.168.1.5', 'gateway': '192.168.1.1'}}
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    result = rm.cleanup_routes()
    
    assert result is True
    
    # Verify states were cleared based on OS
    if rm.os_type == 'windows':
        assert len(rm.added_routes) == 0
        assert len(rm.modified_metrics) == 0
    elif rm.os_type == 'linux':
        assert len(rm.linux_tables) == 0
