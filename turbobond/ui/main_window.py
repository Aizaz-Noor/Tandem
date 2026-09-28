"""
Tandem - High-Contrast Apple Glassmorphic Light UI Dashboard
Engineered for ultra-fast user responsiveness (fully asynchronous operations),
flawless WCAG AAA contrast, and high-legibility Apple typography.
"""

import os
import sys
import time
import threading
import customtkinter as ctk
from tkinter import messagebox
from typing import Dict, List, Optional
from PIL import Image

from turbobond.core.config import ConfigManager
from turbobond.core.detector import detect_active_adapters, optimize_windows_multilink
from turbobond.core.telemetry import BandwidthMonitor
from turbobond.core.engine_manager import EngineManager, TunnelState, is_elevated, relaunch_as_admin
from turbobond.core.dispatcher import LocalDispatcher
from turbobond.core.route_manager import RouteManager
from turbobond.core.system_proxy import SystemProxyConfig
from turbobond.ui.theme import Colors, Fonts, Icons, style_segmented_button, apply_window_icon
from turbobond.ui.widgets.traffic_bar import TrafficDistributionBar
from turbobond.ui.widgets.adapter_card import AdapterCardWidget
from turbobond.ui.settings_dialog import SettingsDialog
from turbobond.ui.tray import SystemTrayManager


