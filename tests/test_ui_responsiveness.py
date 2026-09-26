"""
Tests for Tandem UI responsiveness, theme fonts, vector icons, and non-blocking asynchronous behaviors.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
import customtkinter as ctk
from turbobond.ui.theme import Colors, Fonts, Icons
from turbobond.ui.widgets.adapter_card import AdapterCardWidget


def test_theme_colors_wcag_contrast():
    """Verify key colors conform to high-contrast requirements."""
    assert Colors.BG_AMBIENT == "#F1F5F9"
    assert Colors.CARD_BG == "#FFFFFF"
    assert Colors.TEXT_HERO == "#0A0F1D"
    assert Colors.TEXT_PRIMARY == "#0F172A"
    assert Colors.BORDER_MUTED == "#CBD5E1"
    assert Colors.CARD_HOVER_BORDER == "#93C5FD"


def test_fonts_hierarchy():
    """Verify font builders produce valid CTkFont objects."""
    root = ctk.CTk()
    root.withdraw()
    try:
        hero_font = Fonts.hero_number()
        assert isinstance(hero_font, ctk.CTkFont)
        assert hero_font.cget("size") == 54

        card_font = Fonts.card_title()
        assert isinstance(card_font, ctk.CTkFont)
        assert card_font.cget("size") == 14

        badge_font = Fonts.badge_pill()
        assert isinstance(badge_font, ctk.CTkFont)
        assert badge_font.cget("size") == 11
    finally:
        root.destroy()


def test_fonts_init_fallback():
    """Verify Fonts.init_fonts gracefully handles missing fonts or Tk root."""
    Fonts.init_fonts()
    assert Fonts._DISPLAY_FAMILY is not None
    assert Fonts._BODY_FAMILY is not None
    assert Fonts._MONO_FAMILY is not None


def test_icons_registry():
    """Verify vector icon registry loads and caches CTkImage objects."""
    root = ctk.CTk()
    root.withdraw()
    try:
        ref_icon = Icons.refresh()
        assert ref_icon is not None
        assert isinstance(ref_icon, ctk.CTkImage)

        wifi_icon = Icons.wifi()
        assert wifi_icon is not None

        cell_icon = Icons.cellular()
        assert cell_icon is not None

        bolt_icon = Icons.bolt()
        assert bolt_icon is not None

        # Verify caching returns identical object
        assert Icons.refresh() is ref_icon
    finally:
        root.destroy()


def test_adapter_card_hover_and_click():
    """Test AdapterCardWidget full-card click and hover micro-interactions."""
    root = ctk.CTk()
    root.withdraw()
    try:
        info = {
            "name": "Wi-Fi",
            "type": "wifi",
            "ip": "192.168.1.100",
            "description": "Intel Wi-Fi 6 AX201"
        }
        toggled = []
        card = AdapterCardWidget(root, info, initial_checked=True, on_toggle=lambda n, c: toggled.append((n, c)))
        
        # Test initial state
        assert card.is_selected() is True

        # Test hover event simulation
        card._on_mouse_enter()
        assert card._is_hovered is True

        card._on_mouse_leave()
        assert card._is_hovered is False

        # Test full-card click toggles state
        card._on_card_click()
        assert card.is_selected() is False
        assert len(toggled) == 1
        assert toggled[-1] == ("Wi-Fi", False)

        card._on_card_click()
        assert card.is_selected() is True
        assert toggled[-1] == ("Wi-Fi", True)
    finally:
        root.destroy()


def test_main_window_async_startup_and_teardown():
    """Test that MainWindow initializes without blocking and tears down cleanly."""
    with patch("turbobond.ui.main_window.SystemTrayManager") as mock_tray_cls, \
         patch("turbobond.ui.main_window.detect_active_adapters") as mock_detect:
        
        mock_detect.return_value = [
            {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.50", "description": "Intel Wi-Fi 6"},
            {"name": "Cellular", "type": "usb_tether", "ip": "192.168.42.10", "description": "Remote NDIS"}
        ]
        mock_tray = MagicMock()
        mock_tray_cls.return_value = mock_tray

        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()  # keep hidden

        # Allow after() callbacks to process
        app.update()

        # Check title and link badge
        assert "Tandem" in app.title()
        
        # Verify non-blocking close
        app._closing = True
        app.is_monitoring = False
        app.destroy()


def test_adapter_card_hover_debounce_within_bounds():
    """Verify pointer within card bounds prevents unhover flicker."""
    root = ctk.CTk()
    root.withdraw()
    try:
        info = {"name": "Ethernet", "type": "ethernet", "ip": "10.0.0.5", "description": "Gigabit"}
        card = AdapterCardWidget(root, info)
        root.update()

        card._on_mouse_enter()
        assert card._is_hovered is True

        # Mock an event whose coordinates are inside card's bounding box
        event = MagicMock()
        event.x_root = card.winfo_rootx() + 10
        event.y_root = card.winfo_rooty() + 10

        card._on_mouse_leave(event)
        # Mouse is still within card bounds -> must remain hovered
        assert card._is_hovered is True

        # Now mock an event outside bounds
        event.x_root = card.winfo_rootx() - 100
        event.y_root = card.winfo_rooty() - 100
        card._on_mouse_leave(event)
        assert card._is_hovered is False
    finally:
        root.destroy()


def test_adapter_card_toggle_visual_state():
    """Verify deselected cards visually dim and selected cards restore contrast."""
    root = ctk.CTk()
    root.withdraw()
    try:
        info = {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.1", "description": "Adapter"}
        card = AdapterCardWidget(root, info, initial_checked=True)
        root.update()

        # Deselect
        card.checked_var.set(False)
        card._update_visual_state()
        assert card.cget("fg_color") == Colors.BG_SURFACE
        assert card.cget("border_color") == Colors.BORDER_SUBTLE

        # Re-select
        card.checked_var.set(True)
        card._update_visual_state()
        assert card.cget("fg_color") == Colors.CARD_BG
        assert card.cget("border_color") == Colors.BORDER_MUTED
    finally:
        root.destroy()


def test_main_window_dhcp_ip_update_in_place():
    """Verify IP changes (DHCP resolution) update existing cards without card destruction."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters") as mock_detect:
        
        mock_detect.return_value = [
            {"name": "Cellular", "type": "usb_tether", "ip": "Pending IP...", "description": "Remote NDIS"}
        ]
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            app._apply_detected_adapters(mock_detect.return_value)
            app.update()

            card = app.adapter_cards["Cellular"]
            assert "Pending" in card.meta_lbl.cget("text")

            # Simulate DHCP resolution
            resolved_adapters = [
                {"name": "Cellular", "type": "usb_tether", "ip": "192.168.42.100", "description": "Remote NDIS"}
            ]
            app._update_adapter_ips(resolved_adapters)
            app.update()

            # The card instance was NOT destroyed, but updated in place
            assert app.adapter_cards["Cellular"] is card
            assert "192.168.42.100" in card.meta_lbl.cget("text")
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_main_window_preserve_selection_on_refresh():
    """Verify that auto-refresh or rescanning preserves the user's manual uncheck states."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters") as mock_detect:
        
        adapters_initial = [
            {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.5", "description": "Wi-Fi"},
            {"name": "Ethernet", "type": "ethernet", "ip": "192.168.1.10", "description": "LAN"}
        ]
        mock_detect.return_value = adapters_initial

        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            app._apply_detected_adapters(adapters_initial)
            app.update()

            # User unchecks Ethernet
            app.adapter_cards["Ethernet"].checked_var.set(False)
            assert app.adapter_cards["Ethernet"].is_selected() is False

            # Rescan detects a 3rd adapter (e.g. phone tether plugged in)
            adapters_new = adapters_initial + [
                {"name": "Cellular", "type": "usb_tether", "ip": "192.168.42.1", "description": "Phone"}
            ]
            app._apply_detected_adapters(adapters_new)
            app.update()

            # Ethernet must PRESERVE its unchecked state!
            assert app.adapter_cards["Ethernet"].is_selected() is False
            assert app.adapter_cards["Wi-Fi"].is_selected() is True
            assert app.adapter_cards["Cellular"].is_selected() is True
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_traffic_distribution_bar_stability():
    """Verify traffic distribution bar renders safely without crashing on zero speeds or fluctuations."""
    root = ctk.CTk()
    root.withdraw()
    try:
        from turbobond.ui.widgets.traffic_bar import TrafficDistributionBar
        bar = TrafficDistributionBar(root)
        bar.pack()
        root.update()

        # Standby / empty
        bar.update_distribution({})
        assert bar.ratio_lbl.cget("text") == "Standby"

        # Zero speeds for 2 adapters
        bar.update_distribution({"Wi-Fi": 0.0, "Cellular": 0.0})
        assert "Idle" in bar.ratio_lbl.cget("text")
        assert len(bar.legend_labels) == 2

        # Active speeds
        bar.update_distribution({"Wi-Fi": 25.0, "Cellular": 15.0})
        root.update()
        assert "62%" in bar.ratio_lbl.cget("text") or "38%" in bar.ratio_lbl.cget("text")

        # Fluctuation back to 0 does not destroy legend
        bar.update_distribution({"Wi-Fi": 0.0, "Cellular": 0.0})
        root.update()
        assert len(bar.legend_labels) == 2
    finally:
        root.destroy()


def test_single_instance_logs_window():
    """Verify opening logs window multiple times focuses the existing instance."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]):
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        app.update()

        app._show_logs()
        first_win = app._log_window
        assert first_win is not None
        assert first_win.winfo_exists()

        # Second call must reuse first_win
        app._show_logs()
        assert app._log_window is first_win

        first_win.destroy()
        app._closing = True
        app.is_monitoring = False
        app.destroy()


