"""
Tandem - Vector Icon Asset Generator
Generates crisp, high-resolution, anti-aliased PNG vector icons with transparent
alpha channels for Apple macOS Sequoia Glassmorphic UI using Pillow.
"""

import os
import math
from PIL import Image, ImageDraw


def create_supersampled_image(size: int = 24, factor: int = 4):
    """Create a high-resolution canvas for supersampled drawing."""
    canvas_size = size * factor
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw, canvas_size, factor


def save_icon(img: Image.Image, filepath: str, size: int = 24):
    """Downsample with Lanczos filter for crisp anti-aliasing and save."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    res = img.resize((size, size), Image.Resampling.LANCZOS)
    res.save(filepath, "PNG")


def generate_refresh_icon(out_dir: str, color="#0F172A"):
    """Crisp circular dual-arrow refresh icon."""
    img, draw, S, F = create_supersampled_image(24, 4)
    # Circle arcs
    cx, cy = S / 2, S / 2
    r = S * 0.34
    stroke = int(2.4 * F)

    bbox = [cx - r, cy - r, cx + r, cy + r]
    # Arc 1: from -30 to 140 deg
    draw.arc(bbox, start=-30, end=140, fill=color, width=stroke)
    # Arc 2: from 150 to 320 deg
    draw.arc(bbox, start=150, end=320, fill=color, width=stroke)

    # Arrowhead 1 at ~140 deg (bottom left)
    angle1 = math.radians(140)
    ax1 = cx + r * math.cos(angle1)
    ay1 = cy + r * math.sin(angle1)
    arr_size = 4.0 * F
    p1 = [(ax1 - arr_size * 0.5, ay1 - arr_size), (ax1 + arr_size * 0.8, ay1 + arr_size * 0.2), (ax1 - arr_size * 1.0, ay1 + arr_size * 0.9)]
    draw.polygon(p1, fill=color)

    # Arrowhead 2 at ~320 deg (top right)
    angle2 = math.radians(320)
    ax2 = cx + r * math.cos(angle2)
    ay2 = cy + r * math.sin(angle2)
    p2 = [(ax2 + arr_size * 0.5, ay2 + arr_size), (ax2 - arr_size * 0.8, ay2 - arr_size * 0.2), (ax2 + arr_size * 1.0, ay2 - arr_size * 0.9)]
    draw.polygon(p2, fill=color)

    save_icon(img, os.path.join(out_dir, "refresh.png"))


def generate_settings_icon(out_dir: str, color="#0F172A"):
    """Precision Apple 6-tooth gear icon."""
    img, draw, S, F = create_supersampled_image(24, 4)
    cx, cy = S / 2, S / 2
    r_outer = S * 0.40
    r_inner = S * 0.30
    teeth = 6

    # Build gear tooth polygon
    points = []
    for i in range(teeth * 2):
        angle = i * (math.pi / teeth)
        r = r_outer if i % 2 == 0 else r_inner
        # Add two points per tooth for square teeth
        delta = math.pi / (teeth * 4)
        points.append((cx + r * math.cos(angle - delta), cy + r * math.sin(angle - delta)))
        points.append((cx + r * math.cos(angle + delta), cy + r * math.sin(angle + delta)))

    draw.polygon(points, fill=color)
    # Inner hole
    r_hole = S * 0.14
    draw.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=(0, 0, 0, 0))

    save_icon(img, os.path.join(out_dir, "settings.png"))


def generate_logs_icon(out_dir: str, color="#0F172A"):
    """Terminal / console sheet icon."""
    img, draw, S, F = create_supersampled_image(24, 4)
    stroke = int(2.2 * F)

    # Window / document outline
    margin = S * 0.16
    draw.rounded_rectangle([margin, margin, S - margin, S - margin], radius=int(3 * F), outline=color, width=stroke)

    # Prompt symbol >
    px = margin + S * 0.14
    py = margin + S * 0.22
    p_size = S * 0.14
    draw.line([(px, py), (px + p_size, py + p_size), (px, py + p_size * 2)], fill=color, width=stroke)

    # Cursor line _
    cx1 = px + p_size * 1.5
    cy1 = py + p_size * 2
    draw.line([(cx1, cy1), (cx1 + S * 0.22, cy1)], fill=color, width=stroke)

    save_icon(img, os.path.join(out_dir, "logs.png"))


def generate_wifi_icon(out_dir: str, color="#0071E3"):
    """Concentric Wi-Fi broadcast signal waves."""
    img, draw, S, F = create_supersampled_image(24, 4)
    cx = S / 2
    base_y = S * 0.78
    stroke = int(2.4 * F)

    # Base dot
    dot_r = 1.8 * F
    draw.ellipse([cx - dot_r, base_y - dot_r, cx + dot_r, base_y + dot_r], fill=color)

    # 3 Arcs
    radii = [S * 0.25, S * 0.44, S * 0.62]
    for r in radii:
        bbox = [cx - r, base_y - r, cx + r, base_y + r]
        draw.arc(bbox, start=225, end=315, fill=color, width=stroke)

    save_icon(img, os.path.join(out_dir, "wifi.png"))


def generate_cellular_icon(out_dir: str, color="#7C3AED"):
    """5G Cellular tower & signal waves."""
    img, draw, S, F = create_supersampled_image(24, 4)
    cx = S / 2
    base_y = S * 0.85
    top_y = S * 0.28
    stroke = int(2.2 * F)

    # Central antenna mast
    draw.line([(cx, top_y), (cx, base_y)], fill=color, width=stroke)
    # Triangular antenna base
    draw.polygon([(cx - S * 0.20, base_y), (cx, base_y - S * 0.18), (cx + S * 0.20, base_y)], outline=color, fill=(0, 0, 0, 0), width=stroke)
    # Top emitter dot
    dot_r = 2.4 * F
    draw.ellipse([cx - dot_r, top_y - dot_r, cx + dot_r, top_y + dot_r], fill=color)

    # Broadcast waves left and right
    wave_radii = [S * 0.22, S * 0.38]
    for r in wave_radii:
        bbox = [cx - r, top_y - r, cx + r, top_y + r]
        draw.arc(bbox, start=135, end=225, fill=color, width=stroke)
        draw.arc(bbox, start=315, end=405, fill=color, width=stroke)

    save_icon(img, os.path.join(out_dir, "cellular.png"))


def generate_ethernet_icon(out_dir: str, color="#16A34A"):
    """Precision RJ-45 modular Ethernet plug."""
    img, draw, S, F = create_supersampled_image(24, 4)
    stroke = int(2.2 * F)

    # Plug outer box
    left = S * 0.18
    right = S * 0.82
    top = S * 0.20
    bottom = S * 0.74

    # Main connector body
    draw.rounded_rectangle([left, top, right, bottom], radius=int(3 * F), outline=color, width=stroke)

    # Locking tab clip at bottom
    tab_w = S * 0.24
    draw.polygon([(S/2 - tab_w/2, bottom), (S/2 - tab_w/2, bottom + S * 0.14), (S/2 + tab_w/2, bottom + S * 0.14), (S/2 + tab_w/2, bottom)], fill=color)

    # Internal contact pins (3 vertical lines)
    pin_y1 = top + S * 0.12
    pin_y2 = top + S * 0.28
    for px in [S * 0.36, S * 0.50, S * 0.64]:
        draw.line([(px, pin_y1), (px, pin_y2)], fill=color, width=int(1.8 * F))

    save_icon(img, os.path.join(out_dir, "ethernet.png"))


def generate_bolt_icon(out_dir: str, color="#FFFFFF"):
    """Sharp lightning speed bolt icon."""
    img, draw, S, F = create_supersampled_image(24, 4)
    # Polygon for sharp lightning
    points = [
        (S * 0.55, S * 0.08),  # Top point
        (S * 0.22, S * 0.52),  # Mid left
        (S * 0.48, S * 0.52),  # Inner waist left
        (S * 0.38, S * 0.92),  # Bottom sharp tip
        (S * 0.78, S * 0.46),  # Mid right
        (S * 0.52, S * 0.46),  # Inner waist right
    ]
    draw.polygon(points, fill=color)

    save_icon(img, os.path.join(out_dir, "bolt.png"))


def generate_arrows(out_dir: str):
    """Download (green) and Upload (blue) arrow icons."""
    # Download
    img_down, draw_down, S, F = create_supersampled_image(20, 4)
    stroke = int(2.2 * F)
    cx = S / 2
    # Arrow down
    draw_down.line([(cx, S * 0.15), (cx, S * 0.80)], fill="#15803D", width=stroke)
    draw_down.line([(cx - S * 0.26, S * 0.55), (cx, S * 0.82), (cx + S * 0.26, S * 0.55)], fill="#15803D", width=stroke)
    save_icon(img_down, os.path.join(out_dir, "arrow_down.png"), 20)

    # Upload
    img_up, draw_up, S, F = create_supersampled_image(20, 4)
    # Arrow up
    draw_up.line([(cx, S * 0.85), (cx, S * 0.20)], fill="#075985", width=stroke)
    draw_up.line([(cx - S * 0.26, S * 0.45), (cx, S * 0.18), (cx + S * 0.26, S * 0.45)], fill="#075985", width=stroke)
    save_icon(img_up, os.path.join(out_dir, "arrow_up.png"), 20)


def generate_share_icons(out_dir: str):
    """Export and Import profile icons."""
    # Export (tray with arrow out)
    img_exp, draw_exp, S, F = create_supersampled_image(20, 4)
    stroke = int(2.0 * F)
    cx = S / 2
    # Tray
    draw_exp.line([(S * 0.20, S * 0.55), (S * 0.20, S * 0.82), (S * 0.80, S * 0.82), (S * 0.80, S * 0.55)], fill="#0F172A", width=stroke)
    # Arrow up
    draw_exp.line([(cx, S * 0.65), (cx, S * 0.20)], fill="#0F172A", width=stroke)
    draw_exp.line([(cx - S * 0.20, S * 0.38), (cx, S * 0.18), (cx + S * 0.20, S * 0.38)], fill="#0F172A", width=stroke)
    save_icon(img_exp, os.path.join(out_dir, "export.png"), 20)

    # Import (tray with arrow in)
    img_imp, draw_imp, S, F = create_supersampled_image(20, 4)
    draw_imp.line([(S * 0.20, S * 0.55), (S * 0.20, S * 0.82), (S * 0.80, S * 0.82), (S * 0.80, S * 0.55)], fill="#0F172A", width=stroke)
    # Arrow down
    draw_imp.line([(cx, S * 0.18), (cx, S * 0.62)], fill="#0F172A", width=stroke)
    draw_imp.line([(cx - S * 0.20, S * 0.42), (cx, S * 0.64), (cx + S * 0.20, S * 0.42)], fill="#0F172A", width=stroke)
    save_icon(img_imp, os.path.join(out_dir, "import.png"), 20)


def generate_pulse_icon(out_dir: str):
    """Luminous status indicator LED."""
    img, draw, S, F = create_supersampled_image(16, 4)
    cx, cy = S / 2, S / 2
    # Outer glow
    draw.ellipse([cx - S * 0.42, cy - S * 0.42, cx + S * 0.42, cy + S * 0.42], fill=(34, 197, 94, 60))
    # Core dot
    draw.ellipse([cx - S * 0.25, cy - S * 0.25, cx + S * 0.25, cy + S * 0.25], fill="#16A34A")
    save_icon(img, os.path.join(out_dir, "pulse.png"), 16)


def generate_disconnect_icon(out_dir: str, color="#FFFFFF"):
    """Apple-style clean disconnect/stop icon."""
    img, draw, S, F = create_supersampled_image(24, 4)
    cx, cy = S / 2, S / 2
    r = S * 0.32
    # Clean rounded square stop symbol
    draw.rounded_rectangle(
        [cx - r, cy - r, cx + r, cy + r],
        radius=int(3.5 * F),
        fill=color
    )
    save_icon(img, os.path.join(out_dir, "disconnect.png"), 24)


def generate_copy_icon(out_dir: str, color="#0F172A"):
    """Clean duplicate/copy document icon."""
    img, draw, S, F = create_supersampled_image(20, 4)
    stroke = int(1.8 * F)
    # Back sheet
    draw.rounded_rectangle(
        [S * 0.30, S * 0.15, S * 0.85, S * 0.70],
        radius=int(2.5 * F),
        outline=color,
        width=stroke
    )
    # Front sheet
    draw.rounded_rectangle(
        [S * 0.15, S * 0.30, S * 0.70, S * 0.85],
        radius=int(2.5 * F),
        fill="#FFFFFF",
        outline=color,
        width=stroke
    )
    save_icon(img, os.path.join(out_dir, "copy.png"), 20)


def generate_all_icons(base_dir: str):
    icons_dir = os.path.join(base_dir, "turbobond", "assets", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    generate_refresh_icon(icons_dir)
    generate_settings_icon(icons_dir)
    generate_logs_icon(icons_dir)
    generate_wifi_icon(icons_dir)
    generate_cellular_icon(icons_dir)
    generate_ethernet_icon(icons_dir)
    generate_bolt_icon(icons_dir)
    generate_arrows(icons_dir)
    generate_share_icons(icons_dir)
    generate_pulse_icon(icons_dir)
    generate_disconnect_icon(icons_dir)
    generate_copy_icon(icons_dir)
    print(f"[Assets] Generated precision vector icons in {icons_dir}")


if __name__ == "__main__":
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    generate_all_icons(project_root)
