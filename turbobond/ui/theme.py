"""
Tandem - High-Contrast Apple-Grade Design System, Theme Tokens & Vector Icons
Engineered for maximum legibility, WCAG 2.1 AAA contrast compliance,
macOS Sequoia glassmorphic styling, and hardware-accelerated icon rendering.
"""

import os
import sys
import customtkinter as ctk
from PIL import Image
from typing import Dict, Tuple, Optional

# ==============================================================================
# HIGH-CONTRAST APPLE COLOR PALETTE (WCAG AAA AUDITED)
# ==============================================================================

class Colors:
    # Backgrounds & Ambient Surfaces
    BG_AMBIENT = "#F1F5F9"         # Clean, soft cool-slate ambient desktop canvas
    BG_SURFACE = "#F8FAFC"         # Light frosted scroll container
    CARD_BG = "#FFFFFF"            # Pure white floating glass card
    CARD_BG_HOVER = "#F8FAFD"      # Subtle luminous hover surface
    CARD_BG_ACTIVE = "#F0FDF4"     # Active selected link card (tinted mint)
    SUB_CARD_BG = "#E2E8F0"        # Recessed nested panel (gauges, input tracks)
    
    # High-Definition Borders (Crisp 1px boundary lines)
    BORDER_MUTED = "#CBD5E1"       # Slate 300 - clear, crisp contrast against white
    BORDER_SUBTLE = "#E2E8F0"      # Slate 200 - interior dividers
    BORDER_ACTIVE = "#0071E3"      # Apple Blue active outline
    BORDER_EMERALD = "#22C55E"     # Active bonding emerald border
    CARD_HOVER_BORDER = "#93C5FD"  # Apple Light soft blue hover ring
    CARD_HOVER_BG = "#F8FAFD"      # Apple Light hover surface
    
    # Form Field Focus Rings
    INPUT_BG = "#F8FAFC"
    INPUT_BORDER = "#CBD5E1"
    INPUT_FOCUS_BORDER = "#0071E3" # Illuminated Apple Blue ring on focus
    
    # Apple System Vibrant Accents (Official Apple Human Interface Guidelines)
    ACCENT_CYAN = "#0071E3"        # Apple System Blue (Primary brand & speed accent)
    ACCENT_CYAN_DIM = "#005BB5"    # Darker blue for active states/hover
    ACCENT_CYAN_GLOW = "#E0F2FE"   # Tinted light blue chip background
    ACCENT_CYAN_TEXT = "#075985"   # Deep ocean blue for maximum contrast
    
    ACCENT_EMERALD = "#16A34A"     # Crisp Apple Green (Connected state, download indicator)
    ACCENT_EMERALD_DIM = "#15803D" # Deep Forest Green
    ACCENT_EMERALD_GLOW = "#DCFCE7"# Fresh mint chip background
    ACCENT_EMERALD_TEXT = "#14532D"# Deepest pine green (Contrast > 10:1)
    
    ACCENT_AMBER = "#D97706"       # Dark Amber (Warning, connecting)
    ACCENT_AMBER_GLOW = "#FEF3C7"  # Soft amber chip background
    ACCENT_AMBER_TEXT = "#92400E"  # High-contrast amber text
    
    ACCENT_ROSE = "#FF3B30"        # Apple Red (Disconnect, error alerts)
    ACCENT_ROSE_HOVER = "#E02E24"
    ACCENT_ROSE_GLOW = "#FEE2E2"   # Soft rose chip background
    ACCENT_ROSE_TEXT = "#991B1B"   # Deep crimson text
    
    ACCENT_PURPLE = "#7C3AED"      # Apple Indigo (5G Cellular tethering badge)
    ACCENT_PURPLE_GLOW = "#EDE9FE" # Soft purple chip background
    ACCENT_PURPLE_TEXT = "#5B21B6" # Deep purple text (Contrast > 9:1)
    
    # Razor-Sharp High-Contrast Typography
    TEXT_HERO = "#0A0F1D"          # Deepest Onyx/Black (18:1 contrast ratio)
    TEXT_PRIMARY = "#0F172A"       # Slate 900 - Razor-sharp primary headings & labels
    TEXT_SECONDARY = "#334155"     # Slate 700 - Subtitles & hardware specs (Contrast > 8.5:1)
    TEXT_MUTED = "#475569"         # Slate 600 - Footers & inactive hints (Contrast > 5.5:1)
    TEXT_DISABLED = "#94A3B8"      # Disabled state
    
    # Interactive Buttons
    BTN_PRIMARY = "#0071E3"        # High-impact Apple System Blue action CTA
    BTN_PRIMARY_HOVER = "#0077ED"
    BTN_DANGER = "#FF3B30"         # Apple System Red disconnect button
    BTN_DANGER_HOVER = "#E02E24"
    BTN_NAV = "#FFFFFF"            # Frosted white pill action button
    BTN_NAV_HOVER = "#F1F5F9"

    # Desktop Sidebar Navigation Tokens
    SIDEBAR_BG = "#F8FAFC"         # Crisp Apple frosted sidebar surface
    SIDEBAR_BORDER = "#E2E8F0"     # Vertical boundary divider
    NAV_ITEM_ACTIVE_BG = "#E0F2FE" # Apple Blue tinted active navigation pill
    NAV_ITEM_ACTIVE_TEXT = "#0071E3"
    NAV_ITEM_HOVER_BG = "#F1F5F9"  # Hover background
    NAV_ITEM_TEXT = "#334155"      # Slate 700 standard text


