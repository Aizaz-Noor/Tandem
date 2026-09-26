"""
Tandem - High-Contrast Apple-Style Traffic Distribution Bar
Renders a multi-channel visual telemetry bar showing the live bandwidth
distribution percentage across all active bonded network adapters in WCAG AAA contrast.
"""

import tkinter as tk
import customtkinter as ctk
from typing import Dict, List
from turbobond.ui.theme import Colors, Fonts

# High-Contrast Apple System Palette for distinct adapters
APPLE_LINK_PALETTE = [
    "#0071E3",  # Apple System Blue (Primary link)
    "#16A34A",  # Apple System Green (Secondary link)
    "#7C3AED",  # Apple System Indigo (Tertiary link)
    "#D97706",  # Apple System Amber (4th link)
    "#DB2777",  # Apple System Pink (5th link)
    "#0284C7",  # Apple System Sky Blue (6th link)
]


class TrafficDistributionBar(ctk.CTkFrame):
    """Visual multi-segment proportion bar displaying live per-adapter traffic share."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        # Header info row
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(0, 6))

        self.title_lbl = ctk.CTkLabel(
            self.header_frame,
            text="LINK TRAFFIC BALANCE",
            font=Fonts.badge_pill(),
            text_color=Colors.TEXT_PRIMARY
        )
        self.title_lbl.pack(side="left")

        self.ratio_lbl = ctk.CTkLabel(
            self.header_frame,
            text="Standby",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_MUTED
        )
        self.ratio_lbl.pack(side="right")

        # Drawing Canvas for the segmented multi-color bar with clear border
        self.canvas_height = 8
        self.canvas = tk.Canvas(
            self,
            height=self.canvas_height,
            bg=Colors.SUB_CARD_BG,
            highlightthickness=1,
            highlightbackground=Colors.BORDER_MUTED,
            bd=0
        )
        self.canvas.pack(fill="x", pady=(0, 8))
        self.canvas.bind("<Configure>", self._on_resize, add="+")

        # Legend row
        self.legend_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.legend_frame.pack(fill="x")
        self.legend_labels: Dict[str, ctk.CTkLabel] = {}
        self._last_adapter_speeds: Dict[str, float] = {}

    def _on_resize(self, event=None):
        """Redraw canvas on widget resize to ensure full width is filled cleanly."""
        if self._last_adapter_speeds:
            self.update_distribution(self._last_adapter_speeds)
        else:
            width = self.canvas.winfo_width()
            if width > 1:
                self.canvas.delete("all")
                self.canvas.create_rectangle(
                    0, 0, width, self.canvas_height,
                    fill=Colors.BORDER_SUBTLE, outline=""
                )

    def update_distribution(self, adapter_speeds: Dict[str, float]):
        """
        Update the visual proportion bar with live download speeds per adapter.
        adapter_speeds: {adapter_name: rx_mbps}
        """
        self._last_adapter_speeds = dict(adapter_speeds)
        total_speed = sum(adapter_speeds.values())

        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        if width <= 1:
            width = 500  # Fallback until packed

        # If no adapters provided (e.g. disconnected)
        if not adapter_speeds:
            self.canvas.create_rectangle(
                0, 0, width, self.canvas_height,
                fill=Colors.BORDER_SUBTLE, outline=""
            )
            self.ratio_lbl.configure(text="Standby", text_color=Colors.TEXT_MUTED)
            self._update_legend({}, 0.0, {})
            return

        # Calculate proportions for all bonded adapters
        proportions = {}
        for name, speed in adapter_speeds.items():
            clean_speed = max(speed, 0.0)
            ratio = (clean_speed / total_speed) if total_speed >= 0.1 else 0.0
            proportions[name] = (ratio, clean_speed)

        # Consistent adapter color mapping based on persistent adapter index
        name_to_color = {
            name: APPLE_LINK_PALETTE[i % len(APPLE_LINK_PALETTE)]
            for i, name in enumerate(proportions.keys())
        }

        # If zero or negligible traffic, draw subtle idle track
        if total_speed < 0.1:
            self.canvas.create_rectangle(
                0, 0, width, self.canvas_height,
                fill=Colors.BORDER_SUBTLE, outline=""
            )
            self.ratio_lbl.configure(text="Idle · 0.0 Mbps", text_color=Colors.TEXT_MUTED)
            self._update_legend(proportions, 0.0, name_to_color)
            return

        # Draw active proportional segments with matching persistent palette colors
        x_cursor = 0
        active_names = [n for n, (r, s) in proportions.items() if s > 0]
        for name in active_names:
            ratio, speed = proportions[name]
            segment_width = int(ratio * width)
            color = name_to_color[name]

            self.canvas.create_rectangle(
                x_cursor, 0, x_cursor + segment_width, self.canvas_height,
                fill=color, outline=""
            )
            x_cursor += segment_width

        # Fill remaining pixels if rounding left a slight gap
        if x_cursor < width and active_names:
            last_color = name_to_color[active_names[-1]]
            self.canvas.create_rectangle(x_cursor, 0, width, self.canvas_height, fill=last_color, outline="")

        # Update ratio text in high-contrast blue
        summary_parts = [
            f"{name[:12]}: {ratio*100:.0f}%"
            for name, (ratio, speed) in proportions.items()
            if speed > 0
        ]
        self.ratio_lbl.configure(
            text=" | ".join(summary_parts) if summary_parts else f"{total_speed:.1f} Mbps",
            text_color=Colors.ACCENT_CYAN_TEXT
        )

        self._update_legend(proportions, total_speed, name_to_color)

    def _update_legend(self, proportions: Dict[str, tuple], total_speed: float, name_to_color: Dict[str, str]):
        """Update colored dot badges below the bar without destroying widgets on every tick."""
        if not proportions:
            if self.legend_labels:
                for widget in self.legend_frame.winfo_children():
                    widget.destroy()
                self.legend_labels.clear()
            return

        # Reuse existing labels if keys match to eliminate UI garbage collection and flicker
        if set(self.legend_labels.keys()) == set(proportions.keys()):
            for name, (ratio, speed) in proportions.items():
                display_name = name[:14] + ".." if len(name) > 16 else name
                pct = f" ({ratio*100:.0f}%)" if total_speed >= 0.1 else ""
                self.legend_labels[name].configure(
                    text=f"{display_name}: {speed:.1f} Mbps{pct}"
                )
            return

        # Rebuild legend when adapter set changes
        for widget in self.legend_frame.winfo_children():
            widget.destroy()
        self.legend_labels.clear()

        for name, (ratio, speed) in proportions.items():
            color = name_to_color.get(name, APPLE_LINK_PALETTE[0])
            chip = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
            chip.pack(side="left", padx=(0, 14))

            dot = ctk.CTkLabel(
                chip,
                text="●",
                font=Fonts.speed_metric(),
                text_color=color
            )
            dot.pack(side="left", padx=(0, 4))

            display_name = name[:14] + ".." if len(name) > 16 else name
            pct = f" ({ratio*100:.0f}%)" if total_speed >= 0.1 else ""
            text = f"{display_name}: {speed:.1f} Mbps{pct}"
            lbl = ctk.CTkLabel(
                chip,
                text=text,
                font=Fonts.body_secondary(),
                text_color=Colors.TEXT_SECONDARY
            )
            lbl.pack(side="left")
            self.legend_labels[name] = lbl

