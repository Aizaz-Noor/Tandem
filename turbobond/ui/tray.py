"""
TurboBond - System Tray Integration
Manages background tray icon, status tooltip, and quick action context menu using pystray.
"""

import sys
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw


def create_tray_icon_image(connected: bool = False) -> Image.Image:
    """Generate dynamic high-contrast tray icon image."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer circle
    color = (16, 185, 129, 255) if connected else (100, 116, 139, 255)
    draw.ellipse([4, 4, 60, 60], fill=color)

    # Center Lightning Bolt symbol
    bolt_color = (255, 255, 255, 255)
    bolt_points = [
        (34, 12),
        (20, 34),
        (32, 34),
        (26, 52),
        (46, 28),
        (34, 28)
    ]
    draw.polygon(bolt_points, fill=bolt_color)

    return img


class SystemTrayManager:
    """Manages the OS notification area icon."""

    def __init__(
        self,
        on_show: Callable,
        on_toggle: Callable,
        on_quit: Callable
    ):
        self.on_show = on_show
        self.on_toggle = on_toggle
        self.on_quit = on_quit
        self.icon = None
        self._thread = None
        self.is_connected = False

    def start(self):
        """Start tray icon in a dedicated daemon thread."""
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("Show Tandem", self._on_show_clicked, default=True),
                pystray.MenuItem(lambda text: "Disconnect" if self.is_connected else "Start Tandem", self._on_toggle_clicked),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Tandem", self._on_quit_clicked)
            )

            image = create_tray_icon_image(self.is_connected)
            self.icon = pystray.Icon(
                "Tandem",
                image,
                "Tandem: Multi-Link Aggregator",
                menu
            )

            self._thread = threading.Thread(target=self.icon.run, daemon=True)
            self._thread.start()

        except Exception as e:
            print(f"[Tray] Could not start system tray: {e}", file=sys.stderr)

    def update_status(self, connected: bool, speed_text: str = ""):
        """Update tray icon color and tooltip."""
        self.is_connected = connected
        if self.icon:
            try:
                self.icon.icon = create_tray_icon_image(connected)
                status = f"Tandem: {speed_text}" if connected else "Tandem: Standby"
                self.icon.title = status
            except Exception:
                pass

    def stop(self):
        """Stop and remove tray icon."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def _on_show_clicked(self, icon, item):
        if self.on_show:
            self.on_show()  # on_show already uses self.after()

    def _on_toggle_clicked(self, icon, item):
        if self.on_toggle:
            import tkinter
            try:
                if tkinter._default_root and tkinter._default_root.winfo_exists():
                    tkinter._default_root.after(0, self.on_toggle)
                else:
                    self.on_toggle()
            except Exception:
                pass

    def _on_quit_clicked(self, icon, item):
        if self.on_quit:
            import tkinter
            try:
                if tkinter._default_root and tkinter._default_root.winfo_exists():
                    tkinter._default_root.after(0, self.on_quit)
                else:
                    self.on_quit()
            except Exception:
                pass