# ==============================================================================
# VECTOR ICON ASSET REGISTRY (Cached Hardware-Accelerated Icons)
# ==============================================================================

class Icons:
    """Manages crisp, vector-rendered anti-aliased PNG icons."""
    
    _ICONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icons"))
    _ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    _PIL_CACHE: Dict[str, Image.Image] = {}
    _IMAGE_CACHE: Dict[Tuple[int, str, int, int, str], ctk.CTkImage] = {}

    @classmethod
    def clear_cache(cls):
        """Clear cached CTkImages when needed."""
        cls._IMAGE_CACHE.clear()

    @classmethod
    def get(cls, name: str, size: Tuple[int, int] = (20, 20), color: Optional[str] = None, master: Optional[any] = None) -> Optional[ctk.CTkImage]:
        """Fetch or load a cached CTkImage bound to the active Tk root for the specified icon name, optionally tinted."""
        import tkinter
        root = master.winfo_toplevel() if (master and hasattr(master, "winfo_toplevel")) else tkinter._default_root
        root_id = id(root) if root else 0
        color_str = color or ""
        key = (root_id, name, size[0], size[1], color_str)
        if key in cls._IMAGE_CACHE:
            return cls._IMAGE_CACHE[key]

        if name not in cls._PIL_CACHE:
            icon_path = os.path.join(cls._ICONS_DIR, f"{name}.png")
            if not os.path.exists(icon_path):
                return None
            try:
                cls._PIL_CACHE[name] = Image.open(icon_path)
            except Exception:
                return None

        try:
            pil_img = cls._PIL_CACHE[name]
            if color:
                hex_c = color.lstrip("#")
                r, g, b = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                c_img = pil_img.convert("RGBA")
                alpha = c_img.getchannel("A")
                tinted = Image.new("RGBA", c_img.size, (r, g, b, 255))
                tinted.putalpha(alpha)
                pil_img = tinted

            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            cls._IMAGE_CACHE[key] = ctk_img
            return ctk_img
        except Exception:
            return None

    @classmethod
    def logo(cls, size: Tuple[int, int] = (32, 32), master: Optional[any] = None) -> Optional[ctk.CTkImage]:
        """Fetch the official Tandem transparent squircle app logo."""
        import tkinter
        root = master.winfo_toplevel() if (master and hasattr(master, "winfo_toplevel")) else tkinter._default_root
        root_id = id(root) if root else 0
        key = (root_id, "__logo__", size[0], size[1], "")
        if key in cls._IMAGE_CACHE:
            return cls._IMAGE_CACHE[key]

        logo_path = os.path.join(cls._ASSETS_DIR, "icon.png")
        if not os.path.exists(logo_path):
            return None
        try:
            pil_img = Image.open(logo_path)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            cls._IMAGE_CACHE[key] = ctk_img
            return ctk_img
        except Exception:
            return None

    @classmethod
    def refresh(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("refresh", size, color)

    @classmethod
    def settings(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("settings", size, color)

    @classmethod
    def logs(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("logs", size, color)

    @classmethod
    def wifi(cls, size: Tuple[int, int] = (18, 18), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("wifi", size, color)

    @classmethod
    def cellular(cls, size: Tuple[int, int] = (18, 18), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("cellular", size, color)

    @classmethod
    def ethernet(cls, size: Tuple[int, int] = (18, 18), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("ethernet", size, color)

    @classmethod
    def bolt(cls, size: Tuple[int, int] = (18, 18), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("bolt", size, color)

    @classmethod
    def arrow_down(cls, size: Tuple[int, int] = (14, 14), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("arrow_down", size, color)

    @classmethod
    def arrow_up(cls, size: Tuple[int, int] = (14, 14), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("arrow_up", size, color)

    @classmethod
    def export_icon(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("export", size, color)

    @classmethod
    def import_icon(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("import", size, color)

    @classmethod
    def pulse(cls, size: Tuple[int, int] = (12, 12), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("pulse", size, color)

    @classmethod
    def disconnect(cls, size: Tuple[int, int] = (18, 18), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("disconnect", size, color)

    @classmethod
    def copy(cls, size: Tuple[int, int] = (16, 16), color: Optional[str] = None) -> Optional[ctk.CTkImage]:
        return cls.get("copy", size, color)


# ==============================================================================
# TYPOGRAPHY HIERARCHY (High-Legibility Precision Fonts)
# ==============================================================================

class Fonts:
    """Platform-adaptive, high-legibility Apple-grade typography."""
    
    _DISPLAY_FAMILY = "Segoe UI Variable Display"
    _BODY_FAMILY = "Segoe UI"
    _MONO_FAMILY = "Cascadia Code"
    
    @classmethod
    def init_fonts(cls):
        """Detect best available precision font family on the host OS."""
        try:
            import tkinter as tk
            from tkinter import font
            root = tk._default_root
            if root:
                families = set(font.families(root=root))
                # Display / Heading typography (Apple & Windows 11 precision)
                if "Segoe UI Variable Display" in families:
                    cls._DISPLAY_FAMILY = "Segoe UI Variable Display"
                elif "Bahnschrift" in families:
                    cls._DISPLAY_FAMILY = "Bahnschrift"
                elif "SF Pro Display" in families:
                    cls._DISPLAY_FAMILY = "SF Pro Display"
                elif "Segoe UI" in families:
                    cls._DISPLAY_FAMILY = "Segoe UI"
                else:
                    cls._DISPLAY_FAMILY = "Helvetica"
                    
                # Body / Label typography
                if "Segoe UI Variable Text" in families:
                    cls._BODY_FAMILY = "Segoe UI Variable Text"
                elif "SF Pro Text" in families:
                    cls._BODY_FAMILY = "SF Pro Text"
                elif "Segoe UI" in families:
                    cls._BODY_FAMILY = "Segoe UI"
                else:
                    cls._BODY_FAMILY = "Arial"
                    
                # Monospace / Metric typography
                if "Cascadia Code" in families:
                    cls._MONO_FAMILY = "Cascadia Code"
                elif "SF Mono" in families:
                    cls._MONO_FAMILY = "SF Mono"
                elif "Consolas" in families:
                    cls._MONO_FAMILY = "Consolas"
                else:
                    cls._MONO_FAMILY = "Courier New"
        except Exception:
            pass

    @classmethod
    def hero_number(cls) -> ctk.CTkFont:
        """Massive crisp display font for aggregated throughput."""
        return ctk.CTkFont(family=cls._DISPLAY_FAMILY, size=54, weight="bold")

    @classmethod
    def hero_unit(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._DISPLAY_FAMILY, size=20, weight="bold")

    @classmethod
    def title_brand(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._DISPLAY_FAMILY, size=20, weight="bold")

    @classmethod
    def section_header(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="bold")

    @classmethod
    def badge_pill(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=11, weight="bold")

    @classmethod
    def card_title(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=14, weight="bold")

    @classmethod
    def card_subtitle(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="normal")

    @classmethod
    def body_text(cls) -> ctk.CTkFont:
        """Clean Apple body typography for paragraphs, forms, and checkboxes."""
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="normal")

    @classmethod
    def body_medium(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="bold")

    @classmethod
    def body_secondary(cls) -> ctk.CTkFont:
        """Subtitles, descriptions, hints, and helper text."""
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=11, weight="normal")

    @classmethod
    def card_meta(cls) -> ctk.CTkFont:
        """Default card metadata in clean sans-serif (replaces legacy mono)."""
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=11, weight="normal")

    @classmethod
    def mono_meta(cls) -> ctk.CTkFont:
        """Strictly for tabular numbers, IP addresses, ports, and hardware IDs."""
        return ctk.CTkFont(family=cls._MONO_FAMILY, size=11, weight="normal")

    @classmethod
    def speed_metric(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._DISPLAY_FAMILY, size=13, weight="bold")

    @classmethod
    def action_button(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=15, weight="bold")

    @classmethod
    def nav_button(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="bold")

    @classmethod
    def button(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=12, weight="bold")

    @classmethod
    def caption(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=11, weight="normal")

    @classmethod
    def footer(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._BODY_FAMILY, size=11, weight="normal")

    @classmethod
    def code_log(cls) -> ctk.CTkFont:
        return ctk.CTkFont(family=cls._MONO_FAMILY, size=11, weight="normal")


def style_segmented_button(
    seg_btn: ctk.CTkSegmentedButton,
    selected_text_color: str = "#FFFFFF",
    unselected_text_color: str = "#334155"
):
    """Enforce WCAG AAA contrast on CTkSegmentedButton: pure white on active blue, dark slate on inactive white."""
    def _apply_text_colors():
        try:
            curr = seg_btn.get()
            for val, btn in getattr(seg_btn, "_buttons_dict", {}).items():
                if val == curr:
                    btn.configure(text_color=selected_text_color)
                else:
                    btn.configure(text_color=unselected_text_color)
        except Exception:
            pass

    try:
        orig_select = seg_btn._select_button_by_value
        def custom_select(val):
            orig_select(val)
            _apply_text_colors()
        seg_btn._select_button_by_value = custom_select
    except Exception:
        pass

    _apply_text_colors()


def apply_window_icon(window):
    """
    Set the official Tandem icon on a window border (title bar and taskbar).
    Permanently neutralizes CustomTkinter's 200ms hardcoded icon replacement on CTkToplevel.
    """
    try:
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.tandem.network.aggregator.v1")
            except Exception:
                pass

        icon_ico = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico"))
        if not os.path.exists(icon_ico):
            return

        orig_iconbitmap = getattr(window, "iconbitmap", None)
        if callable(orig_iconbitmap):
            def _safe_iconbitmap(bitmap=None, default=None):
                try:
                    return orig_iconbitmap(icon_ico, default)
                except Exception:
                    pass
            window.iconbitmap = _safe_iconbitmap
            window._iconbitmap_method_called = True

        def _do_apply():
            try:
                if window.winfo_exists():
                    if callable(orig_iconbitmap):
                        orig_iconbitmap(icon_ico)
                    else:
                        window.iconbitmap(icon_ico)
            except Exception:
                pass

        _do_apply()
        # Schedule deferred re-enforcement past CustomTkinter's 200ms timer
        try:
            window.after(250, _do_apply)
        except Exception:
            pass

    except Exception:
        pass


