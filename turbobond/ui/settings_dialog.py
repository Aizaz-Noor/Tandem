"""
Tandem - Apple Glassmorphism Settings & Profile Dialog
Configures Local Dispatcher and Cloud Bonding parameters in a macOS-inspired
frosted glass modal dialog with 1-click import/export profiles.
"""

import re
import base64
import socket
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Callable, Optional
from turbobond.core.config import ConfigManager
from turbobond.core.system_proxy import SystemProxyConfig
from turbobond.ui.theme import Colors, Fonts, Icons, style_segmented_button, apply_window_icon


class SettingsDialog(ctk.CTkToplevel):
    """Apple Glassmorphism Light Settings modal dialog."""

    def __init__(self, parent, config: ConfigManager, on_save_callback: Optional[Callable] = None):
        super().__init__(parent)
        self.config = config
        self.on_save_callback = on_save_callback

        self.title("Tandem - Configuration & Settings")
        dialog_w = 600
        dialog_h = 630
        self.geometry(f"{dialog_w}x{dialog_h}")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_AMBIENT)

        # Center modal dialog directly over parent window
        try:
            parent.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            pos_x = max(40, px + (pw - dialog_w) // 2)
            pos_y = max(40, py + (ph - dialog_h) // 2)
            self.geometry(f"{dialog_w}x{dialog_h}+{pos_x}+{pos_y}")
        except Exception:
            pass

        self.transient(parent)
        self.grab_set()

        apply_window_icon(self)

        self._build_ui()

    def _build_ui(self):
        # Header with official Tandem logo
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 10))

        header_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_row.pack(fill="x", anchor="w")

        logo_img = Icons.logo((32, 32))
        if logo_img:
            logo_lbl = ctk.CTkLabel(header_row, text="", image=logo_img)
            logo_lbl.pack(side="left", padx=(0, 12))

        title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        title_box.pack(side="left")

        title_lbl = ctk.CTkLabel(
            title_box,
            text="Tandem Settings",
            font=Fonts.title_brand(),
            text_color=Colors.TEXT_HERO
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Configure network topology, proxy ports, and link aggregation.",
            font=Fonts.body_secondary(),
            text_color=Colors.TEXT_SECONDARY
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Apple Glass TabView
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=Colors.CARD_BG,
            segmented_button_fg_color=Colors.SUB_CARD_BG,
            segmented_button_selected_color=Colors.ACCENT_CYAN,
            segmented_button_selected_hover_color=Colors.ACCENT_CYAN_DIM,
            segmented_button_unselected_color=Colors.CARD_BG,
            segmented_button_unselected_hover_color=Colors.CARD_BG_HOVER,
            corner_radius=12,
            border_width=1,
            border_color=Colors.BORDER_MUTED
        )
        self.tabview.pack(fill="both", expand=True, padx=24, pady=5)

        tab_local = self.tabview.add("Local Dispatcher")
        tab_cloud = self.tabview.add("Cloud Bonding")

        # Style tabview segmented button for WCAG AAA contrast
        if hasattr(self.tabview, "_segmented_button"):
            style_segmented_button(self.tabview._segmented_button)

        self._build_local_dispatcher_tab(tab_local)
        self._build_cloud_bonding_tab(tab_cloud)

        # Bottom Area
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=24, pady=(10, 18))

        # Profile Sharing Row
        share_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        share_frame.pack(fill="x", pady=(0, 14))

        btn_export = ctk.CTkButton(
            share_frame,
            text=" Export Profile",
            image=Icons.export_icon((16, 16)),
            compound="left",
            font=Fonts.badge_pill(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._export_profile
        )
        btn_export.pack(side="left", padx=(0, 10))

        btn_import = ctk.CTkButton(
            share_frame,
            text=" Import Profile",
            image=Icons.import_icon((16, 16)),
            compound="left",
            font=Fonts.badge_pill(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._import_profile
        )
        btn_import.pack(side="left")

        # Action Buttons
        btn_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=Fonts.badge_pill(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            width=100,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save Settings",
            font=Fonts.badge_pill(),
            fg_color=Colors.BTN_PRIMARY,
            hover_color=Colors.BTN_PRIMARY_HOVER,
            corner_radius=8,
            width=130,
            command=self._save_settings
        )
        btn_save.pack(side="right")

    def _bind_focus_glow(self, entry: ctk.CTkEntry):
        """Add Apple Blue focus ring when input field is active without geometry jitter."""
        entry.configure(border_width=2, border_color=Colors.BORDER_MUTED)
        entry.bind("<FocusIn>", lambda e: entry.configure(border_color=Colors.INPUT_FOCUS_BORDER), add="+")
        entry.bind("<FocusOut>", lambda e: entry.configure(border_color=Colors.BORDER_MUTED), add="+")

    def _build_local_dispatcher_tab(self, tab):
        info_card = ctk.CTkFrame(
            tab,
            fg_color="#F0F9FF",
            corner_radius=8,
            border_width=1,
            border_color="#E0F2FE"
        )
        info_card.pack(fill="x", padx=16, pady=(14, 16))

        info_lbl = ctk.CTkLabel(
            info_card,
            text="Local Dispatcher routes your parallel downloads directly through multiple local network adapters at 5ms ping — zero VPS latency, zero encryption overhead.",
            font=Fonts.body_text(),
            text_color="#0369A1",
            justify="left",
            wraplength=490,
            padx=14,
            pady=10
        )
        info_lbl.pack()

        form_card = ctk.CTkFrame(tab, fg_color="transparent")
        form_card.pack(fill="x", padx=16)

        # Proxy Port
        ctk.CTkLabel(form_card, text="Local Proxy Port:", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", pady=10
        )
        self.proxy_port_entry = ctk.CTkEntry(
            form_card,
            width=140,
            font=Fonts.mono_meta(),
            fg_color=Colors.SUB_CARD_BG,
            border_color=Colors.BORDER_MUTED,
            text_color=Colors.TEXT_HERO
        )
        self.proxy_port_entry.insert(0, str(self.config.get("proxy_port", 8080)))
        self._bind_focus_glow(self.proxy_port_entry)
        self.proxy_port_entry.grid(row=0, column=1, sticky="w", padx=16, pady=10)

        # Distribution Strategy
        ctk.CTkLabel(form_card, text="Balancing Strategy:", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=1, column=0, sticky="w", pady=10
        )
        self.dist_strategy_menu = ctk.CTkOptionMenu(
            form_card,
            values=["Round-Robin (Balanced)", "Weighted (Manual)"],
            width=240,
            font=Fonts.badge_pill(),
            fg_color=Colors.SUB_CARD_BG,
            button_color=Colors.BORDER_MUTED,
            button_hover_color="#CBD5E1",
            text_color=Colors.TEXT_PRIMARY
        )
        curr_dist = self.config.get("distribution_strategy", "round_robin")
        self.dist_strategy_menu.set("Weighted (Manual)" if curr_dist == "weighted" else "Round-Robin (Balanced)")
        self.dist_strategy_menu.grid(row=1, column=1, sticky="w", padx=16, pady=10)

        # Auto System Proxy
        self.auto_proxy_var = ctk.BooleanVar(value=bool(self.config.get("auto_system_proxy", True)))
        self.auto_proxy_check = ctk.CTkCheckBox(
            form_card,
            text="Auto-Configure Windows System Proxy (Browser/Apps use it automatically)",
            variable=self.auto_proxy_var,
            font=Fonts.body_text(),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.ACCENT_CYAN,
            hover_color=Colors.ACCENT_CYAN_DIM,
            border_color="#CBD5E1",
            corner_radius=4
        )
        self.auto_proxy_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 6))

        # Auto-Connect on Launch
        self.auto_connect_var = ctk.BooleanVar(value=bool(self.config.get("auto_connect_on_launch", True)))
        self.auto_connect_check = ctk.CTkCheckBox(
            form_card,
            text="Auto-Connect & Bond Links Immediately on Application Launch",
            variable=self.auto_connect_var,
            font=Fonts.body_text(),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.ACCENT_CYAN,
            hover_color=Colors.ACCENT_CYAN_DIM,
            border_color="#CBD5E1",
            corner_radius=4
        )
        self.auto_connect_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 10))

        # Restore Direct Internet Tool Frame
        proxy_tool_frame = ctk.CTkFrame(
            form_card,
            fg_color=Colors.SUB_CARD_BG,
            corner_radius=6,
            border_width=1,
            border_color=Colors.BORDER_MUTED
        )
        proxy_tool_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 4))

        def _do_reset_system_proxy():
            SystemProxyConfig.cleanup_orphaned_proxy(force=True)
            self.lbl_reset_feedback.configure(
                text="Direct Internet restored (proxy disabled)",
                text_color=Colors.ACCENT_EMERALD
            )

        btn_reset_proxy = ctk.CTkButton(
            proxy_tool_frame,
            text="Reset Windows Proxy Now",
            command=_do_reset_system_proxy,
            font=Fonts.button(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            height=28
        )
        btn_reset_proxy.pack(side="left", padx=10, pady=8)

        self.lbl_reset_feedback = ctk.CTkLabel(
            proxy_tool_frame,
            text="Restores direct connection if browser gets stuck without Tandem",
            font=Fonts.caption(),
            text_color=Colors.TEXT_MUTED
        )
        self.lbl_reset_feedback.pack(side="left", padx=(4, 10), pady=8)

    def _build_cloud_bonding_tab(self, tab):
        form_card = ctk.CTkFrame(tab, fg_color="transparent")
        form_card.pack(fill="x", padx=16, pady=14)

        # Server Host
        ctk.CTkLabel(form_card, text="Server IP / Hostname:", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", pady=8
        )
        self.host_entry = ctk.CTkEntry(
            form_card,
            width=280,
            font=Fonts.mono_meta(),
            fg_color=Colors.SUB_CARD_BG,
            border_color=Colors.BORDER_MUTED,
            text_color=Colors.TEXT_HERO
        )
        self.host_entry.insert(0, str(self.config.get("server_host", "")))
        self._bind_focus_glow(self.host_entry)
        self.host_entry.grid(row=0, column=1, sticky="w", padx=16, pady=8)

        # Server Port
        ctk.CTkLabel(form_card, text="Server Port (UDP):", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=1, column=0, sticky="w", pady=8
        )
        self.port_entry = ctk.CTkEntry(
            form_card,
            width=120,
            font=Fonts.mono_meta(),
            fg_color=Colors.SUB_CARD_BG,
            border_color=Colors.BORDER_MUTED,
            text_color=Colors.TEXT_HERO
        )
        self.port_entry.insert(0, str(self.config.get("server_port", 443)))
        self._bind_focus_glow(self.port_entry)
        self.port_entry.grid(row=1, column=1, sticky="w", padx=16, pady=8)

        # Auth Key
        ctk.CTkLabel(form_card, text="Secret Auth Key (PSK):", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=2, column=0, sticky="w", pady=8
        )
        self.key_entry = ctk.CTkEntry(
            form_card,
            width=280,
            show="•",
            font=Fonts.mono_meta(),
            fg_color=Colors.SUB_CARD_BG,
            border_color=Colors.BORDER_MUTED,
            text_color=Colors.TEXT_HERO
        )
        self.key_entry.insert(0, str(self.config.get("auth_key", "")))
        self._bind_focus_glow(self.key_entry)
        self.key_entry.grid(row=2, column=1, sticky="w", padx=16, pady=8)

        # Scheduler
        ctk.CTkLabel(form_card, text="Bonding Scheduler:", font=Fonts.section_header(), text_color=Colors.TEXT_PRIMARY).grid(
            row=3, column=0, sticky="w", pady=8
        )
        self.scheduler_menu = ctk.CTkOptionMenu(
            form_card,
            values=["wlb (Balanced Throughput)", "minrtt (Low Latency / Gaming)"],
            width=240,
            font=Fonts.badge_pill(),
            fg_color=Colors.SUB_CARD_BG,
            button_color=Colors.BORDER_MUTED,
            button_hover_color="#CBD5E1",
            text_color=Colors.TEXT_PRIMARY
        )
        curr_sched = self.config.get("scheduler", "wlb")
        self.scheduler_menu.set("minrtt (Low Latency / Gaming)" if curr_sched == "minrtt" else "wlb (Balanced Throughput)")
        self.scheduler_menu.grid(row=3, column=1, sticky="w", padx=16, pady=8)

        # Insecure Checkbox
        self.insecure_var = ctk.BooleanVar(value=bool(self.config.get("insecure", False)))
        self.insecure_check = ctk.CTkCheckBox(
            form_card,
            text="Allow Self-Signed TLS Certificate",
            variable=self.insecure_var,
            font=Fonts.body_text(),
            text_color=Colors.TEXT_PRIMARY,
            fg_color=Colors.ACCENT_CYAN,
            hover_color=Colors.ACCENT_CYAN_DIM,
            border_color="#CBD5E1",
            corner_radius=4
        )
        self.insecure_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 10))

        self.btn_test = ctk.CTkButton(
            form_card,
            text="Test Cloud Connection",
            font=Fonts.badge_pill(),
            fg_color=Colors.CARD_BG,
            hover_color=Colors.CARD_BG_HOVER,
            text_color=Colors.ACCENT_CYAN,
            border_width=1,
            border_color=Colors.BORDER_MUTED,
            corner_radius=8,
            command=self._test_connection
        )
        self.btn_test.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 10))

    def _safe_after(self, callback: Callable):
        """Schedule callback on main thread if window still exists."""
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass

    def _test_connection(self):
        host = self.host_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            port = 443

        if not host:
            messagebox.showerror("Error", "Please enter a server host/IP first.", parent=self)
            return

        self.btn_test.configure(text=" Testing Connection...", state="disabled")

        def _do_test():
            try:
                reachable = False
                for probe_port in (22, port):
                    try:
                        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        tcp_sock.settimeout(2.5)
                        if tcp_sock.connect_ex((host, probe_port)) == 0:
                            reachable = True
                            tcp_sock.close()
                            break
                        tcp_sock.close()
                    except Exception:
                        pass

                if not reachable:
                    try:
                        import subprocess
                        ping_cmd = ["ping", "-n", "1", "-w", "1500", host]
                        res = subprocess.run(ping_cmd, capture_output=True, timeout=3)
                        if res.returncode == 0:
                            reachable = True
                    except Exception:
                        pass

                if not reachable:
                    self._safe_after(lambda: messagebox.showerror(
                        "Server Unreachable",
                        f"Could not reach server at {host}.\nMake sure the server is powered on and the IP/hostname is correct.",
                        parent=self
                    ))
                    return

                self._safe_after(lambda: messagebox.showinfo(
                    "Server Reachable",
                    f"The host {host} responded to a basic network probe.\n\n"
                    f"This does not verify the UDP tunnel on port {port}, credentials, or bonding. "
                    "Start Cloud Bonding to test the full connection.", parent=self
                ))
            finally:
                self._safe_after(lambda: self.btn_test.configure(text="Test Cloud Connection", state="normal"))

        threading.Thread(target=_do_test, daemon=True).start()

    def _sync_inputs_to_config(self) -> bool:
        """Validate and transfer current UI values into config data."""
        try:
            proxy_port = int(self.proxy_port_entry.get().strip())
            if proxy_port < 1 or proxy_port > 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation Error", "Proxy Port must be an integer between 1 and 65535.", parent=self)
            return False

        host = self.host_entry.get().strip()
        if host:
            host_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9.\-]{0,253}[a-zA-Z0-9]$|^\d{1,3}(\.\d{1,3}){3}$')
            if not host_pattern.match(host):
                messagebox.showerror("Validation Error", "Server hostname/IP format is invalid.", parent=self)
                return False

        try:
            port = int(self.port_entry.get().strip())
            if port < 1 or port > 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation Error", "Server Port must be an integer between 1 and 65535.", parent=self)
            return False

        auth_key = self.key_entry.get().strip()
        if auth_key:
            try:
                decoded = base64.b64decode(auth_key, validate=True)
                if len(decoded) < 16:
                    messagebox.showwarning("Weak Auth Key", "Auth key is shorter than 16 bytes.", parent=self)
            except Exception:
                messagebox.showerror("Validation Error", "Auth Key is not valid Base64.", parent=self)
                return False

        sched_val = "minrtt" if "minrtt" in self.scheduler_menu.get() else "wlb"
        dist_val = "weighted" if "Weighted" in self.dist_strategy_menu.get() else "round_robin"

        try:
            self.config.update({
                "proxy_port": proxy_port, "distribution_strategy": dist_val,
                "auto_system_proxy": self.auto_proxy_var.get(),
                "auto_connect_on_launch": self.auto_connect_var.get(),
                "server_host": host, "server_port": port, "auth_key": auth_key,
                "scheduler": sched_val, "insecure": self.insecure_var.get(),
            })
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("Save Failed", str(exc), parent=self)
            return False

    def _save_settings(self):
        if not self._sync_inputs_to_config():
            return

        if self.on_save_callback:
            self.on_save_callback()

        self.destroy()

    def _export_profile(self):
        if not self._sync_inputs_to_config():
            return

        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export Tandem Profile for Friends",
            defaultextension=".tandem",
            filetypes=[("Tandem Profile", "*.tandem"), ("TurboBond Legacy", "*.turbobond"), ("JSON Files", "*.json")]
        )
        if path:
            if self.config.export_profile(path):
                messagebox.showinfo("Export Success", "Profile exported as plain JSON, including your Auth Key. Share it only through a trusted channel.", parent=self)
            else:
                messagebox.showerror("Export Failed", "Could not write profile file.", parent=self)

    def _import_profile(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Import Tandem Profile",
            filetypes=[("Tandem Profile", "*.tandem"), ("TurboBond Legacy", "*.turbobond"), ("JSON Files", "*.json")]
        )
        if path:
            if self.config.import_profile(path):
                # Update Cloud Bonding fields
                self.host_entry.delete(0, "end")
                self.host_entry.insert(0, str(self.config.get("server_host", "")))
                self.port_entry.delete(0, "end")
                self.port_entry.insert(0, str(self.config.get("server_port", 443)))
                self.key_entry.delete(0, "end")
                self.key_entry.insert(0, str(self.config.get("auth_key", "")))

                sched = self.config.get("scheduler", "wlb")
                self.scheduler_menu.set("minrtt (Low Latency / Gaming)" if sched == "minrtt" else "wlb (Balanced Throughput)")
                self.insecure_var.set(bool(self.config.get("insecure", False)))

                # Update Local Dispatcher fields if present in imported profile
                if "proxy_port" in self.config.data:
                    self.proxy_port_entry.delete(0, "end")
                    self.proxy_port_entry.insert(0, str(self.config.get("proxy_port", 8080)))
                if "distribution_strategy" in self.config.data:
                    dist = self.config.get("distribution_strategy", "round_robin")
                    self.dist_strategy_menu.set("Weighted (Manual)" if dist == "weighted" else "Round-Robin (Balanced)")
                if "auto_system_proxy" in self.config.data:
                    self.auto_proxy_var.set(bool(self.config.get("auto_system_proxy", True)))

                messagebox.showinfo("Import Success", "Profile imported successfully!", parent=self)
            else:
                messagebox.showerror("Import Failed", "Failed to parse profile file.", parent=self)
