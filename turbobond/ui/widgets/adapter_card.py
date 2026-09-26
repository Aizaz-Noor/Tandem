"""
Tandem - High-Contrast Apple-Style Physical Link Card
Represents an individual physical network adapter (Wi-Fi, USB Tether, Ethernet)
with vector hardware badges, full-card hover elevation, whole-card click toggling,
and real-time live telemetry.
"""

import customtkinter as ctk
from typing import Callable, Optional
from turbobond.ui.theme import Colors, Fonts, Icons


class AdapterCardWidget(ctk.CTkFrame):
    """High-contrast Apple macOS white glass hardware link card."""

    def __init__(
        self,
        parent,
        adapter_info: dict,
        initial_checked: bool = True,
        on_toggle: Optional[Callable[[str, bool], None]] = None,
        **kwargs
    ):
        super().__init__(
            parent,
            corner_radius=12,
            fg_color=Colors.CARD_BG,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            **kwargs
        )

        self.adapter_info = adapter_info
        self.name = adapter_info.get("name", "Unknown")
        self.desc = adapter_info.get("description", "")
        self.ip = adapter_info.get("ip", "Pending IP...")
        self.atype = adapter_info.get("type", "other")
        self.on_toggle = on_toggle

        self.checked_var = ctk.BooleanVar(value=initial_checked)
        self._is_active_visual: Optional[bool] = None
        self._is_hovered: bool = False

        self._build_card()
        self._bind_hover_and_click()

    def _get_badge_meta(self):
        """Return (Icon_CTkImage, Badge Text, Text Color, Background Tint, Border Color)."""
        if self.atype == "usb_tether":
            return (
                Icons.cellular((16, 16)),
                "5G / CELLULAR TETHER",
                Colors.ACCENT_PURPLE_TEXT,
                Colors.ACCENT_PURPLE_GLOW,
                "#C4B5FD"
            )
        elif self.atype == "wifi":
            return (
                Icons.wifi((16, 16)),
                "WI-FI DUAL-BAND",
                Colors.ACCENT_CYAN_TEXT,
                Colors.ACCENT_CYAN_GLOW,
                "#7DD3FC"
            )
        elif self.atype == "ethernet":
            return (
                Icons.ethernet((16, 16)),
                "GIGABIT ETHERNET",
                Colors.ACCENT_EMERALD_TEXT,
                Colors.ACCENT_EMERALD_GLOW,
                "#86EFAC"
            )
        else:
            return (
                Icons.wifi((16, 16)),
                "NETWORK ADAPTER",
                Colors.TEXT_SECONDARY,
                Colors.SUB_CARD_BG,
                Colors.BORDER_MUTED
            )

    def _build_card(self):
        self.pack(fill="x", pady=5, padx=4)

        # Main horizontal container
        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.pack(fill="x", padx=16, pady=12)

        # ── Left: Toggle & Info ──
        self.left_box = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.left_box.pack(side="left", fill="both", expand=True)

        self.top_row = ctk.CTkFrame(self.left_box, fg_color="transparent")
        self.top_row.pack(fill="x", anchor="w")

        # Active Activity LED Indicator
        self.led_indicator = ctk.CTkLabel(
            self.top_row,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Colors.BORDER_MUTED,
            width=16
        )
        self.led_indicator.pack(side="left", padx=(0, 8))

        # Apple-Style High-Contrast Checkbox
        self.chk = ctk.CTkCheckBox(
            self.top_row,
            text=self.name,
            variable=self.checked_var,
            font=Fonts.card_title(),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.ACCENT_CYAN,
            hover_color=Colors.ACCENT_CYAN_DIM,
            border_color="#94A3B8",
            border_width=2,
            corner_radius=4,
            command=self._on_check_changed
        )
        self.chk.pack(side="left", padx=(0, 10))

        # Apple High-Contrast Translucent Category Badge with Vector Icon
        icon_img, badge_text, badge_fg, badge_bg, badge_border = self._get_badge_meta()
        self._badge_fg = badge_fg
        self._badge_bg = badge_bg
        self._badge_border = badge_border

        self.badge_frame = ctk.CTkFrame(
            self.top_row,
            fg_color=badge_bg,
            border_width=1,
            border_color=badge_border,
            corner_radius=6
        )
        self.badge_frame.pack(side="left", padx=4)

        self.badge_lbl = ctk.CTkLabel(
            self.badge_frame,
            text=f" {badge_text}",
            image=icon_img,
            compound="left",
            font=Fonts.badge_pill(),
            text_color=badge_fg,
            padx=8,
            pady=2
        )
        self.badge_lbl.pack()

        # Metadata Row (IP and Hardware Description in high-contrast slate)
        self.meta_row = ctk.CTkFrame(self.left_box, fg_color="transparent")
        self.meta_row.pack(fill="x", anchor="w", pady=(4, 0), padx=(24, 0))

        ip_display = self.ip if self.ip else "Pending IP..."
        desc_clean = self.desc[:45] + ("..." if len(self.desc) > 45 else "")
        self.meta_lbl = ctk.CTkLabel(
            self.meta_row,
            text=f"IP: {ip_display}  ·  {desc_clean}",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_SECONDARY
        )
        self.meta_lbl.pack(side="left")

        # ── Right: Live Speed Telemetry ──
        self.right_box = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.right_box.pack(side="right", padx=(10, 0))

        # Download speed with vector direction arrow
        self.speed_down_frame = ctk.CTkFrame(self.right_box, fg_color="transparent")
        self.speed_down_frame.pack(anchor="e")

        self.speed_down_lbl = ctk.CTkLabel(
            self.speed_down_frame,
            text=" 0.0 Mbps",
            image=Icons.arrow_down((12, 12)),
            compound="left",
            font=Fonts.speed_metric(),
            text_color="#15803D",  # Deep forest green (Contrast > 10:1)
            width=100,
            anchor="e"
        )
        self.speed_down_lbl.pack(anchor="e")

        # Upload speed with vector direction arrow
        self.speed_up_frame = ctk.CTkFrame(self.right_box, fg_color="transparent")
        self.speed_up_frame.pack(anchor="e")

        self.speed_up_lbl = ctk.CTkLabel(
            self.speed_up_frame,
            text=" 0.0 Mbps",
            image=Icons.arrow_up((12, 12)),
            compound="left",
            font=Fonts.speed_metric(),
            text_color="#075985",  # Deep ocean blue (Contrast > 9:1)
            width=100,
            anchor="e"
        )
        self.speed_up_lbl.pack(anchor="e")

        # Mini Link Saturation Bar
        self.meter_bar = ctk.CTkProgressBar(
            self.right_box,
            width=110,
            height=8,
            corner_radius=4,
            fg_color=Colors.SUB_CARD_BG,
            progress_color=Colors.ACCENT_CYAN
        )
        self.meter_bar.set(0.0)
        self.meter_bar.pack(anchor="e", pady=(6, 0))

    def _bind_hover_and_click(self):
        """Bind whole-card hover feedback and full-surface click toggling."""
        clickable_widgets = [
            self,
            self.inner,
            self.left_box,
            self.top_row,
            self.meta_row,
            self.meta_lbl,
            self.right_box,
            self.speed_down_frame,
            self.speed_down_lbl,
            self.speed_up_frame,
            self.speed_up_lbl,
            self.badge_frame,
            self.badge_lbl,
            self.led_indicator,
            self.meter_bar
        ]

        for widget in clickable_widgets:
            widget.bind("<Enter>", self._on_mouse_enter, add="+")
            widget.bind("<Leave>", self._on_mouse_leave, add="+")
            widget.bind("<Button-1>", self._on_card_click, add="+")

    def _is_within_card(self, event) -> bool:
        """Verify whether pointer coordinates remain inside this card's geometry."""
        if event is None:
            return False
        try:
            x, y = event.x_root, event.y_root
            card_x = self.winfo_rootx()
            card_y = self.winfo_rooty()
            card_w = self.winfo_width()
            card_h = self.winfo_height()
            return (card_x <= x <= card_x + card_w) and (card_y <= y <= card_y + card_h)
        except Exception:
            return False

    def _on_mouse_enter(self, event=None):
        self._is_hovered = True
        try:
            self.configure(cursor="hand2")
        except Exception:
            pass
        self._update_visual_state()

    def _on_mouse_leave(self, event=None):
        if self._is_within_card(event):
            # Pointer merely crossed into an internal child widget — avoid unhover flicker
            return
        self._is_hovered = False
        try:
            self.configure(cursor="")
        except Exception:
            pass
        self._update_visual_state()

    def _update_visual_state(self):
        """Synchronize colors and elevation according to selection, hover, and live activity."""
        try:
            if not self.is_selected():
                # Inactive / De-selected link card styling
                self.configure(border_color=Colors.BORDER_SUBTLE, fg_color=Colors.BG_SURFACE)
                self.chk.configure(text_color=Colors.TEXT_MUTED)
                self.led_indicator.configure(text_color=Colors.BORDER_MUTED)
                self.badge_frame.configure(fg_color=Colors.SUB_CARD_BG, border_color=Colors.BORDER_SUBTLE)
                self.badge_lbl.configure(text_color=Colors.TEXT_MUTED)
                self.meta_lbl.configure(text_color=Colors.TEXT_MUTED)
                self.speed_down_lbl.configure(text_color=Colors.TEXT_MUTED)
                self.speed_up_lbl.configure(text_color=Colors.TEXT_MUTED)
                self.meter_bar.configure(progress_color=Colors.BORDER_MUTED)
            else:
                # Active link card styling
                self.chk.configure(text_color=Colors.TEXT_PRIMARY)
                self.badge_frame.configure(fg_color=self._badge_bg, border_color=self._badge_border)
                self.badge_lbl.configure(text_color=self._badge_fg)
                self.meta_lbl.configure(text_color=Colors.TEXT_SECONDARY)
                self.speed_down_lbl.configure(text_color="#15803D")
                self.speed_up_lbl.configure(text_color="#075985")
                self.meter_bar.configure(progress_color=Colors.ACCENT_CYAN)

                if self._is_active_visual:
                    self.led_indicator.configure(text_color=Colors.ACCENT_EMERALD)
                    self.configure(border_color=Colors.BORDER_ACTIVE, fg_color=Colors.CARD_BG_ACTIVE)
                elif self._is_hovered:
                    self.led_indicator.configure(text_color=Colors.BORDER_MUTED)
                    self.configure(border_color=Colors.CARD_HOVER_BORDER, fg_color=Colors.CARD_HOVER_BG)
                else:
                    self.led_indicator.configure(text_color=Colors.BORDER_MUTED)
                    self.configure(border_color=Colors.BORDER_MUTED, fg_color=Colors.CARD_BG)
        except Exception:
            pass

    def _on_card_click(self, event=None):
        """Toggle adapter checkbox when clicking anywhere on the card surface."""
        new_val = not self.checked_var.get()
        self.checked_var.set(new_val)
        self._on_check_changed()

    def update_telemetry(self, rx_mbps: float, tx_mbps: float):
        """Update live speeds and dynamic visual activity."""
        self.speed_down_lbl.configure(text=f" {rx_mbps:.1f} Mbps")
        self.speed_up_lbl.configure(text=f" {tx_mbps:.1f} Mbps")

        saturation = min(rx_mbps / 100.0, 1.0)
        self.meter_bar.set(saturation)

        # Dynamic activity LED and subtle card highlight
        is_active = (rx_mbps > 0.3 or tx_mbps > 0.3) if self.is_selected() else False
        if is_active != self._is_active_visual:
            self._is_active_visual = is_active
            self._update_visual_state()

    def is_selected(self) -> bool:
        return self.checked_var.get()

    def set_ip(self, ip: str):
        self.ip = ip
        desc_clean = self.desc[:45] + ("..." if len(self.desc) > 45 else "")
        self.meta_lbl.configure(text=f"IP: {ip}  ·  {desc_clean}")

    def _on_check_changed(self):
        self._update_visual_state()
        if self.on_toggle:
            self.on_toggle(self.name, self.checked_var.get())