class MainWindow(ctk.CTk):
    """Tandem High-Contrast Apple Glassmorphic Light UI Dashboard."""

    def __init__(self):
        super().__init__()

        # Appearance configuration - Apple Light Mode
        ctk.set_appearance_mode("light")
        self.configure(fg_color=Colors.BG_AMBIENT)

        # Initialize Apple typography
        Fonts.init_fonts()

        from turbobond import __version__
        self.title(f"Tandem v{__version__} - Multi-Link Internet Aggregator")
        self.geometry("980x800")
        self.minsize(840, 640)
        self.bind("<Configure>", self._on_window_configure, add="+")

        # Set Window Taskbar/Title Icon
        apply_window_icon(self)

        # Core Services
        self.config = ConfigManager()
        self.monitor = BandwidthMonitor()
        self.engine = EngineManager(on_state_change=self._on_engine_state_change)
        self.tray = SystemTrayManager(
            on_show=self._show_window_from_tray,
            on_toggle=self._toggle_bonding,
            on_quit=self._quit_application
        )

        # Dispatcher Services (Local Mode)
        self.dispatcher: Optional[LocalDispatcher] = None
        self.route_manager = RouteManager()
        self.system_proxy = SystemProxyConfig()
        # Clean any orphaned proxy from prior crashes before starting
        SystemProxyConfig.cleanup_orphaned_proxy()
        self._dispatcher_active = False

        # State Variables
        self.detected_adapters: List[Dict[str, str]] = []
        self.adapter_cards: Dict[str, AdapterCardWidget] = {}
        self.is_monitoring = True
        self._closing = False
        self._is_refreshing = False
        self._has_auto_connected = False
        self.sidebar_nav_items: Dict[str, ctk.CTkButton] = {}
        self._active_nav_key = "speed"
        self._log_window: Optional[ctk.CTkToplevel] = None

        self._build_ui()
        self._apply_mode_ui()
        self.tray.start()

        # Non-blocking asynchronous adapter scan on launch
        self._refresh_adapters()

        # Intercept window close to minimize to tray
        self.protocol("WM_DELETE_WINDOW", self._on_close_to_tray)

        # Start background telemetry loop
        self.telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.telemetry_thread.start()

        # Start periodic adapter auto-refresh
        self._schedule_adapter_refresh()

    def _get_current_mode(self) -> str:
        return self.config.get("mode", "local_dispatcher")

    def _on_window_configure(self, event=None):
        """Responsive layout: Keeps content beautifully proportioned on wide screens without horizontal distortion."""
        if event and event.widget == self:
            try:
                scale = self._get_window_scaling()
                avail_w = event.width - int(240 * scale)
                target_phys = int(760 * scale)
                pad = max(20, (avail_w - target_phys) // 2)
                if getattr(self, "_current_hpad", None) != pad:
                    self._current_hpad = pad
                    self.main_container.pack_configure(padx=pad)
            except Exception:
                pass

    def _build_ui(self):
        """Construct the Tandem Apple Glassmorphic interface with Desktop Sidebar Navigation."""
        # ──────────────────────────────────────────────
        # 1. DESKTOP SIDEBAR NAVIGATION ("Side Line Menu")
        # ──────────────────────────────────────────────
        self.sidebar_frame = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color=Colors.SIDEBAR_BG,
            border_width=1,
            border_color=Colors.SIDEBAR_BORDER
        )
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # ── Sidebar Brand Header ──
        brand_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand_container.pack(side="top", fill="x", padx=16, pady=(20, 14))

        brand_header_row = ctk.CTkFrame(brand_container, fg_color="transparent")
        brand_header_row.pack(fill="x", anchor="w")

        # Tandem Icon
        self.logo_img = Icons.logo((32, 32))
        if self.logo_img:
            sidebar_logo = ctk.CTkLabel(brand_header_row, text="", image=self.logo_img)
            sidebar_logo.pack(side="left", padx=(0, 10))

        sidebar_title = ctk.CTkLabel(
            brand_header_row,
            text="Tandem",
            font=Fonts.title_brand(),
            text_color=Colors.TEXT_HERO
        )
        sidebar_title.pack(side="left")

        sidebar_sub = ctk.CTkLabel(
            brand_container,
            text="Multi-Link Internet Aggregator",
            font=Fonts.footer(),
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        sidebar_sub.pack(fill="x", pady=(3, 12))

        # Hairline separator
        brand_sep = ctk.CTkFrame(brand_container, height=1, fg_color=Colors.SIDEBAR_BORDER)
        brand_sep.pack(fill="x")

        # ── Sidebar Navigation Items ──
        nav_box = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        nav_box.pack(side="top", fill="x", padx=10, pady=10)

        nav_header = ctk.CTkLabel(
            nav_box,
            text="MENU",
            font=Fonts.badge_pill(),
            text_color=Colors.TEXT_MUTED,
            anchor="w"
        )
        nav_header.pack(fill="x", padx=8, pady=(0, 4))

        nav_items_config = [
            ("speed",    "  Speed Bonding",      Icons.bolt((16, 16), color=Colors.ACCENT_CYAN)),
            ("local",    "  Local Dispatcher",   Icons.refresh((16, 16))),
            ("cloud",    "  Cloud Bonding",      Icons.wifi((16, 16))),
            ("settings", "  Settings & Profiles", Icons.settings((16, 16))),
            ("logs",     "  System Logs",         Icons.logs((16, 16))),
        ]

        self.sidebar_nav_items = {}
        for key, text, icon in nav_items_config:
            btn = ctk.CTkButton(
                nav_box,
                text=text,
                image=icon,
                compound="left",
                anchor="w",
                height=38,
                corner_radius=8,
                font=Fonts.nav_button(),
                fg_color=Colors.NAV_ITEM_ACTIVE_BG if key == "speed" else "transparent",
                hover_color=Colors.NAV_ITEM_HOVER_BG,
                text_color=Colors.NAV_ITEM_ACTIVE_TEXT if key == "speed" else Colors.NAV_ITEM_TEXT,
                command=lambda k=key: self._select_nav(k)
            )
            btn.pack(fill="x", pady=2)
            self.sidebar_nav_items[key] = btn

        # ── Pinned Bottom Action Dock in Sidebar ──
        # Guaranteed visible: Packed with side="bottom" so it never drops off-screen!
        self.sidebar_dock = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar_dock.pack(side="bottom", fill="x", padx=14, pady=(0, 18))

        dock_sep = ctk.CTkFrame(self.sidebar_dock, height=1, fg_color=Colors.SIDEBAR_BORDER)
        dock_sep.pack(fill="x", pady=(0, 12))

        self.sidebar_link_badge = ctk.CTkLabel(
            self.sidebar_dock,
            text="● 0 LINKS READY",
            font=Fonts.badge_pill(),
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.SUB_CARD_BG,
            corner_radius=8,
            height=28
        )
        self.sidebar_link_badge.pack(fill="x", pady=(0, 10))

        self.btn_turbo = ctk.CTkButton(
            self.sidebar_dock,
            text=" START",
            image=Icons.bolt((18, 18), color="#FFFFFF"),
            compound="left",
            font=Fonts.action_button(),
            height=48,
            corner_radius=12,
            fg_color=Colors.BTN_PRIMARY,
            hover_color=Colors.BTN_PRIMARY_HOVER,
            command=self._toggle_bonding
        )
        self.btn_turbo.pack(fill="x", pady=(0, 8))

        self.sidebar_footnote = ctk.CTkLabel(
            self.sidebar_dock,
            text="Proxy: 127.0.0.1:8080 · 5ms",
            font=Fonts.footer(),
            text_color=Colors.TEXT_MUTED
        )
        self.sidebar_footnote.pack(fill="x")

        # ──────────────────────────────────────────────
        # 2. MAIN WORKSPACE / CONTENT AREA
        # ──────────────────────────────────────────────
        self.workspace_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace_frame.pack(side="left", fill="both", expand=True)

        self.main_container = ctk.CTkFrame(self.workspace_frame, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=8)

        # Top Bar (Title + Health Badge + Action Buttons)
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_bar.pack(fill="x", padx=4, pady=(12, 8))

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left")

        brand_row = ctk.CTkFrame(title_box, fg_color="transparent")
        brand_row.pack(anchor="w")

        title_lbl = ctk.CTkLabel(
            brand_row,
            text="Speed Bonding Dashboard",
            font=Fonts.title_brand(),
            text_color=Colors.TEXT_HERO
        )
        title_lbl.pack(side="left")

        # Apple-Style High-Contrast Health Badge
        self.link_count_badge = ctk.CTkLabel(
            brand_row,
            text="0 LINKS",
            font=Fonts.badge_pill(),
            text_color=Colors.ACCENT_CYAN_TEXT,
            fg_color=Colors.ACCENT_CYAN_GLOW,
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.link_count_badge.pack(side="left", padx=(10, 0))

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Real-time multi-WAN link aggregation and local proxy dispatcher",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_SECONDARY
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Top Bar Action Buttons
        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.pack(side="right")

        self.btn_refresh = ctk.CTkButton(
            btn_box,
            text=" Refresh",
            image=Icons.refresh((15, 15)),
            compound="left",
            width=96,
            height=32,
            font=Fonts.nav_button(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._refresh_adapters
        )
        self.btn_refresh.pack(side="left", padx=(0, 6))

        self.btn_settings = ctk.CTkButton(
            btn_box,
            text=" Settings",
            image=Icons.settings((15, 15)),
            compound="left",
            width=96,
            height=32,
            font=Fonts.nav_button(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._open_settings
        )
        self.btn_settings.pack(side="left", padx=(0, 6))

        self.btn_logs = ctk.CTkButton(
            btn_box,
            text=" Logs",
            image=Icons.logs((15, 15)),
            compound="left",
            width=80,
            height=32,
            font=Fonts.nav_button(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._show_logs
        )
        self.btn_logs.pack(side="left")

        # ── Mode Switcher Capsule ──
        mode_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        mode_frame.pack(fill="x", padx=4, pady=(2, 6))

        curr_mode = self._get_current_mode()
        initial_val = "Local Dispatcher" if curr_mode == "local_dispatcher" else "Cloud Bonding"
        self.mode_var = ctk.StringVar(value=initial_val)

        self.mode_toggle = ctk.CTkSegmentedButton(
            mode_frame,
            values=["Local Dispatcher", "Cloud Bonding"],
            variable=self.mode_var,
            command=self._on_mode_toggled,
            font=Fonts.section_header(),
            selected_color=Colors.ACCENT_CYAN,
            selected_hover_color=Colors.ACCENT_CYAN_DIM,
            unselected_color=Colors.CARD_BG,
            unselected_hover_color=Colors.CARD_BG_HOVER,
            corner_radius=10,
            height=36
        )
        self.mode_toggle.pack(fill="x")
        style_segmented_button(self.mode_toggle)

        # ── Hero Speedometer Frosted Glass Card ──
        self.hero_card = ctk.CTkFrame(
            self.main_container,
            corner_radius=16,
            fg_color=Colors.CARD_BG,
            border_width=1,
            border_color=Colors.BORDER_MUTED
        )
        self.hero_card.pack(fill="x", padx=4, pady=6)

        # Status Pill Badge (Interactive click to connect/disconnect)
        self.status_pill = ctk.CTkLabel(
            self.hero_card,
            text="● STANDBY  ·  Ready to Bond",
            font=Fonts.badge_pill(),
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.SUB_CARD_BG,
            corner_radius=14,
            padx=20,
            pady=7,
            cursor="hand2"
        )
        self.status_pill.pack(pady=(16, 6))
        self.status_pill.bind("<Button-1>", lambda e: self._toggle_bonding())

        # Massive Aggregated Throughput Readout
        speed_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        speed_box.pack(pady=2)

        self.speed_number_lbl = ctk.CTkLabel(
            speed_box,
            text="0.0",
            font=Fonts.hero_number(),
            text_color=Colors.TEXT_HERO
        )
        self.speed_number_lbl.pack(side="left")

        self.speed_unit_lbl = ctk.CTkLabel(
            speed_box,
            text=" Mbps",
            font=Fonts.hero_unit(),
            text_color=Colors.ACCENT_CYAN
        )
        self.speed_unit_lbl.pack(side="left", pady=(16, 0))

        self.speed_secondary_lbl = ctk.CTkLabel(
            self.hero_card,
            text="Aggregated Speed · ~0.0 MB/s",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_SECONDARY
        )
        self.speed_secondary_lbl.pack(pady=(0, 10))

        # Split Download / Upload Inset Cards (Fixed width 180px, zero jitter)
        stats_frame = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=16, pady=(0, 10))

        # Download card
        down_card = ctk.CTkFrame(
            stats_frame,
            fg_color=Colors.ACCENT_EMERALD_GLOW,
            border_width=1,
            border_color="#86EFAC",
            corner_radius=8
        )
        down_card.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self.stat_down_lbl = ctk.CTkLabel(
            down_card,
            text=" Download: 0.0 Mbps",
            image=Icons.arrow_down((14, 14)),
            compound="left",
            font=Fonts.speed_metric(),
            text_color=Colors.ACCENT_EMERALD_TEXT,
            width=180,
            pady=8
        )
        self.stat_down_lbl.pack()

        # Upload card
        up_card = ctk.CTkFrame(
            stats_frame,
            fg_color=Colors.ACCENT_CYAN_GLOW,
            border_width=1,
            border_color="#7DD3FC",
            corner_radius=8
        )
        up_card.pack(side="right", fill="both", expand=True, padx=(6, 0))

        self.stat_up_lbl = ctk.CTkLabel(
            up_card,
            text=" Upload: 0.0 Mbps",
            image=Icons.arrow_up((14, 14)),
            compound="left",
            font=Fonts.speed_metric(),
            text_color=Colors.ACCENT_CYAN_TEXT,
            width=180,
            pady=8
        )
        self.stat_up_lbl.pack()

        # Live Traffic Proportion Bar
        self.traffic_bar_frame = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        self.traffic_bar_frame.pack(fill="x", padx=16, pady=(0, 14))

        self.traffic_bar = TrafficDistributionBar(self.traffic_bar_frame)
        self.traffic_bar.pack(fill="x")

        # ── Physical Links Section ──
        section_row = ctk.CTkFrame(self.main_container, fg_color="transparent")
        section_row.pack(fill="x", padx=6, pady=(8, 4))

        self.section_lbl = ctk.CTkLabel(
            section_row,
            text="ACTIVE PHYSICAL LINKS",
            font=Fonts.section_header(),
            text_color=Colors.TEXT_PRIMARY
        )
        self.section_lbl.pack(side="left")

        self.bonded_count_lbl = ctk.CTkLabel(
            section_row,
            text="Scanning...",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_SECONDARY
        )
        self.bonded_count_lbl.pack(side="right")

        self.adapters_scroll = ctk.CTkScrollableFrame(
            self.main_container,
            height=200,
            corner_radius=12,
            fg_color=Colors.CARD_BG,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Colors.BORDER_MUTED,
            scrollbar_button_hover_color=Colors.TEXT_MUTED
        )
        self.adapters_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Help Callout
        self.hint_lbl = ctk.CTkLabel(
            self.main_container,
            text="Tip: Plug in as many USB dongles or phone tethers as you want — Tandem scales linearly!",
            font=Fonts.body_secondary(),
            text_color=Colors.ACCENT_CYAN_TEXT
        )
        self.hint_lbl.pack(pady=(4, 6))

        # Telemetry Status Footer
        footer_card = ctk.CTkFrame(
            self.main_container,
            fg_color=Colors.CARD_BG,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            height=30
        )
        footer_card.pack(fill="x", padx=4, pady=(0, 8))

        self.footer_lbl = ctk.CTkLabel(
            footer_card,
            text="Mode: Local Multi-WAN Dispatcher · Proxy: 127.0.0.1:8080 · Direct 5ms Latency",
            font=Fonts.footer(),
            text_color=Colors.TEXT_SECONDARY
        )
        self.footer_lbl.pack(pady=5)

    def _select_nav(self, key: str):
        """Handle sidebar navigation clicks."""
        if key == "speed":
            self._update_nav_selection("speed")
        elif key == "local":
            self._update_nav_selection("local")
            if self._get_current_mode() != "local_dispatcher":
                self.mode_var.set("Local Dispatcher")
                self._on_mode_toggled("Local Dispatcher")
        elif key == "cloud":
            self._update_nav_selection("cloud")
            if self._get_current_mode() != "cloud_bonding":
                self.mode_var.set("Cloud Bonding")
                self._on_mode_toggled("Cloud Bonding")
        elif key == "settings":
            self._open_settings()
        elif key == "logs":
            self._show_logs()

    def _update_nav_selection(self, active_key: str):
        """Highlight active navigation item in the sidebar."""
        self._active_nav_key = active_key
        for k, btn in self.sidebar_nav_items.items():
            if k == active_key:
                btn.configure(
                    fg_color=Colors.NAV_ITEM_ACTIVE_BG,
                    text_color=Colors.NAV_ITEM_ACTIVE_TEXT,
                    hover_color=Colors.NAV_ITEM_ACTIVE_BG
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=Colors.NAV_ITEM_TEXT,
                    hover_color=Colors.NAV_ITEM_HOVER_BG
                )

    def _on_mode_toggled(self, selected_text: str):
        new_mode = "local_dispatcher" if "Local" in selected_text else "cloud_bonding"

        if self._dispatcher_active or self.engine.state in [TunnelState.CONNECTED, TunnelState.CONNECTING]:
            messagebox.showwarning("Cannot Switch Mode", "Please disconnect before switching bonding mode.", parent=self)
            curr = self._get_current_mode()
            self.mode_var.set("Local Dispatcher" if curr == "local_dispatcher" else "Cloud Bonding")
            return

        self.config.set("mode", new_mode)
        self._apply_mode_ui()

    def _apply_mode_ui(self):
        mode = self._get_current_mode()
        if hasattr(self, "sidebar_nav_items") and self.sidebar_nav_items:
            if mode == "local_dispatcher":
                self._update_nav_selection("local" if self._active_nav_key == "local" else "speed")
            else:
                self._update_nav_selection("cloud" if self._active_nav_key == "cloud" else "speed")

        if mode == "local_dispatcher":
            proxy_port = self.config.get("proxy_port", 8080)
            self.footer_lbl.configure(
                text=f"Mode: Local Multi-WAN Dispatcher · Proxy: 127.0.0.1:{proxy_port} · Zero Cloud Overhead · 5ms Ping"
            )
            if hasattr(self, "sidebar_footnote"):
                self.sidebar_footnote.configure(
                    text=f"Proxy: 127.0.0.1:{proxy_port} · 5ms"
                )
            if not self._dispatcher_active:
                self.btn_turbo.configure(
                    text=" START",
                    image=Icons.bolt((18, 18)),
                    compound="left",
                    fg_color=Colors.BTN_PRIMARY,
                    hover_color=Colors.BTN_PRIMARY_HOVER
                )
            self.hint_lbl.configure(
                text="Tip: Local Dispatcher routes parallel download streams directly across your adapters at 5ms ping — zero encryption overhead!"
            )
        else:
            server_ip = self.config.get("server_host", "150.136.212.160")
            server_port = self.config.get("server_port", 443)
            self.footer_lbl.configure(
                text=f"Gateway: {server_ip}:{server_port} · Protocol: Multipath QUIC VPN"
            )
            if hasattr(self, "sidebar_footnote"):
                self.sidebar_footnote.configure(
                    text=f"Cloud: {server_ip}:{server_port}"
                )
            if self.engine.state != TunnelState.CONNECTED:
                self.btn_turbo.configure(
                    text=" CONNECT",
                    image=Icons.bolt((18, 18)),
                    compound="left",
                    fg_color=Colors.BTN_PRIMARY,
                    hover_color=Colors.BTN_PRIMARY_HOVER
                )
            self.hint_lbl.configure(
                text="Tip: Cloud Bonding mode tunnels and encrypts all system traffic through a remote Multipath QUIC server."
            )

    # ──────────────────────────────────────────────
    #  ASYNCHRONOUS NON-BLOCKING ADAPTER SCANNING
    # ──────────────────────────────────────────────

    def _refresh_adapters(self):
        """Scan and display detected physical network adapters asynchronously."""
        if self._is_refreshing:
            return
        self._is_refreshing = True

        self.btn_refresh.configure(text=" Scanning...", image=Icons.refresh((15, 15)), state="disabled")

        # Show non-blocking loading state if list is currently empty
        if not self.adapter_cards:
            for widget in self.adapters_scroll.winfo_children():
                widget.destroy()
            placeholder = ctk.CTkLabel(
                self.adapters_scroll,
                text="Scanning network adapters in background...",
                text_color=Colors.TEXT_SECONDARY,
                font=Fonts.card_title()
            )
            placeholder.pack(pady=35)

        def _scan_worker():
            try:
                adapters = detect_active_adapters()
            except Exception as e:
                print(f"[Detector] Scan error: {e}", file=sys.stderr)
                adapters = []

            if not self._closing:
                try:
                    if self.winfo_exists():
                        self.after(0, lambda: self._apply_detected_adapters(adapters))
                except Exception:
                    pass

        threading.Thread(target=_scan_worker, daemon=True).start()

    def _apply_detected_adapters(self, adapters: List[Dict[str, str]]):
        self._is_refreshing = False
        if self._closing:
            return

        self.btn_refresh.configure(text=" Refresh", image=Icons.refresh((15, 15)), state="normal")
        
        # Save existing user checkbox selections so refresh doesn't overwrite manual choices
        existing_selections = {name: card.is_selected() for name, card in self.adapter_cards.items()}
        self.detected_adapters = adapters

        # Rebuild adapter cards
        for widget in self.adapters_scroll.winfo_children():
            widget.destroy()
        self.adapter_cards.clear()

        count = len(self.detected_adapters)
        self.link_count_badge.configure(text=f"{count} {'LINK' if count == 1 else 'LINKS'}")

        if not self.detected_adapters:
            no_link_lbl = ctk.CTkLabel(
                self.adapters_scroll,
                text="No active network adapters found.\nPlease connect to Wi-Fi, Ethernet, or plug in USB Tethering.",
                text_color=Colors.ACCENT_ROSE_TEXT,
                font=Fonts.card_title()
            )
            no_link_lbl.pack(pady=35)
            self.bonded_count_lbl.configure(text="0 links available")
            return

        for adapter in self.detected_adapters:
            name = adapter["name"]
            initial_checked = existing_selections.get(name, True)
            card = AdapterCardWidget(
                self.adapters_scroll,
                adapter_info=adapter,
                initial_checked=initial_checked,
                on_toggle=self._on_adapter_toggled
            )
            self.adapter_cards[name] = card

        self._update_bonded_counter()

        if self._dispatcher_active and self.dispatcher:
            selected_ips = [
                card.ip for card in self.adapter_cards.values()
                if card.is_selected() and card.ip and not card.ip.startswith("Pending")
            ]
            n = len(selected_ips)
            lw = "LINK" if n == 1 else "LINKS"
            self.dispatcher.update_adapters(selected_ips)
            self.status_pill.configure(
                text=f"● DISPATCHER ACTIVE  ·  {n} {lw} BONDED",
                text_color=Colors.ACCENT_EMERALD_TEXT,
                fg_color=Colors.ACCENT_EMERALD_GLOW
            )
            self.tray.update_status(True, f"{n} links active")

        # Auto-connect immediately on launch if configured and not running under automated test suite
        if (
            self.config.get("auto_connect_on_launch", True)
            and not os.environ.get("PYTEST_CURRENT_TEST")
            and not self._has_auto_connected
            and not self._dispatcher_active
            and self.engine.state == TunnelState.DISCONNECTED
        ):
            valid_ips = [
                card.ip for card in self.adapter_cards.values()
                if card.is_selected() and card.ip and not card.ip.startswith("Pending")
            ]
            if valid_ips:
                self._has_auto_connected = True
                self.after(350, self._auto_connect_on_startup)

    def _auto_connect_on_startup(self):
        """Asynchronously initiate bonding on launch without blocking UI."""
        if self._closing:
            return
        mode = self._get_current_mode()
        if mode == "local_dispatcher" and not self._dispatcher_active:
            self._start_dispatcher()
        elif mode == "cloud_bonding" and self.engine.state == TunnelState.DISCONNECTED:
            # Only auto-connect cloud bonding if running elevated and auth key is present
            if is_elevated() and self.config.get("auth_key"):
                self._start_cloud_bonding()

    def _update_adapter_ips(self, adapters: List[Dict[str, str]]):
        """Update IP addresses in place without destroying cards or resetting selections."""
        if self._closing:
            return
        self.detected_adapters = adapters
        for ad in adapters:
            name = ad.get("name")
            ip = ad.get("ip", "")
            if name in self.adapter_cards:
                self.adapter_cards[name].set_ip(ip)

        if self._dispatcher_active and self.dispatcher:
            selected_ips = [
                card.ip for card in self.adapter_cards.values()
                if card.is_selected() and card.ip and not card.ip.startswith("Pending")
            ]
            n = len(selected_ips)
            lw = "LINK" if n == 1 else "LINKS"
            self.dispatcher.update_adapters(selected_ips)
            self.status_pill.configure(
                text=f"● DISPATCHER ACTIVE  ·  {n} {lw} BONDED",
                text_color=Colors.ACCENT_EMERALD_TEXT,
                fg_color=Colors.ACCENT_EMERALD_GLOW
            )
            self.tray.update_status(True, f"{n} links active")

    def _on_adapter_toggled(self, name: str, checked: bool):
        self._update_bonded_counter()
        if self._dispatcher_active and self.dispatcher:
            selected_ips = [
                card.ip for card in self.adapter_cards.values()
                if card.is_selected() and card.ip and not card.ip.startswith("Pending")
            ]
            n = len(selected_ips)
            lw = "LINK" if n == 1 else "LINKS"
            self.dispatcher.update_adapters(selected_ips)
            self.status_pill.configure(
                text=f"● DISPATCHER ACTIVE  ·  {n} {lw} BONDED",
                text_color=Colors.ACCENT_EMERALD_TEXT,
                fg_color=Colors.ACCENT_EMERALD_GLOW
            )
            self.tray.update_status(True, f"{n} links active")
            proxy_port = self.config.get("proxy_port", 8080)
            self.footer_lbl.configure(
                text=f"Proxy: 127.0.0.1:{proxy_port} · {n} Adapter{'s' if n != 1 else ''} Aggregated · 5ms Direct Ping"
            )

    def _update_bonded_counter(self):
        selected_count = sum(1 for c in self.adapter_cards.values() if c.is_selected())
        total_count = len(self.adapter_cards)
        self.bonded_count_lbl.configure(text=f"{selected_count} of {total_count} bonded")
        if hasattr(self, "sidebar_link_badge"):
            if self._dispatcher_active or self.engine.state == TunnelState.CONNECTED:
                self.sidebar_link_badge.configure(
                    text=f"● {selected_count} LINKS BONDED",
                    text_color=Colors.ACCENT_EMERALD_TEXT,
                    fg_color=Colors.ACCENT_EMERALD_GLOW
                )
            else:
                self.sidebar_link_badge.configure(
                    text=f"● {selected_count} OF {total_count} READY",
                    text_color=Colors.ACCENT_CYAN_TEXT if selected_count > 0 else Colors.TEXT_SECONDARY,
                    fg_color=Colors.ACCENT_CYAN_GLOW if selected_count > 0 else Colors.SUB_CARD_BG
                )

    def _schedule_adapter_refresh(self):
        if self._closing:
            return
        if self.engine.state == TunnelState.DISCONNECTED and not self._dispatcher_active and not self._is_refreshing:
            try:
                def _background_check():
                    try:
                        new_adapters = detect_active_adapters()
                        current_map = {a['name']: a.get('ip', '') for a in self.detected_adapters}
                        new_map = {a['name']: a.get('ip', '') for a in new_adapters}

                        if set(current_map.keys()) != set(new_map.keys()):
                            # Adapters added or removed
                            if not self._closing:
                                try:
                                    if self.winfo_exists():
                                        self.after(0, lambda: self._apply_detected_adapters(new_adapters))
                                except Exception:
                                    pass
                        elif current_map != new_map:
                            # Same adapters, but IPs changed (e.g. DHCP assigned!)
                            if not self._closing:
                                try:
                                    if self.winfo_exists():
                                        self.after(0, lambda: self._update_adapter_ips(new_adapters))
                                except Exception:
                                    pass
                    except Exception:
                        pass
                threading.Thread(target=_background_check, daemon=True).start()
            except Exception:
                pass
        if not self._closing:
            try:
                if self.winfo_exists():
                    self.after(10000, self._schedule_adapter_refresh)
            except Exception:
                pass

    def _toggle_bonding(self):
        mode = self._get_current_mode()
        if mode == "local_dispatcher":
            if self._dispatcher_active:
                self._stop_dispatcher()
            else:
                self._start_dispatcher()
        else:
            if self.engine.state in [TunnelState.CONNECTED, TunnelState.CONNECTING, TunnelState.RECONNECTING]:
                self.engine.stop()
                self._update_ui_disconnected()
            else:
                self._start_cloud_bonding()

    # ──────────────────────────────────────────────
    #  ASYNCHRONOUS LOCAL DISPATCHER START / STOP
    # ──────────────────────────────────────────────

    def _start_dispatcher(self):
        selected = [name for name, card in self.adapter_cards.items() if card.is_selected()]
        if not selected:
            messagebox.showwarning("No Adapters Selected", "Please select at least one network adapter to bond.", parent=self)
            return

        ip_by_name = {a.get("name"): a.get("ip", "") for a in self.detected_adapters}
        pending_adapters = [n for n in selected if ip_by_name.get(n, "").startswith("Pending") or not ip_by_name.get(n)]
        if pending_adapters:
            messagebox.showwarning(
                "Adapter Acquiring IP",
                "The following adapter(s) have not received an IP address yet:\n\n" +
                "\n".join([f"• {n}" for n in pending_adapters]) +
                "\n\nPlease wait a moment for DHCP or toggle USB Tethering on your phone.\nYou can also uncheck pending adapters to bond available links now.",
                parent=self
            )
            return

        adapter_ips = list(dict.fromkeys([ip_by_name[n] for n in selected if ip_by_name.get(n)]))
        if len(adapter_ips) < 1:
            messagebox.showerror("No Valid IPs", "No valid IP addresses found for selected adapters.", parent=self)
            return

        # Immediate responsive UI state
        self.btn_turbo.configure(
            text=" STARTING...",
            image=Icons.pulse((18, 18)),
            compound="left",
            state="disabled",
            fg_color=Colors.ACCENT_CYAN
        )
        self.status_pill.configure(
            text="● INITIALIZING DISPATCHER...",
            text_color=Colors.ACCENT_AMBER_TEXT,
            fg_color=Colors.ACCENT_AMBER_GLOW
        )

        proxy_port = int(self.config.get("proxy_port", 8080))
        strategy = self.config.get("distribution_strategy", "round_robin")
        selected_adapters = [a for a in self.detected_adapters if a["name"] in selected]

        def _start_worker():
            try:
                optimize_windows_multilink()

                if is_elevated():
                    self.route_manager.setup_routes(selected_adapters)

                self.dispatcher = LocalDispatcher(
                    host='127.0.0.1',
                    port=proxy_port,
                    adapter_ips=adapter_ips,
                    strategy=strategy,
                    adapter_weights={ip_by_name[name]: self.config.get("adapter_weights", {}).get(name, 1) for name in selected}
                )
                self.dispatcher.start_in_thread(timeout=3.0)

                if self.config.get("auto_system_proxy", True):
                    if not self.system_proxy.enable_proxy('127.0.0.1', proxy_port):
                        raise RuntimeError('Could not configure the system proxy')

                if not self._closing:
                    try:
                        if self.winfo_exists():
                            self.after(0, lambda: self._on_dispatcher_started(adapter_ips, proxy_port))
                    except Exception:
                        pass

            except Exception as e:
                # Defensive rollback
                if self.dispatcher:
                    try:
                        self.dispatcher.stop_from_thread()
                    except Exception:
                        pass
                    self.dispatcher = None
                if self.config.get("auto_system_proxy", True):
                    try:
                        self.system_proxy.disable_proxy()
                    except Exception:
                        pass
                if is_elevated():
                    try:
                        self.route_manager.cleanup_routes()
                    except Exception:
                        pass
                if not self._closing:
                    try:
                        if self.winfo_exists():
                            self.after(0, lambda err=e: self._on_dispatcher_error(err))
                    except Exception:
                        pass

        threading.Thread(target=_start_worker, daemon=True).start()

    def _on_dispatcher_started(self, adapter_ips: list, proxy_port: int):
        self._dispatcher_active = True
        n = len(adapter_ips)
        link_word = "LINK" if n == 1 else "LINKS"
        self.status_pill.configure(
            text=f"● DISPATCHER ACTIVE  ·  {n} {link_word} BONDED",
            text_color=Colors.ACCENT_EMERALD_TEXT,
            fg_color=Colors.ACCENT_EMERALD_GLOW
        )
        self.btn_turbo.configure(
            text=" STOP",
            image=Icons.disconnect((18, 18)),
            compound="left",
            state="normal",
            fg_color=Colors.BTN_DANGER,
            hover_color=Colors.BTN_DANGER_HOVER
        )
        self.footer_lbl.configure(
            text=f"Proxy: 127.0.0.1:{proxy_port} · {n} Adapter{'s' if n != 1 else ''} Aggregated · 5ms Direct Ping"
        )
        if hasattr(self, "sidebar_link_badge"):
            self.sidebar_link_badge.configure(
                text=f"● {n} {link_word} BONDED",
                text_color=Colors.ACCENT_EMERALD_TEXT,
                fg_color=Colors.ACCENT_EMERALD_GLOW
            )
        if hasattr(self, "sidebar_footnote"):
            self.sidebar_footnote.configure(
                text=f"Proxy: 127.0.0.1:{proxy_port} · Active"
            )
        self.tray.update_status(True, f"{n} links active")

    def _on_dispatcher_error(self, err: Exception):
        self._dispatcher_active = False
        messagebox.showerror("Dispatcher Error", f"Failed to start local proxy:\n\n{err}", parent=self)
        self._update_ui_disconnected()
        self.btn_turbo.configure(state="normal")

    def _stop_dispatcher(self):
        self.btn_turbo.configure(
            text=" STOPPING...",
            image=Icons.pulse((18, 18)),
            compound="left",
            state="disabled"
        )
        self.status_pill.configure(
            text="● DISCONNECTING...",
            text_color=Colors.TEXT_MUTED,
            fg_color=Colors.SUB_CARD_BG
        )

        def _stop_worker():
            if self.dispatcher:
                self.dispatcher.stop_from_thread()
                self.dispatcher = None

            if self.config.get("auto_system_proxy", True):
                self.system_proxy.disable_proxy()

            if is_elevated():
                self.route_manager.cleanup_routes()

            if not self._closing:
                self.after(0, self._on_dispatcher_stopped)

        threading.Thread(target=_stop_worker, daemon=True).start()

    def _on_dispatcher_stopped(self):
        self._dispatcher_active = False
        self._update_ui_disconnected()
        self.btn_turbo.configure(state="normal")

    # ──────────────────────────────────────────────
    #  CLOUD BONDING MODE (LEGACY)
    # ──────────────────────────────────────────────

    def _start_cloud_bonding(self):
        if not is_elevated():
            res = messagebox.askyesno(
                "Administrator Rights Required",
                "Tandem Cloud Bonding requires Administrator elevation to configure network adapters and routing.\n\nRelaunch as Administrator now?",
                parent=self
            )
            if res:
                relaunch_as_admin()
            return

        optimize_windows_multilink()

        selected = [name for name, card in self.adapter_cards.items() if card.is_selected()]
        if not selected:
            messagebox.showwarning("No Adapters Selected", "Please select at least one network adapter to bond.", parent=self)
            return

        ip_by_name = {a.get("name"): a.get("ip", "") for a in self.detected_adapters}
        pending_adapters = [n for n in selected if ip_by_name.get(n, "").startswith("Pending") or not ip_by_name.get(n)]
        if pending_adapters:
            messagebox.showwarning(
                "Adapter Acquiring IP",
                "The following adapter(s) have not received an IP address yet:\n\n" +
                "\n".join([f"• {n}" for n in pending_adapters]) +
                "\n\nPlease wait a moment for DHCP.",
                parent=self
            )
            return

        host = self.config.get("server_host", "150.136.212.160")
        port = int(self.config.get("server_port", 443))
        key = self.config.get("auth_key", "")
        sched = self.config.get("scheduler", "wlb")
        insecure = bool(self.config.get("insecure", True))
        dns = self.config.get("dns", ["1.1.1.1", "8.8.8.8"])

        if not key:
            messagebox.showerror("Missing Auth Key", "Please configure the server Auth Key in Settings before connecting.", parent=self)
            self._open_settings()
            return

        self.status_pill.configure(
            text=f"● CONNECTING ({len(selected)} LINKS)...",
            text_color=Colors.ACCENT_AMBER_TEXT,
            fg_color=Colors.ACCENT_AMBER_GLOW
        )
        self.btn_turbo.configure(
            text=" CONNECTING...",
            image=Icons.pulse((18, 18)),
            compound="left",
            state="disabled",
            fg_color=Colors.ACCENT_AMBER,
            hover_color=Colors.ACCENT_AMBER_GLOW
        )

        success = self.engine.start(
            server_host=host,
            server_port=port,
            auth_key=key,
            adapter_names=selected,
            scheduler=sched,
            insecure=insecure,
            dns_servers=dns
        )
        if not success:
            self._update_ui_disconnected()

    def _on_engine_state_change(self, state: TunnelState, message: str):
        self.after(0, lambda: self._apply_engine_state(state, message))

    def _apply_engine_state(self, state: TunnelState, message: str):
        if state == TunnelState.CONNECTED:
            selected_count = sum(1 for card in self.adapter_cards.values() if card.is_selected())
            link_word = "LINK" if selected_count == 1 else "LINKS"
            self.status_pill.configure(
                text=f"● CONNECTED  ·  {selected_count} {link_word} BONDED",
                text_color=Colors.ACCENT_EMERALD_TEXT,
                fg_color=Colors.ACCENT_EMERALD_GLOW
            )
            self.btn_turbo.configure(
                text=" STOP",
                image=Icons.disconnect((18, 18)),
                compound="left",
                fg_color=Colors.BTN_DANGER,
                hover_color=Colors.BTN_DANGER_HOVER
            )
            if hasattr(self, "sidebar_link_badge"):
                self.sidebar_link_badge.configure(
                    text=f"● {selected_count} {link_word} BONDED",
                    text_color=Colors.ACCENT_EMERALD_TEXT,
                    fg_color=Colors.ACCENT_EMERALD_GLOW
                )
            if hasattr(self, "sidebar_footnote"):
                self.sidebar_footnote.configure(
                    text="Cloud QUIC Tunnel · Active"
                )
            self.tray.update_status(True, f"{self.speed_number_lbl.cget('text')} Mbps")

        elif state == TunnelState.CONNECTING:
            self.status_pill.configure(
                text="● CONNECTING TO GATEWAY...",
                text_color=Colors.ACCENT_AMBER_TEXT,
                fg_color=Colors.ACCENT_AMBER_GLOW
            )
            self.btn_turbo.configure(
                text=" CONNECTING...",
                image=Icons.pulse((18, 18)),
                compound="left",
                fg_color=Colors.ACCENT_AMBER,
                hover_color=Colors.ACCENT_AMBER_GLOW
            )

        elif state == TunnelState.RECONNECTING:
            self.status_pill.configure(
                text="● RECONNECTING...",
                text_color=Colors.ACCENT_AMBER_TEXT,
                fg_color=Colors.ACCENT_AMBER_GLOW
            )
            self.btn_turbo.configure(
                text=" RECONNECTING...",
                image=Icons.pulse((18, 18)),
                compound="left",
                fg_color=Colors.ACCENT_AMBER,
                hover_color=Colors.ACCENT_AMBER_GLOW
            )

        elif state == TunnelState.ERROR:
            self._update_ui_disconnected()
            self.status_pill.configure(
                text="● CONNECTION ERROR",
                text_color=Colors.ACCENT_ROSE_TEXT,
                fg_color=Colors.ACCENT_ROSE_GLOW
            )
            self.btn_turbo.configure(
                text=" RETRY",
                image=Icons.refresh((18, 18)),
                compound="left",
                fg_color=Colors.BTN_PRIMARY,
                hover_color=Colors.BTN_PRIMARY_HOVER
            )
            if message:
                messagebox.showerror("Tandem Error", f"{message}", parent=self)

        elif state == TunnelState.DISCONNECTED:
            self._update_ui_disconnected()

    def _update_ui_disconnected(self):
        self.status_pill.configure(
            text="● STANDBY  ·  Ready to Bond",
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.SUB_CARD_BG
        )
        mode = self._get_current_mode()
        btn_text = " START" if mode == "local_dispatcher" else " CONNECT"
        self.btn_turbo.configure(
            text=btn_text,
            image=Icons.bolt((18, 18)),
            compound="left",
            fg_color=Colors.BTN_PRIMARY,
            hover_color=Colors.BTN_PRIMARY_HOVER
        )
        self.speed_number_lbl.configure(text="0.0")
        self.speed_secondary_lbl.configure(text="Standby · Ready to Bond")
        self.stat_down_lbl.configure(text=" Download: 0.0 Mbps")
        self.stat_up_lbl.configure(text=" Upload: 0.0 Mbps")
        self.traffic_bar.update_distribution({})
        self.tray.update_status(False)
        self._apply_mode_ui()
        if hasattr(self, "sidebar_link_badge"):
            selected_count = sum(1 for c in self.adapter_cards.values() if c.is_selected()) if self.adapter_cards else 0
            total_count = len(self.adapter_cards) if self.adapter_cards else 0
            self.sidebar_link_badge.configure(
                text=f"● {selected_count} of {total_count} Ready" if selected_count > 0 else "● Standby",
                text_color=Colors.ACCENT_CYAN_TEXT if selected_count > 0 else Colors.TEXT_SECONDARY,
                fg_color=Colors.ACCENT_CYAN_GLOW if selected_count > 0 else Colors.SUB_CARD_BG
            )
        if hasattr(self, "sidebar_footnote"):
            proxy_port = self.config.get("proxy_port", 8080)
            self.sidebar_footnote.configure(
                text=f"Proxy: 127.0.0.1:{proxy_port} · Standby"
            )

    def _telemetry_loop(self):
        consecutive_errors = 0
        while self.is_monitoring and not self._closing:
            try:
                active_names = [a["name"] for a in self.detected_adapters]
                stats = self.monitor.sample(active_names)

                total_down_mbps = stats["total"]["rx_mbps"]
                total_up_mbps = stats["total"]["tx_mbps"]
                total_mb_s = stats["total"]["rx_mb_s"]

                if not self._closing:
                    try:
                        if self.winfo_exists():
                            self.after(
                                0,
                                lambda d=total_down_mbps, u=total_up_mbps, m=total_mb_s, ad=stats["adapters"]: self._update_speed_ui(d, u, m, ad)
                            )
                    except Exception:
                        pass
                consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print(f"[Telemetry] Persistent error ({consecutive_errors}x): {e}", file=sys.stderr)
                    consecutive_errors = 0
            time.sleep(0.8)

    def _update_speed_ui(self, down_mbps: float, up_mbps: float, mb_s: float, adapter_stats: dict):
        if self._closing:
            return

        # 1. Update individual adapter hardware telemetry regardless of bonding state
        adapter_rx_dict = {}
        for name, card in list(self.adapter_cards.items()):
            try:
                astat = adapter_stats.get(name, {})
                adown = astat.get("rx_mbps", 0.0)
                aup = astat.get("tx_mbps", 0.0)
                card.update_telemetry(adown, aup)
                if card.is_selected():
                    adapter_rx_dict[name] = adown
            except Exception:
                pass

        # 2. Check active bonding state
        is_active = self.engine.state == TunnelState.CONNECTED or self._dispatcher_active
        if is_active:
            # Calculate aggregate throughput exclusively across bonded/selected links
            bonded_down = sum(adapter_rx_dict.values())
            bonded_up = sum(
                adapter_stats.get(name, {}).get("tx_mbps", 0.0)
                for name, card in self.adapter_cards.items()
                if card.is_selected()
            )
            bonded_mb_s = bonded_down / 8.0

            self.speed_number_lbl.configure(text=f"{bonded_down:.1f}")
            self.speed_secondary_lbl.configure(text=f"Aggregated Speed · ~{bonded_mb_s:.1f} MB/s")
            self.stat_down_lbl.configure(text=f" Download: {bonded_down:.1f} Mbps")
            self.stat_up_lbl.configure(text=f" Upload: {bonded_up:.1f} Mbps")
            self.traffic_bar.update_distribution(adapter_rx_dict)
            self.tray.update_status(True, f"{bonded_down:.1f} Mbps")
        else:
            # Standby state: keep hero card and distribution bar in clean Standby mode
            self.speed_number_lbl.configure(text="0.0")
            self.speed_secondary_lbl.configure(text="Standby · Ready to Bond")
            self.stat_down_lbl.configure(text=" Download: 0.0 Mbps")
            self.stat_up_lbl.configure(text=" Upload: 0.0 Mbps")
            self.traffic_bar.update_distribution({})
            self.tray.update_status(False)

    def _open_settings(self):
        SettingsDialog(self, self.config, on_save_callback=self._on_settings_saved)

    def _on_settings_saved(self):
        self._apply_mode_ui()

    def _show_logs(self):
        if self._log_window is not None and self._log_window.winfo_exists():
            self._log_window.lift()
            self._log_window.focus_force()
            return

        log_win = ctk.CTkToplevel(self)
        self._log_window = log_win
        log_win.title("Tandem - Telemetry & Engine Logs")
        dialog_w = 700
        dialog_h = 480
        log_win.geometry(f"{dialog_w}x{dialog_h}")
        log_win.minsize(500, 300)
        log_win.configure(fg_color=Colors.BG_AMBIENT)
        log_win.transient(self)

        try:
            self.update_idletasks()
            px = self.winfo_rootx()
            py = self.winfo_rooty()
            pw = self.winfo_width()
            ph = self.winfo_height()
            pos_x = max(40, px + (pw - dialog_w) // 2)
            pos_y = max(40, py + (ph - dialog_h) // 2)
            log_win.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")
        except Exception:
            pass

        apply_window_icon(log_win)

        # Top action bar in logs window
        top_bar = ctk.CTkFrame(log_win, fg_color="transparent")
        top_bar.pack(fill="x", padx=18, pady=(16, 10))

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left")

        log_logo = Icons.logo((28, 28))
        if log_logo:
            logo_lbl = ctk.CTkLabel(title_box, text="", image=log_logo)
            logo_lbl.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            title_box,
            text="Tandem — System Logs",
            font=Fonts.title_brand(),
            text_color=Colors.TEXT_HERO
        )
        title_lbl.pack(side="left")

        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.pack(side="right")

        text_box = ctk.CTkTextbox(
            log_win,
            font=Fonts.footer(),
            fg_color=Colors.CARD_BG,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED
        )
        text_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        def _populate_logs():
            text_box.configure(state="normal")
            text_box.delete("1.0", "end")
            logs = []
            if hasattr(self.engine, 'log_buffer'):
                logs.extend(list(self.engine.log_buffer))

            if self.dispatcher and self._dispatcher_active:
                stats = self.dispatcher.get_stats()
                logs.append("\n=== LOCAL MULTI-WAN DISPATCHER TELEMETRY ===")
                logs.append(f"Total Dispatched Connections: {stats['total']['connections_total']}")
                logs.append(f"Active Live Connections:     {stats['total']['connections_active']}")
                logs.append(f"Total Bytes Received (RX):   {stats['total']['bytes_rx']:,} bytes")
                logs.append(f"Total Bytes Sent (TX):       {stats['total']['bytes_tx']:,} bytes")
                logs.append("\n--- Per-Adapter Distribution ---")
                for ip, astats in stats.get('adapters', {}).items():
                    logs.append(f" • IP {ip:15} -> {astats['connections_total']} conns | RX: {astats['bytes_rx']:,} B | TX: {astats['bytes_tx']:,} B")

            if logs:
                text_box.insert("1.0", "\n".join(logs))
            else:
                text_box.insert("1.0", "No logs yet. Start bonding to see real-time output.")
            text_box.see("end")
            text_box.configure(state="disabled")

        def _copy_logs():
            text = text_box.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Logs copied to clipboard!", parent=log_win)

        btn_copy = ctk.CTkButton(
            btn_box,
            text=" Copy",
            image=Icons.copy((15, 15)),
            compound="left",
            font=Fonts.badge_pill(),
            width=80,
            height=28,
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=6,
            command=_copy_logs
        )
        btn_copy.pack(side="left", padx=(0, 6))

        btn_refresh_log = ctk.CTkButton(
            btn_box,
            text=" Refresh",
            image=Icons.refresh((15, 15)),
            compound="left",
            font=Fonts.badge_pill(),
            width=85,
            height=28,
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=6,
            command=_populate_logs
        )
        btn_refresh_log.pack(side="left")

        _populate_logs()

    def _on_close_to_tray(self):
        if self._log_window is not None and self._log_window.winfo_exists():
            try:
                self._log_window.withdraw()
            except Exception:
                pass

        if self.tray and self.tray.icon:
            self.withdraw()
        else:
            self._quit_application()

    def _show_window_from_tray(self):
        def _restore():
            if not self._closing and self.winfo_exists():
                self.deiconify()
                self.state('normal')
                self.lift()
                self.attributes('-topmost', True)
                self.after(50, lambda: self.attributes('-topmost', False) if not self._closing and self.winfo_exists() else None)
                self.focus_force()
        if not self._closing and self.winfo_exists():
            self.after(0, _restore)

    def _quit_application(self):
        self._closing = True
        self.is_monitoring = False

        # Synchronous cleanup to guarantee no proxy/route leaks on termination
        if self.dispatcher:
            try:
                self.dispatcher.stop_from_thread()
            except Exception:
                pass
            self.dispatcher = None

        if hasattr(self, 'system_proxy') and self.system_proxy:
            try:
                self.system_proxy.disable_proxy()
            except Exception:
                pass
        SystemProxyConfig.cleanup_orphaned_proxy()

        if is_elevated():
            try:
                self.route_manager.cleanup_routes()
            except Exception:
                pass

        try:
            self.engine.stop()
        except Exception:
            pass

        try:
            self.tray.stop()
        except Exception:
            pass

        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def destroy(self):
        if not self._closing:
            self._closing = True
            self.is_monitoring = False
            if self.dispatcher:
                try:
                    self.dispatcher.stop_from_thread()
                except Exception:
                    pass
                self.dispatcher = None
            if hasattr(self, 'system_proxy') and self.system_proxy:
                try:
                    self.system_proxy.disable_proxy()
                except Exception:
                    pass
            SystemProxyConfig.cleanup_orphaned_proxy()
        super().destroy()