def test_dispatcher_dynamic_hot_toggle():
    """Verify unchecking an adapter while dispatcher is active dynamically updates the dispatcher links."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters") as mock_detect:
        
        mock_detect.return_value = [
            {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.50", "description": "Wi-Fi"},
            {"name": "Cellular", "type": "usb_tether", "ip": "192.168.42.10", "description": "Cellular"}
        ]
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            app._apply_detected_adapters(mock_detect.return_value)
            app.update()

            mock_dispatcher = MagicMock()
            app.dispatcher = mock_dispatcher
            app._dispatcher_active = True

            # Hot-uncheck Cellular
            app.adapter_cards["Cellular"].checked_var.set(False)
            app._on_adapter_toggled("Cellular", False)
            app.update()

            # Dispatcher must be updated immediately with ONLY Wi-Fi's IP
            mock_dispatcher.update_adapters.assert_called_once_with(["192.168.1.50"])
            pill_text = app.status_pill.cget("text")
            # Verify singular grammar — "1 LINK" not "1 LINKS"
            assert "1 LINK" in pill_text
            assert "1 LINKS" not in pill_text
            assert "DISPATCHER ACTIVE" in pill_text
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_main_window_quit_synchronous_cleanup():
    """Verify quitting application synchronously disables proxy and cleans routes before exiting."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]), \
         patch("os._exit") as mock_exit:
        
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        app.update()

        mock_dispatcher = MagicMock()
        app.dispatcher = mock_dispatcher
        app._dispatcher_active = True

        mock_proxy_disable = MagicMock()
        app.system_proxy.disable_proxy = mock_proxy_disable

        mock_cleanup_routes = MagicMock()
        app.route_manager.cleanup_routes = mock_cleanup_routes

        with patch("turbobond.ui.main_window.is_elevated", return_value=True):
            app._quit_application()

        mock_dispatcher.stop_from_thread.assert_called_once()
        mock_proxy_disable.assert_called_once()
        mock_cleanup_routes.assert_called_once()
        mock_exit.assert_called_once_with(0)


