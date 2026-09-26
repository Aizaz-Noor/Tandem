# Tandem: Multi-Link Internet Aggregator

Tandem combines multiple active network connections on a single computer into a unified, high-throughput network pipeline. It supports built-in Wi-Fi, Ethernet, USB Wi-Fi dongles, and smartphone USB tethering to increase bandwidth and provide link failover.

## Key Features

- Dual aggregation modes: Local Socket Dispatcher (zero-cloud) and Cloud Packet Bonding.
- Automatic adapter detection: Identifies physical adapters, IP addresses, interface types, and gateway metrics while filtering out virtual adapters.
- Local Dispatcher proxy: High-throughput local SOCKS5 and HTTP proxy (127.0.0.1:8080) that distributes outgoing TCP sockets across multiple local network interfaces using round-robin scheduling.
- Cloud Bonding engine: Multipath QUIC and MASQUE (RFC 9484) encapsulation over a Wintun virtual network adapter for single-IP traffic reassembly via an external gateway.
- Dynamic interface hot-toggling: Enable or disable individual network links in real time without restarting active downloads.
- Real-time telemetry: Live bandwidth tracking for aggregate and per-adapter download and upload rates.
- Desktop user interface: Apple-inspired light theme built with CustomTkinter, featuring WCAG AAA contrast and high-resolution vector icons.
- One-click profile sharing: Export and import network profiles using encrypted `.turbobond` profile files.

## Bonding Modes

Tandem provides two distinct operating modes depending on your infrastructure and use case:

### 1. Local Dispatcher Mode (No Server Required)

Local Dispatcher mode operates entirely on your local machine without requiring a remote server, VPS, or cloud subscription.

- How it works: Tandem runs a lightweight, multithreaded proxy server on `127.0.0.1:8080` (supporting both SOCKS5 and HTTP CONNECT protocols). When applications open parallel connections (such as multi-segment file downloads, web browsers, torrent clients, Steam, or web scrapers), the dispatcher binds each outgoing socket to a different physical network interface using its local IP address (`bind()` on Windows, `SO_BINDTODEVICE` on Linux).
- Benefits: Zero external server latency, zero cloud costs, direct hardware throughput, and no server bandwidth limits.
- Best for: Multi-connection file downloads, web browsing, streaming platforms with parallel segment fetching, package managers, and game downloads.

### 2. Cloud Bonding Mode (Single Public IP)

Cloud Bonding mode bonds all network interfaces at the packet level through a remote cloud reassembly gateway.

- How it works: Tandem instantiates a Wintun virtual network adapter on Windows (or a TUN interface on Linux). Outgoing IP packets are captured by the virtual adapter, split into Multipath QUIC datagrams across all connected network links, transmitted over UDP port 443 to a remote Tandem server, and reassembled with NAT masquerade before exiting to the public internet through a single IP address.
- Benefits: True packet-level bonding where all traffic exits from a single static public IP. Works for single-stream connections, multiplayer gaming, VPNs, and services with strict IP persistence checks.
- Best for: Real-time gaming, single-stream TCP transfers, VoIP, and banking or work services that restrict changing IP addresses.

## Tech Stack

| Component | Technology | Description |
|---|---|---|
| Language | Python 3.10+ | Core application logic and asynchronous networking |
| GUI Framework | CustomTkinter | Desktop user interface with Apple Light design system |
| Icon Engine | Pillow (PIL) | Anti-aliased vector icon rendering and dynamic tinting |
| Local Proxy | Python `socket`, `threading` | SOCKS5 and HTTP proxy server with interface binding |
| Cloud Tunnel | Xray / Wintun / MASQUE | Multipath QUIC packet encapsulation (RFC 9484) |
| System Integration | Win32 Registry / ctypes | Windows system proxy configuration and route management |
| System Tray | pystray | Background notification area integration |
| Test Framework | pytest | Automated unit and integration test suite |

## Architecture

