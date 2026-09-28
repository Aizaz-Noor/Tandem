# Tandem

Tandem is a desktop network tool with two modes. Local Dispatcher routes separate TCP connections through selected network adapters using a loopback SOCKS5/HTTP proxy. Cloud Bonding starts the bundled `mqvpn` engine and requires a compatible server. A single connection does not gain combined bandwidth in local mode.

## Supported setup

The desktop app uses Tauri 2, React 18, TypeScript, and a Python 3.10+ sidecar. The primary release target is Windows 10/11 with WebView2. The Python backend includes Linux detection and GNOME proxy support, but a Linux desktop package and cloud tunnel have not been validated for release. The optional legacy interface requires CustomTkinter, Pillow, and pystray.

Local mode needs active IPv4 adapters. Cloud mode also needs a compatible server, an auth key, and administrator rights on Windows. Cloud mode may change system routes; test it on the intended hardware before release. A system-wide kill switch is not implemented.

## Development

```powershell
python -m pip install -r requirements.txt
cd tandem-ui
npm ci
npm run tauri dev
```

Use `python main.py --legacy-ui` for the legacy interface. Running `python main.py` starts only the sidecar. The sidecar is launched automatically by the Tauri app.

Configuration is stored in `%APPDATA%\TurboBond\config.json` on Windows or `~/.config/turbobond/config.json` on Linux. Local mode defaults to port 8080 and can configure the system proxy. Automatic connection on launch is off by default. Cloud mode has no preset server and verifies the server certificate by default. The UI has an explicit option to allow an unverified certificate for servers using self-signed certificates; this weakens protection against interception.

Cloud credentials remain in the user configuration file. At engine launch, Tandem writes the auth key to a temporary JSON config with owner-only access and removes that file when the engine stops. The key is not placed in the engine process arguments.

Profiles exported by the legacy UI are **plain JSON**, including the cloud auth key. Treat `.turbobond` files as credentials. Do not publish or share them through untrusted channels. The Tauri UI currently supports editing settings but has no profile import/export controls.

## Tests and build

```powershell
python -m pytest tests -q
cd tandem-ui
npm test
npm run build
cd src-tauri
cargo check --target x86_64-pc-windows-gnu
```

Build the complete Windows desktop package from the repository root with `python build_exe.py`. The script bundles the Python sidecar, verifies its engine and WebSocket dependency, then invokes the Tauri build. `python build_exe.py --sidecar-only` builds only the sidecar. `python build_exe.py --legacy` builds the legacy interface. Outputs are written under `dist/` and `tandem-ui/src-tauri/target/`.

If the app exits while it owns the Windows proxy, the next launch attempts to restore the prior values. The Settings screen has an explicit reset action that clears the system proxy, including settings from another application. Use it only when you intend to reset the machine's proxy.

## Server deployment

`scripts/setup_vps.sh` is an example Ubuntu server setup script. It downloads mqvpn v0.16.3 for amd64 or arm64 and verifies the published SHA-256 before installation. Review its Docker image and firewall settings before running it on a production host. It creates a self-signed certificate; clients must explicitly opt into unverified certificates unless a trusted certificate is configured.

## License

The project is licensed under Apache License 2.0; see [LICENSE](LICENSE). The bundled `mqvpn` engine and libraries have separate notices in `bin/` and `bin/THIRD_PARTY_LICENSES/`.