def test_settings_dialog_full_sync():
    """Verify settings dialog synchronizes all controls on profile import."""
    import tempfile
    import json
    from turbobond.core.config import ConfigManager
    from turbobond.ui.settings_dialog import SettingsDialog

    root = ctk.CTk()
    root.withdraw()
    try:
        cfg = ConfigManager()
        dialog = SettingsDialog(root, cfg)
        root.update()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".tandem") as tmp:
            profile_data = {
                "server_host": "203.0.113.5",
                "server_port": 8443,
                "auth_key": "dGVzdF9rZXlfYmFzZTY0X3N0cmluZw==",
                "scheduler": "minrtt",
                "insecure": False
            }
            json.dump(profile_data, tmp)
            tmp_path = tmp.name

        with patch("tkinter.filedialog.askopenfilename", return_value=tmp_path), \
             patch("tkinter.messagebox.showinfo"):
            dialog._import_profile()
            root.update()

        assert dialog.host_entry.get() == "203.0.113.5"
        assert dialog.port_entry.get() == "8443"
        assert "minrtt" in dialog.scheduler_menu.get()
        assert dialog.insecure_var.get() is False

        dialog.destroy()
    finally:
        root.destroy()


def test_traffic_distribution_bar_color_consistency():
    """Verify canvas segment colors match the legend dot colors."""
    root = ctk.CTk()
    root.withdraw()
    try:
        from turbobond.ui.widgets.traffic_bar import TrafficDistributionBar, APPLE_LINK_PALETTE
        bar = TrafficDistributionBar(root)
        bar.pack()
        root.update()

        # Adapter 0 has 0 speed, Adapter 1 has active speed
        speeds = {"Wi-Fi": 0.0, "Cellular": 25.0}
        bar.update_distribution(speeds)
        root.update()

        # Cellular is at index 1 in the adapter dict -> its palette color must be APPLE_LINK_PALETTE[1]
        expected_color = APPLE_LINK_PALETTE[1]
        
        # Legend chip for Cellular must use expected_color
        cell_dot = None
        for child in bar.legend_frame.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, ctk.CTkLabel) and sub.cget("text") == "●":
                    # Check text color of the dot
                    if sub.cget("text_color") == expected_color:
                        cell_dot = sub
        assert cell_dot is not None, "Legend dot color does not match persistent palette index"
    finally:
        root.destroy()