```
                    +---------------------------------------+
                    |          Client Applications          |
                    | (Web Browsers, Game Launchers, Tools) |
                    +---------------------------------------+
                                        |
                 +----------------------+----------------------+
                 | (Local Dispatcher)                          | (Cloud Bonding)
                 v                                             v
    +-------------------------+                   +-------------------------+
    | Local Proxy (127.0.0.1) |                   | Virtual Adapter (TUN)   |
    | SOCKS5 / HTTP Connect   |                   | Wintun Driver           |
    +-------------------------+                   +-------------------------+
                 |                                             |
                 v                                             v
    +-------------------------+                   +-------------------------+
    | Round-Robin Dispatcher  |                   | Multipath QUIC Tunnel   |
    | Dynamic Socket Binding  |                   | Packet Fragmentation    |
    +-------------------------+                   +-------------------------+
                 |                                             |
                 +----------------------+----------------------+
                                        |
                 +----------------------+----------------------+
                 |                      |                      |
                 v                      v                      v
        +----------------+     +----------------+     +----------------+
        | NIC 1 (Wi-Fi)  |     | NIC 2 (USB Wi-Fi) |  | NIC 3 (Cellular) |
        | 192.168.1.100  |     | 192.168.2.100  |     | 192.168.42.10  |
        +----------------+     +----------------+     +----------------+
                 |                      |                      |
                 v                      v                      v
        [ Local Gateway 1 ]    [ Local Gateway 2 ]    [ Local Gateway 3 ]
                 |                      |                      |
                 |                      | (Cloud Mode Only)    |
                 |                      +----------+-----------+
                 |                                 |
                 |                                 v
                 |                      +---------------------+
                 |                      | Remote Cloud Server |
                 |                      | Reassembly & NAT    |
                 |                      +---------------------+
                 v                                 v
        +-----------------------------------------------------+
        |                   Public Internet                   |
        +-----------------------------------------------------+
```

## Repository Structure

```
TurboBond/
├── bin/                          # Standalone binary drivers (wintun.dll, engine core)
├── scripts/                      # Deployment and installation scripts
│   └── setup_vps.sh              # 1-click cloud gateway installer for Ubuntu VPS
├── tests/                        # Automated test suite (54 unit and integration tests)
│   ├── test_config.py            # Configuration manager and profile persistence tests
│   ├── test_detector.py          # Network adapter detection and metric tests
│   ├── test_dispatcher.py        # Local dispatcher, SOCKS5, and HTTP proxy tests
│   ├── test_engine_manager.py    # Cloud bonding engine state transition tests
│   ├── test_route_manager.py     # Windows route table and gateway tests
│   ├── test_system_proxy.py      # System proxy configuration tests
│   ├── test_telemetry.py         # Bandwidth monitor and telemetry tests
│   └── test_ui_responsiveness.py # GUI responsiveness, WCAG contrast, and styling tests
├── turbobond/                    # Main package source code
│   ├── assets/                   # App icons, vector graphics, and logo assets
│   ├── core/                     # Networking, configuration, and engine logic
│   │   ├── config.py             # JSON configuration and encrypted profiles
│   │   ├── detector.py           # Physical network interface classification
│   │   ├── dispatcher.py         # Multi-interface SOCKS5/HTTP socket dispatcher
│   │   ├── engine_manager.py     # Background tunnel process manager
│   │   ├── route_manager.py      # Windows routing table manager
│   │   ├── system_proxy.py       # OS-level proxy registry controller
│   │   └── telemetry.py          # Real-time traffic rate sampler
│   └── ui/                       # Desktop user interface
│       ├── main_window.py        # Primary dashboard and navigation window
│       ├── settings_dialog.py    # Modal configuration dialog
│       ├── theme.py              # Apple Light theme tokens, fonts, and icon registry
│       ├── tray.py               # System tray manager
│       └── widgets/              # Reusable UI widgets
│           ├── adapter_card.py   # Interactive network card widget with signal metrics
│           └── traffic_bar.py    # Multi-link traffic distribution bar
├── main.py                       # Application entry point
├── requirements.txt              # Python runtime dependencies
├── build_exe.py                  # PyInstaller build script for Windows executable
├── LICENSE                       # Apache-2.0 open source license
└── README.md                     # Documentation
```

## Prerequisites

