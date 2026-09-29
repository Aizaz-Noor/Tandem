# Tandem

Tandem helps a Windows PC use more than one internet connection. For example, you can connect Wi-Fi and a phone's USB tethering, then choose which connections Tandem may use. It has a simple local mode and an optional cloud mode for people who have their own compatible server.

**What to expect:** In Local Dispatcher mode, Tandem spreads *separate* app connections across the adapters you choose. It does **not** combine two connections into one faster download. Some apps ignore the Windows system proxy and will not use Local Dispatcher.

## Download and install

1. Open the [latest Tandem release](https://github.com/Aizaz-Noor/Tandem/releases/latest) and download **`Tandem_1.0.1_x64-setup.exe`** under **Assets**. The MSI on the same page is an alternative for managed Windows installations. The “Source code” downloads are for developers; they are not the installer.
2. Run the installer, then open **Tandem** from the Start menu.
3. Connect the internet links you want to use before opening Tandem (for example, Wi-Fi and USB tethering).

The current desktop installer is for **64-bit Windows 10/11** and needs WebView2. The installers are **not digitally signed**; Windows or your organization may warn or block an unsigned app. Check that you downloaded it from this project's GitHub release. If your device requires signed software, wait for a signed release.

## Your first connection

1. On **Dashboard**, check that your network adapters appear. Click **Refresh** if you plugged one in after opening Tandem.
2. Click the adapter cards you want to use. If you leave all cards unselected, Tandem uses all available adapters.
3. Open **Settings → General** and choose a mode. **Local Dispatcher** is the default and needs no server. Click **Save Settings** if you change anything.
4. Return to **Dashboard** and click **Start Bonding**. When it is running, the button changes to **Stop Bonding**. The speed meters show traffic that Tandem handles.
5. Click **Stop Bonding** before changing adapters or settings, or when you are done.

The **Backend ready** label only means Tandem's background service is available. It does not mean a connection is active.

| Mode | What it does | What you need |
| --- | --- | --- |
| **Local Dispatcher** | Sends separate proxy-aware app connections through selected adapters. | One or more active internet adapters. Tandem sets the Windows system proxy by default. |
| **Cloud Bonding** | Creates a tunnel to a compatible server and can use selected adapters as paths. | Your own compatible server address, port, auth key, and Administrator rights on Windows. |

### Using Cloud Bonding

Cloud Bonding is optional. Tandem does **not** include a public cloud account or server. Get the address, port, and auth key from the person who runs your compatible server. Do not post the auth key in an issue or share a settings/profile file that contains it.

1. Close Tandem, then right-click its Start menu entry and choose **Run as administrator**.
2. In **Settings → General**, select **Cloud Bonding**. Under **Cloud Bonding**, enter the server host, port, and auth key.
3. Leave **Allow an unverified server certificate** off for a server with a trusted certificate. Turn it on only if you control the server and know it uses a self-signed certificate; this reduces protection against interception. Click **Save Settings**.
4. On **Dashboard**, select your active adapters and click **Start Bonding**. Look for the cloud state to become **connected**. Click **Stop Bonding** to disconnect.

Cloud mode can change Windows network routes. A successful tunnel was checked with one adapter; combining multiple adapters and resulting speed gains have not been independently validated. Tandem has no system-wide kill switch.

## If something goes wrong

| What you see | What to try |
| --- | --- |
| **No active adapters found** | Check that Wi-Fi, Ethernet, or USB tethering is connected and has internet access, then click **Refresh**. |
| **Backend offline** or **Connecting to the Tandem backend…** stays on screen | Close and reopen Tandem. If it persists, reinstall the latest release and check **Activity Log** for an error. |
| **Cloud connection failed** | Confirm the server is running, the host and UDP port are correct, the auth key matches, and Tandem is running as Administrator. Check the server's cloud firewall for that UDP port. Use the unverified-certificate option only for a known self-signed server. |
| Browsing stays broken after Local Dispatcher closes | Reopen Tandem and disconnect. If Tandem still owns the Windows proxy, use **Settings → Diagnostics → Reset system proxy**. This reset clears the machine's proxy even if another app configured it, so check your proxy settings first. |

For more detail, open **Activity Log** in Tandem. If the problem continues, [open a GitHub issue](https://github.com/Aizaz-Noor/Tandem/issues) and describe what you tried. Before sharing a log or screenshot, remove credentials and other private information.

## Current limits and platform support

Tandem's packaged desktop release targets Windows 10/11 x64. A macOS installer and a Linux desktop package have not been validated or published. The Python backend includes Linux detection and GNOME proxy support, but that is not a supported desktop release. Automatic connection on launch is off by default. Local mode is a proxy, not a VPN or a system-wide privacy barrier; cloud mode also has no kill switch.

## For developers and server operators

The desktop app uses Tauri 2, React 18, TypeScript, and a Python 3.10+ sidecar. To run from source on Windows, install Python, Node.js/npm, Rust, and the Tauri build prerequisites, then run:

```powershell
python -m pip install -r requirements.txt
cd tandem-ui
npm.cmd ci
npm.cmd run tauri dev
```

Running `python main.py` starts only the sidecar; Tauri starts it automatically for the desktop app. `python main.py --legacy-ui` opens the optional legacy interface, which needs CustomTkinter, Pillow, and pystray. `run.bat` starts an existing local build or builds one first; ordinary users should install a release package instead.

To test and build:

```powershell
python -m pytest tests -q
cd tandem-ui
npm.cmd test
npm.cmd run build
cd src-tauri
cargo check --target x86_64-pc-windows-gnu
```

Run `python build_exe.py` from the repository root to package the Python sidecar and Windows app. `--sidecar-only` builds only the sidecar; `--legacy` builds the legacy interface. Generated output goes under `dist/` and `tandem-ui/src-tauri/target/`.

User settings are stored in `%APPDATA%\TurboBond\config.json` on Windows or `~/.config/turbobond/config.json` on Linux. Cloud credentials remain in this user file. At launch, Tandem gives the engine an owner-only temporary config and removes it when the engine stops; the auth key is not a process argument. Legacy `.turbobond` profile exports are plain JSON and may contain the key. The Tauri interface does not currently offer profile import/export controls.

`scripts/setup_vps.sh` is an example Ubuntu server deployment script. It downloads mqvpn v0.16.3 with SHA-256 verification and creates a self-signed certificate. Review its Docker and firewall settings before using it. If you used this script, the server port and auth key are in `/opt/turbobond-server/config/server.conf` on the server. Keep that file private.

### Usability improvements to build next

1. Add a first-run guide that explains the two modes and detects when no usable adapter is connected.
2. Replace networking jargon and raw engine errors in the app with clear actions users can take.
3. Add an in-app connection check that distinguishes backend availability, server reachability, authentication, and an active tunnel.

## License

Tandem is licensed under [Apache License 2.0](LICENSE). The bundled `mqvpn` engine and libraries have separate notices in `bin/` and `bin/THIRD_PARTY_LICENSES/`.