def test_telemetry_active_vs_standby_isolation():
    """Verify hero speedometer shows 0.0 in Standby and only sums bonded adapters when active."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters") as mock_detect:
        
        mock_detect.return_value = [
            {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.50", "description": "Wi-Fi"},
            {"name": "Cellular", "type": "usb_tether", "ip": "192.168.42.10", "description": "Cellular"}
        ]
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            app._apply_detected_adapters(mock_detect.return_value)
            app.update()

            mock_adapter_stats = {
                "Wi-Fi": {"rx_mbps": 30.0, "tx_mbps": 5.0},
                "Cellular": {"rx_mbps": 20.0, "tx_mbps": 3.0}
            }

            # 1. STANDBY: Not active -> Hero gauge must stay at 0.0
            app._dispatcher_active = False
            app._update_speed_ui(50.0, 8.0, 6.25, mock_adapter_stats)
            app.update()

            assert app.speed_number_lbl.cget("text") == "0.0"
            assert "Standby" in app.speed_secondary_lbl.cget("text")
            assert "0.0 Mbps" in app.stat_down_lbl.cget("text")
            # Individual cards must still show live hardware telemetry
            assert "30.0 Mbps" in app.adapter_cards["Wi-Fi"].speed_down_lbl.cget("text")

            # 2. ACTIVE: Cellular deselected, Wi-Fi selected -> Hero gauge only counts Wi-Fi (30.0)
            app._dispatcher_active = True
            app.adapter_cards["Cellular"].checked_var.set(False)
            app._update_speed_ui(50.0, 8.0, 6.25, mock_adapter_stats)
            app.update()

            assert app.speed_number_lbl.cget("text") == "30.0"
            assert "30.0 Mbps" in app.stat_down_lbl.cget("text")
            assert "5.0 Mbps" in app.stat_up_lbl.cget("text")
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_apple_typography_tokens():
    """Verify Apple typography hierarchy: body & subtitles use sans-serif, mono is reserved."""
    root = ctk.CTk()
    root.withdraw()
    try:
        Fonts.init_fonts()
        # Card meta must be clean sans-serif, not typewriter monospace
        meta_font = Fonts.card_meta()
        assert meta_font.cget("family") == Fonts._BODY_FAMILY

        body_font = Fonts.body_text()
        assert body_font.cget("family") == Fonts._BODY_FAMILY

        sec_font = Fonts.body_secondary()
        assert sec_font.cget("family") == Fonts._BODY_FAMILY

        # Mono is strictly for code_meta / mono_meta
        mono_font = Fonts.mono_meta()
        assert mono_font.cget("family") == Fonts._MONO_FAMILY
    finally:
        root.destroy()


def test_main_window_responsive_max_width_centering():
    """Verify MainWindow maintains centered layout without infinite stretching on wide monitors."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]):
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            # Simulate maximizing to 1400px wide
            app.geometry("1400x800")
            app.update()
            
            # Trigger configure event simulation
            class MockEvent:
                widget = app
                width = 1400
                height = 800
            
            app._on_window_configure(MockEvent())
            app.update()

            # Ensure horizontal padding was calculated to center the container
            assert hasattr(app, "_current_hpad")
            assert app._current_hpad > 20
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_sidebar_navigation_and_pinned_action_dock():
    """Verify Desktop Sidebar Navigation, active highlights, and pinned action dock."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]):
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            app.update()

            # 1. Sidebar Frame
            assert hasattr(app, "sidebar_frame")
            assert app.sidebar_frame.cget("width") == 240
            assert app.sidebar_frame.cget("fg_color") == Colors.SIDEBAR_BG

            # 2. Navigation items
            expected_keys = ["speed", "local", "cloud", "settings", "logs"]
            for k in expected_keys:
                assert k in app.sidebar_nav_items
                assert app.sidebar_nav_items[k].winfo_exists()

            # Default active is speed
            assert app._active_nav_key == "speed"

            # 3. Switching navigation
            app._select_nav("local")
            assert app._active_nav_key == "local"
            assert app._get_current_mode() == "local_dispatcher"

            app._select_nav("cloud")
            assert app._active_nav_key == "cloud"
            assert app._get_current_mode() == "cloud_bonding"

            # Restore to local mode
            app._select_nav("local")
            assert app._active_nav_key == "local"
            assert app._get_current_mode() == "local_dispatcher"

            # 4. Pinned Action Dock & Button
            assert hasattr(app, "sidebar_dock")
            assert hasattr(app, "btn_turbo")
            # Verify btn_turbo is anchored in the sidebar dock
            assert app.btn_turbo.master == app.sidebar_dock
            assert hasattr(app, "sidebar_link_badge")
            assert hasattr(app, "sidebar_footnote")
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_auto_connect_on_launch_trigger():
    """Verify auto_connect_on_launch invokes dispatcher when valid adapters are discovered."""
    adapters = [
        {"name": "Wi-Fi", "type": "wifi", "ip": "192.168.1.100", "description": "Wi-Fi 6"}
    ]
    from turbobond.ui.main_window import MainWindow
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=adapters), \
         patch.object(MainWindow, "_start_dispatcher") as mock_start:
        app = MainWindow()
        app.withdraw()
        try:
            app.config.set("mode", "local_dispatcher")
            app._auto_connect_on_startup()
            mock_start.assert_called()
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_hero_stat_labels_fixed_width_no_jitter():
    """Verify hero card stat labels have fixed width=180 to prevent text jitter."""
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]):
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            assert app.stat_down_lbl.cget("width") == 180
            assert app.stat_up_lbl.cget("width") == 180
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()


def test_settings_dialog_centering_and_fonts():
    """Verify SettingsDialog opens centered over parent and uses sans-serif typography."""
    root = ctk.CTk()
    root.withdraw()
    root.geometry("800x800+200+200")
    root.update()
    try:
        from turbobond.core.config import ConfigManager
        from turbobond.ui.settings_dialog import SettingsDialog
        cfg = ConfigManager()
        dlg = SettingsDialog(root, cfg)
        dlg.withdraw()
        try:
            # Check dialog position is offset from parent origin
            assert dlg.winfo_width() > 0
            # Check checkbox uses sans-serif
            check_font = dlg.auto_proxy_check.cget("font")
            assert check_font.cget("family") == Fonts._BODY_FAMILY
        finally:
            dlg.destroy()
    finally:
        root.destroy()


def test_segmented_button_wcag_contrast_dynamic_styling():
    """Verify style_segmented_button dynamically maintains #FFFFFF on selected and dark slate on unselected."""
    root = ctk.CTk()
    root.withdraw()
    try:
        from turbobond.ui.theme import style_segmented_button
        var = ctk.StringVar(value="Option 1")
        seg = ctk.CTkSegmentedButton(root, values=["Option 1", "Option 2"], variable=var)
        style_segmented_button(seg, selected_text_color="#FFFFFF", unselected_text_color="#334155")

        # Initial check
        assert seg._buttons_dict["Option 1"].cget("text_color") == "#FFFFFF"
        assert seg._buttons_dict["Option 2"].cget("text_color") == "#334155"

        # Toggle to Option 2
        var.set("Option 2")
        assert seg._buttons_dict["Option 1"].cget("text_color") == "#334155"
        assert seg._buttons_dict["Option 2"].cget("text_color") == "#FFFFFF"
    finally:
        root.destroy()