- Operating System: Windows 10, Windows 11, or Ubuntu Linux (20.04 or later).
- Python: Version 3.10, 3.11, 3.12, or 3.13.
- Network Hardware: At least two active network connections (for example, built-in Wi-Fi plus phone USB tethering, or Wi-Fi plus an Ethernet cable).
- Permissions: Administrator rights on Windows (or root permissions on Linux) are required to bind to individual physical network interfaces and configure system proxy settings.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Aizaz-Noor/Tandem.git
cd Tandem
```

### 2. Install Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

Package dependencies:
- `customtkinter`: Modern desktop UI library.
- `pillow`: Image processing and icon rendering.
- `pystray`: System tray icon integration.
- `pytest`: Test execution.
- `pyinstaller`: Standalone executable compilation.

## Running Tandem

Launch Tandem directly from your terminal:

```bash
python main.py
```

To run with automatic administrator elevation:

```bash
python main.py --admin
```

### First-Time Walkthrough (Zero Hardware Cost)

You can test link aggregation immediately using standard hardware:
1. Connect your computer to your primary Wi-Fi network.
2. Connect your mobile phone to a second Wi-Fi network (or enable cellular data).
3. Connect your phone to your computer with a USB cable and turn on **USB Tethering** in phone settings.
4. Your computer will detect the phone as a secondary network adapter.
5. Launch Tandem: both adapters appear on the dashboard.
6. Click **Start** to begin aggregation.

## Configuration

Tandem stores local configuration in `config.json` in the application directory.

### Available Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `mode` | string | `"local_dispatcher"` | Active bonding mode (`"local_dispatcher"` or `"cloud_bonding"`) |
| `auto_connect_on_launch` | boolean | `true` | Automatically starts bonding when active adapters are detected |
| `auto_proxy` | boolean | `true` | Automatically configures the Windows system proxy when starting |
| `dispatcher_port` | integer | `8080` | Port for the local dispatcher proxy server |
| `server_address` | string | `""` | Remote cloud bonding server IP or hostname |
| `server_port` | integer | `443` | Remote server UDP port |
| `auth_key` | string | `""` | Secret authentication key for cloud bonding gateway |
| `congestion_control` | string | `"bbr"` | QUIC congestion control algorithm (`"bbr"` or `"cubic"`) |
| `adapter_weights` | object | `{}` | Per-adapter traffic distribution weights |

### Exporting and Importing Profiles

Tandem allows you to export your configuration to a `.turbobond` profile file:
- To export: Open **Settings** -> Click **Export Profile** -> Choose file destination.
- To import: Open **Settings** -> Click **Import Profile** -> Select your `.turbobond` file. Settings apply immediately.

## Running Tests

Tandem includes an automated test suite with 54 unit and integration tests covering configuration management, adapter detection, local proxy mechanics, system proxy integration, routing tables, and UI responsiveness.

Execute the test suite with pytest:

```bash
pytest tests/ -v
```

All 54 tests execute in under 30 seconds with mock isolation for network hardware and system services.

## Compiling Standalone Executable

To build a standalone Windows binary (`Tandem.exe`) that runs without a Python installation:

```bash
python build_exe.py
```

The compiled binary will be placed in the `dist/` directory.

## Troubleshooting

### Windows SmartScreen or Elevation Prompt
- Problem: The application requests Administrator privileges on startup.
- Explanation: Windows requires administrative privileges to query interface routing metrics, bind sockets to specific network cards, and configure system proxy settings. Grant permission when prompted by User Account Control (UAC).

### Adapter Detected as Disconnected
- Problem: An adapter appears with a gray indicator or is missing an IP address.
- Solution: Ensure the adapter is actively connected to an access point and has received an IPv4 address via DHCP. Click the **Refresh** button in the top navigation bar to rescan active hardware.

### Web Browser Not Routing Through Dispatcher
- Problem: The dispatcher is active, but browser traffic is not distributed across adapters.
- Solution: Verify that your operating system proxy is enabled and pointing to `127.0.0.1:8080`. In Tandem, ensure the **Configure Windows Proxy Automatically** checkbox is enabled in Settings.

### Port 8080 Already in Use
- Problem: Error log indicates `Address already in use` on port 8080.
- Solution: Open **Settings** -> Change the **Local Proxy Port** to an available port (such as `8085` or `9090`) -> Click **Save Changes**.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
