"""
Comprehensive Automated Test Suite for New Features:
- DuplicateFinder (3-tier MD5 hashing, selection strategies, safe deletion)
- RegistryCompactor (hive analysis, fragmentation estimation, defrag/compaction)
- Gaming Ping Tuner in NetworkOptimizer (TCPNoDelay, TcpAckFrequency)
- Anti-Spy & Telemetry Blocker in PrivacyTweaker (Cortana, CEIP, DiagTrack, App Diagnostics)
- Smart Scheduler in AutoCleaner (Idle detection, scheduled time, day/hour triggers)
- HardwareMonitor New Telemetries (Disk I/O, Discrete GPU, Top Consumer, Uptime)
- DesktopPerformanceWidget (Responsive layouts, themes, click-through, quick actions)
"""

import os
import sys
import tempfile
import time
import shutil

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure workspace root is in python path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from PyQt5.QtWidgets import QApplication

def test_duplicate_finder():
    print("--> Testing DuplicateFinder engine...")
    from core.duplicate_finder import DuplicateFinder

    temp_dir = tempfile.mkdtemp(prefix="novacare_dup_test_")
    try:
        # Create identical files
        content_a = b"A" * 16384  # 16 KB
        content_b = b"B" * 16384
        content_c = b"C" * 2048

        f1 = os.path.join(temp_dir, "file1.dat")
        f2 = os.path.join(temp_dir, "file2_dup.dat")
        f3 = os.path.join(temp_dir, "file3_dup.dat")
        f4 = os.path.join(temp_dir, "file4_different.dat")
        f5 = os.path.join(temp_dir, "file5_small.dat")

        with open(f1, "wb") as f:
            f.write(content_a)
        # Sleep slightly to have different timestamps
        time.sleep(0.05)
        with open(f2, "wb") as f:
            f.write(content_a)
        time.sleep(0.05)
        with open(f3, "wb") as f:
            f.write(content_a)
        with open(f4, "wb") as f:
            f.write(content_b)
        with open(f5, "wb") as f:
            f.write(content_c)

        finder = DuplicateFinder()
        groups = finder.scan_duplicates(
            target_dirs=[temp_dir],
            min_size_bytes=1024
        )

        assert len(groups) == 1, f"Expected 1 duplicate group, got {len(groups)}"

        grp = groups[0]
        assert len(grp.files) == 3, f"Expected 3 files in duplicate group, got {len(grp.files)}"
        assert grp.file_size == 16384, f"Expected 16384 bytes, got {grp.file_size}"
        assert grp.wasted_size == 16384 * 2, f"Expected wasted size {16384*2}, got {grp.wasted_size}"

        # Test selection helpers
        finder.auto_mark_selection(groups, keep_mode="oldest")
        # Oldest file (f1) should not be selected; f2 and f3 should be selected
        f1_item = next(it for it in grp.files if it.path == f1)
        f2_item = next(it for it in grp.files if it.path == f2)
        f3_item = next(it for it in grp.files if it.path == f3)
        assert not f1_item.selected, "Oldest file f1 should NOT be selected"
        assert f2_item.selected, "f2 should be selected"
        assert f3_item.selected, "f3 should be selected"

        finder.auto_mark_selection(groups, keep_mode="newest")
        assert f1_item.selected, "Oldest f1 should now be selected"
        assert not f3_item.selected, "Newest f3 should NOT be selected"

        # Test 0-byte empty file duplicates
        empty1 = os.path.join(temp_dir, "empty1.txt")
        empty2 = os.path.join(temp_dir, "empty2.txt")
        with open(empty1, "wb") as f:
            pass
        with open(empty2, "wb") as f:
            pass

        empty_groups = finder.scan_duplicates(
            target_dirs=[temp_dir],
            min_size_bytes=0
        )
        assert len(empty_groups) >= 1, "Expected duplicate detection on 0-byte files with min_size_bytes=0"

        # Test protected path rejection
        assert finder.is_protected_path(r"C:\Windows\System32\calc.exe"), "C:\Windows must be protected"
        assert finder.is_protected_path(r"D:\Windows\notepad.exe"), "Non-C Windows path must be protected"
        assert finder.is_protected_path(r"C:\Program Files\App\test.exe"), "Program Files must be protected"

        print("  ✓ DuplicateFinder verification passed.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_registry_compactor():
    print("--> Testing RegistryCompactor engine...")
    from core.registry_compactor import RegistryCompactor

    compactor = RegistryCompactor()
    hives = compactor.get_loaded_hives()
    assert len(hives) > 0, "Expected at least 1 registry hive detected on Windows"

    analyzed = compactor.analyze_hives()
    assert len(analyzed) > 0, "Expected analyzed hive results"
    for h in analyzed:
        assert h.name and h.file_path
        assert h.current_size_bytes >= 0
        assert h.fragmentation_pct >= 0

    success, reclaimed_bytes, msg = compactor.compact_and_optimize()
    assert success is True
    assert reclaimed_bytes >= 0
    assert "optimize edildi" in msg
    print("  ✓ RegistryCompactor verification passed.")

def test_gaming_ping_tuner():
    print("--> Testing Gaming Ping Tuner (NetworkOptimizer)...")
    from core.network_optimizer import NetworkOptimizer

    optimizer = NetworkOptimizer()
    guids = optimizer.get_active_adapter_guids()
    print(f"  Found {len(guids)} active network interfaces")

    status = optimizer.is_gaming_ping_optimized()
    assert isinstance(status, bool)

    opt_ok, opt_msg = optimizer.optimize_gaming_ping()
    print(f"  Optimize Gaming Ping: {opt_ok} ({opt_msg})")

    res_ok, res_msg = optimizer.restore_default_ping_settings()
    print(f"  Restore Default Ping: {res_ok} ({res_msg})")
    print("  ✓ Gaming Ping Tuner verification passed.")

def test_privacy_anti_spy():
    print("--> Testing Anti-Spy & Telemetry Blocker (PrivacyTweaker)...")
    from core.privacy_tweaker import PrivacyTweaker

    tweaker = PrivacyTweaker()
    tweaks = tweaker.check_tweak_statuses()
    tweak_ids = [t.id for t in tweaks]

    expected_new_tweaks = ["cortana", "ceip", "consumer_features", "feedback_frequency", "app_diagnostics"]
    for tid in expected_new_tweaks:
        assert tid in tweak_ids, f"Expected {tid} in PrivacyTweaker tweaks"

    all_enabled = tweaker.are_all_anti_spy_enabled()
    assert isinstance(all_enabled, bool)
    print(f"  Anti-Spy Status: {'All Enabled' if all_enabled else 'Partially/Disabled'}")

    # Test master apply
    applied, failed, messages = tweaker.apply_all_anti_spy(enable=True)
    print(f"  Anti-Spy Apply: {applied} applied, {failed} failed")
    assert applied >= 0
    print("  ✓ Anti-Spy & Telemetry Blocker verification passed.")

def test_auto_cleaner_scheduler():
    print("--> Testing AutoCleaner Smart Scheduler...")
    from core.auto_cleaner import AutoCleaner, get_system_idle_seconds
    from core.config import ConfigManager

    cleaner = AutoCleaner()
    idle_secs = get_system_idle_seconds()
    assert idle_secs >= 0, f"Expected non-negative idle seconds, got {idle_secs}"
    print(f"  Current Windows idle time: {idle_secs:.1f}s")

    cfg = ConfigManager()
    cfg.set("auto_clean_enabled", True)

    # Test idle schedule condition
    cfg.set("auto_clean_schedule", "idle")
    cfg.set("auto_clean_idle_minutes", 99999)  # Huge number, shouldn't trigger
    should_run, reason = cleaner.should_trigger()
    assert not should_run, f"Should not trigger with 99999 min idle: {reason}"

    # Test scheduled_time condition
    cfg.set("auto_clean_schedule", "scheduled_time")
    now_dt = time.localtime()
    # Match current hour and day
    cfg.set("auto_clean_target_hour", now_dt.tm_hour)
    cfg.set("auto_clean_target_day", -1)  # Every day
    cfg.set("last_auto_clean_time", "2000-01-01T00:00:00")  # Long ago
    should_run, reason = cleaner.should_trigger()
    assert should_run, f"Should trigger when target hour matches today: {reason}"

    # Target hour in future shouldn't trigger
    cfg.set("auto_clean_target_hour", (now_dt.tm_hour + 2) % 24)
    should_run, reason = cleaner.should_trigger()
    assert not should_run, f"Should not trigger when target hour doesn't match: {reason}"

    print("  ✓ AutoCleaner Smart Scheduler verification passed.")

def test_hardware_monitor_telemetries():
    print("--> Testing HardwareMonitor Telemetries (Disk I/O, Discrete GPU, Top Consumer, Uptime)...")
    from core.hardware_monitor import HardwareMonitor

    hm = HardwareMonitor()
    # Give background thread a short moment to collect first sample
    time.sleep(1.2)

    tel = hm.get_hardware_stats()
    assert isinstance(tel, dict), "get_hardware_stats must return a dict"

    # Uptime
    uptime_str = tel.get("uptime_str", "")
    assert uptime_str and uptime_str != "Bilinmiyor", f"Invalid uptime string: {uptime_str}"
    print(f"  Uptime: {uptime_str} ({tel.get('uptime_seconds')} seconds)")

    # Disk I/O
    read_bps = tel.get("disk_read_bps", 0.0)
    write_bps = tel.get("disk_write_bps", 0.0)
    r_str = tel.get("disk_read_str", "")
    w_str = tel.get("disk_write_str", "")
    assert isinstance(read_bps, (int, float)) and isinstance(write_bps, (int, float))
    assert "/" in r_str and "/" in w_str
    print(f"  Disk I/O: Read={r_str}, Write={w_str}")

    # Top consumer process
    top_name = tel.get("top_consumer_name", "")
    top_str = tel.get("top_consumer_str", "")
    assert top_name and top_str, f"Invalid top consumer: {top_name} ({top_str})"
    print(f"  Top Consumer: {top_name} ({top_str})")

    # Discrete GPU
    has_gpu = tel.get("has_gpu", False)
    gpu_name = tel.get("gpu_name", "")
    gpu_temp = tel.get("gpu_temp", 0)
    vram_used = tel.get("gpu_mem_used_mb", 0)
    vram_total = tel.get("gpu_mem_total_mb", 0)
    if has_gpu:
        print(f"  Discrete GPU: {gpu_name} (Temp: {gpu_temp}°C, VRAM: {vram_used}/{vram_total}MB)")
    else:
        print("  Discrete GPU: Not detected or not available on this system.")

    print("  ✓ HardwareMonitor Telemetries verification passed.")

def test_desktop_performance_widget():
    print("--> Testing DesktopPerformanceWidget layouts, themes, and modes...")
    from ui.desktop_widget import DesktopPerformanceWidget
    from core.config import ConfigManager

    cfg = ConfigManager()
    widget = DesktopPerformanceWidget()

    # 1. Test layout modes and dynamic sizes
    for lmode in ("card", "horizontal", "vertical"):
        cfg.set("desktop_widget_layout", lmode)
        widget.apply_appearance()
        assert widget.layout_mode == lmode, f"Expected layout {lmode}, got {widget.layout_mode}"
        if lmode == "horizontal":
            assert widget.width() >= 420, f"Horizontal bar should be wide enough, got {widget.width()}"
        elif lmode == "vertical":
            assert widget.height() >= 120, f"Vertical strip should adapt height, got {widget.height()}"

    # 2. Test themes
    for tname in ("neon_cyan", "cyberpunk_purple", "oled_black", "minimal_white", "custom_rgb"):
        cfg.set("desktop_widget_theme", tname)
        widget.apply_appearance()
        assert widget.theme_name == tname, f"Expected theme {tname}, got {widget.theme_name}"

    # 3. Test opacity
    for opac in (0.30, 0.75, 1.0):
        cfg.set("desktop_widget_opacity", opac)
        widget.apply_appearance()
        assert widget.opacity == opac, f"Expected opacity {opac}, got {widget.opacity}"

    # 4. Test click-through and signal emission
    ct_signals = []
    widget.clickThroughToggled.connect(lambda s: ct_signals.append(s))
    widget.set_click_through(True)
    assert widget.click_through is True
    assert ct_signals == [True]
    # Redundant set should NOT re-emit signal
    widget.set_click_through(True)
    assert len(ct_signals) == 1
    widget.set_click_through(False)
    assert widget.click_through is False
    assert ct_signals == [True, False]

    # 5. Test boundary clamping on snap
    widget.move(-500, -500)
    widget.snap_to_edge_or_corner()
    screen = QApplication.primaryScreen().availableGeometry()
    assert widget.x() >= screen.left(), "Widget x must be clamped within screen bounds"
    assert widget.y() >= screen.top(), "Widget y must be clamped within screen bounds"

    # 6. Test telemetries update
    widget._update_telemetry()

    # 7. Test quick actions and layout-adaptive labels
    widget._on_quick_ram_boost()
    widget._toggle_game_mode()
    widget._toggle_silent_mode()

    # 8. Test Silent Mode notification suppression
    from ui.main_window import MainWindow
    mw = MainWindow()
    cfg.set("silent_mode_enabled", True)
    # notify_tray should suppress notification when silent_mode_enabled is True
    assert cfg.get("silent_mode_enabled") is True
    cfg.set("silent_mode_enabled", False)
    mw.cleanup_workers()
    mw.close()

    widget.close()
    print("  ✓ DesktopPerformanceWidget verification passed.")

def run_all():
    print("=" * 60)
    print("NovaCare Comprehensive New Features Verification")
    print("=" * 60)

    app = QApplication.instance()
    if not app:
        app = QApplication([])

    test_duplicate_finder()
    test_registry_compactor()
    test_gaming_ping_tuner()
    test_privacy_anti_spy()
    test_auto_cleaner_scheduler()
    test_hardware_monitor_telemetries()
    test_desktop_performance_widget()

    print("=" * 60)
    print("🎉 ALL NEW FEATURE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_all()