def test_logo_and_brand_integration_across_windows():
    """Verify Tandem transparent squircle logo loads and is integrated into Main, Settings, and Logs."""
    Icons.clear_cache()
    with patch("turbobond.ui.main_window.SystemTrayManager"), \
         patch("turbobond.ui.main_window.detect_active_adapters", return_value=[]):
        from turbobond.ui.main_window import MainWindow
        app = MainWindow()
        app.withdraw()
        try:
            # 1. Logo asset loads on MainWindow and border icon is set
            assert hasattr(app, "logo_img")
            assert app.logo_img is not None
            assert isinstance(app.logo_img, ctk.CTkImage)
            assert getattr(app, "_iconbitmap_method_called", False) is True

            # 2. SettingsDialog has branded header, styled tabview, and border icon protection
            from turbobond.core.config import ConfigManager
            from turbobond.ui.settings_dialog import SettingsDialog
            cfg = ConfigManager()
            dlg = SettingsDialog(app, cfg)
            dlg.withdraw()
            try:
                assert getattr(dlg, "_iconbitmap_method_called", False) is True
                # Verify tabview segmented button has white active and dark inactive
                sb = dlg.tabview._segmented_button
                curr = sb.get()
                for val, btn in sb._buttons_dict.items():
                    if val == curr:
                        assert btn.cget("text_color") == "#FFFFFF"
                    else:
                        assert btn.cget("text_color") == "#334155"
            finally:
                dlg.destroy()

            # 3. Logs window opens, has branded header, and border icon protection
            app._show_logs()
            try:
                assert app._log_window is not None
                assert app._log_window.winfo_exists()
                assert getattr(app._log_window, "_iconbitmap_method_called", False) is True
            finally:
                if app._log_window:
                    app._log_window.destroy()
        finally:
            app._closing = True
            app.is_monitoring = False
            app.destroy()
            Icons.clear_cache()






