import sys
import platform
import subprocess
import json
import os
from typing import List, Dict, Optional, Any

class RouteManager:
    """
    Manages per-adapter routing tables so that socket.bind() actually routes
    traffic through the correct network interface.
    """
    
    def __init__(self):
        self.os_type = platform.system().lower()
        self.added_routes = []
        self.modified_metrics = {}
        self.linux_tables = {}

    def log_error(self, msg: str):
        print(f"[RouteManager] ERROR: {msg}", file=sys.stderr)

    def log_info(self, msg: str):
        print(f"[RouteManager] INFO: {msg}", file=sys.stderr)
        
    def log_warning(self, msg: str):
        print(f"[RouteManager] WARNING: {msg}", file=sys.stderr)

    def is_admin(self) -> bool:
        if self.os_type == 'windows':
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except Exception:
                return False
        else:
            return os.geteuid() == 0

    def get_adapter_gateways(self) -> Dict[str, str]:
        """
        Discover the gateway for each adapter.
        """
        gateways = {}
        try:
            if self.os_type == 'windows':
                # Query default gateways using PowerShell
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object InterfaceAlias, @{N='Gateway';E={$_.IPv4DefaultGateway.NextHop}}, @{N='InterfaceIndex';E={$_.InterfaceIndex}} | ConvertTo-Json -Compress"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    data = json.loads(result.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        alias = item.get("InterfaceAlias")
                        gw = item.get("Gateway")
                        if alias and gw:
                            gateways[alias] = gw
            elif self.os_type == 'linux':
                result = subprocess.run(["ip", "-4", "route", "show"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if line.startswith("default"):
                            parts = line.split()
                            if "via" in parts and "dev" in parts:
                                gw = parts[parts.index("via") + 1]
                                dev = parts[parts.index("dev") + 1]
                                # Only record the first default route per device
                                if dev not in gateways:
                                    gateways[dev] = gw
        except Exception as e:
            self.log_error(f"Failed to get gateways: {e}")
            
        return gateways

    def _get_original_metric_win(self, alias: str) -> Optional[int]:
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetIPInterface -InterfaceAlias '{alias.replace(chr(39), chr(39) * 2)}' -AddressFamily IPv4).InterfaceMetric"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                metric_str = res.stdout.strip()
                if metric_str.isdigit():
                    return int(metric_str)
        except Exception as e:
            self.log_error(f"Failed to get original metric for {alias}: {e}")
        return None

    def setup_routes(self, adapters: List[Dict]) -> bool:
        """
        Set up per-adapter routing to ensure bound sockets exit through the correct interface.
        """
        if not self.is_admin():
            self.log_warning("Administrator privileges required for setup_routes. Returning False.")
            return False

        gateways = self.get_adapter_gateways()
        success = True

        if self.os_type == 'windows':
            for adapter in adapters:
                name = adapter.get('name')
                if not name:
                    continue
                gw = gateways.get(name)
                if not gw:
                    self.log_warning(f"No gateway found for {name}, skipping route setup.")
                    continue
                
                # Store original metric before changing
                orig_metric = self._get_original_metric_win(name)
                if orig_metric is not None:
                    self.modified_metrics[name] = orig_metric
                
                # Set metric very low so bound sockets prefer it
                try:
                    subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-NetIPInterface -InterfaceAlias '{name.replace(chr(39), chr(39) * 2)}' -InterfaceMetric 10"], check=True, timeout=10, capture_output=True)
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to set interface metric for {name}: {e.stderr}")
                    success = False
                    continue
                
                # Add specific source-based route
                try:
                    cmd = f"New-NetRoute -DestinationPrefix '0.0.0.0/0' -InterfaceAlias '{name.replace(chr(39), chr(39) * 2)}' -NextHop '{gw}' -RouteMetric 10 -PolicyStore ActiveStore"
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, timeout=10, capture_output=True)
                    self.added_routes.append({'alias': name, 'gateway': gw, 'prefix': '0.0.0.0/0'})
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to add route for {name}: {e.stderr}")
                    success = False

        elif self.os_type == 'linux':
            table_id = 100
            for adapter in adapters:
                name = adapter.get('name')
                ip_addr = adapter.get('ip')
                if not name or not ip_addr:
                    continue
                gw = gateways.get(name)
                if not gw:
                    self.log_warning(f"No gateway found for {name}, skipping route setup.")
                    continue
                
                # Add policy routing rules and route table
                try:
                    subprocess.run(["ip", "rule", "add", "from", ip_addr, "table", str(table_id)], check=True, timeout=10, capture_output=True)
                    subprocess.run(["ip", "route", "add", "default", "via", gw, "dev", name, "table", str(table_id)], check=True, timeout=10, capture_output=True)
                    self.linux_tables[name] = {'table': table_id, 'ip': ip_addr, 'gateway': gw}
                    table_id += 1
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to setup linux routing for {name}: {e.stderr}")
                    success = False
        else:
            self.log_error(f"Unsupported OS: {self.os_type}")
            return False

        return success

    def cleanup_routes(self) -> bool:
        """
        Remove all routes added by TurboBond and restore original metrics.
        """
        if not self.is_admin():
            self.log_warning("Administrator privileges required for cleanup_routes. Returning False.")
            return False
            
        success = True
        
        if self.os_type == 'windows':
            # Remove added routes
            for route in self.added_routes:
                alias = route['alias']
                gw = route['gateway']
                prefix = route['prefix']
                try:
                    cmd = f"Remove-NetRoute -DestinationPrefix '{prefix}' -InterfaceAlias '{alias.replace(chr(39), chr(39) * 2)}' -NextHop '{gw}' -PolicyStore ActiveStore -Confirm:$false"
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, timeout=10, capture_output=True)
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to remove route for {alias}: {e.stderr}")
                    success = False

            # Restore original metrics
            for alias, metric in self.modified_metrics.items():
                try:
                    cmd = f"Set-NetIPInterface -InterfaceAlias '{alias.replace(chr(39), chr(39) * 2)}' -InterfaceMetric {metric}"
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, timeout=10, capture_output=True)
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to restore metric for {alias}: {e.stderr}")
                    success = False
                    
            self.added_routes.clear()
            self.modified_metrics.clear()

        elif self.os_type == 'linux':
            for name, info in self.linux_tables.items():
                ip_addr = info['ip']
                table = info['table']
                try:
                    subprocess.run(["ip", "rule", "del", "from", ip_addr, "table", str(table)], check=True, timeout=10, capture_output=True)
                    subprocess.run(["ip", "route", "flush", "table", str(table)], check=True, timeout=10, capture_output=True)
                except subprocess.CalledProcessError as e:
                    self.log_warning(f"Failed to cleanup linux routing for {name}: {e.stderr}")
                    success = False
                    
            self.linux_tables.clear()
            
        return success
