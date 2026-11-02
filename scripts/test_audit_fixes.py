"""
NovaCare System Suite - Comprehensive 14-Point Audit Fixes Verification Suite
Validates all defensive fixes and reliability enhancements across core and UI modules.
"""
import os
import sys
import time
import shutil
import tempfile
import threading
from unittest.mock import MagicMock, patch

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

def test_1_disk_analyzer_delete_file_safely():
    print("[1/14] Testing DiskAnalyzer.delete_file_safely and delete_file...")
    from core.disk_analyzer import DiskAnalyzer

    analyzer = DiskAnalyzer()

    # 1. Non-existent file
    ok, msg = analyzer.delete_file_safely("C:\\non_existent_novacare_file_12345.xyz")
    assert not ok, "Non-existent file must not be reported as deleted"
    assert "bulunamadı" in msg.lower() or "geçersiz" in msg.lower()

    # 2. Critical system file protection
    sys_root = os.environ.get('SystemRoot', r'C:\Windows')
    crit_path = os.path.join(sys_root, "System32", "notepad.exe")
    ok, msg = analyzer.delete_file_safely(crit_path)
    assert not ok, "Critical system file must be rejected"
    assert "güvenlik" in msg.lower() or "silinemez" in msg.lower()

    # 3. Safe deletion of real temporary file
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_name = f.name
        f.write(b"NovaCare Test Safe Deletion")

    assert os.path.isfile(tmp_name)
    ok, msg = analyzer.delete_file_safely(tmp_name)
    assert ok, f"delete_file_safely failed on temp file: {msg}"
    assert not os.path.exists(tmp_name), "Temp file should be removed from filesystem"

    # 4. delete_file returns bool
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_name2 = f.name
        f.write(b"NovaCare Test Bool")
    bool_ok = analyzer.delete_file(tmp_name2)
    assert bool_ok is True, "delete_file must return True on success"
    assert not os.path.exists(tmp_name2)

    print("  [✔] DiskAnalyzer.delete_file_safely and delete_file verified successfully.")


def test_2_duplicate_finder_imports_and_guard():
    print("[2/14] Testing DuplicateFinder protected system file import & guards...")
    from core.duplicate_finder import DuplicateFinder, is_protected_system_file
    from core.disk_analyzer import is_critical_system_file

    # Verify functions are callable and aliased properly
    assert callable(is_protected_system_file)
    assert callable(is_critical_system_file)
    assert is_protected_system_file == is_critical_system_file

    # Verify DuplicateFinder.is_protected_path recognizes critical paths
    sys_root = os.environ.get('SystemRoot', r'C:\Windows')
    assert DuplicateFinder.is_protected_path(os.path.join(sys_root, "explorer.exe"))
    assert DuplicateFinder.is_protected_path(r"C:\pagefile.sys")
    assert DuplicateFinder.is_protected_path(r"C:\Program Files\Test\App.exe")
    assert DuplicateFinder.is_protected_path(r"D:\$Recycle.Bin\S-1-5-21\test.tmp")

    print("  [✔] DuplicateFinder system file imports & guards verified.")


def test_3_hardware_monitor_cpu_smoothness():
    print("[3/14] Testing HardwareMonitor centralized CPU sampling & concurrency...")
    from core.hardware_monitor import HardwareMonitor
    from core.memory_booster import MemoryBooster

    hm = HardwareMonitor()
    time.sleep(0.5)

    # Concurrently query CPU percent from 10 threads simulating concurrent timers
    readings = []
    def reader():
        for _ in range(5):
            pct = hm.get_cpu_percent()
            readings.append(pct)
            time.sleep(0.02)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(readings) == 50
    for r in readings:
        assert isinstance(r, (int, float))
        assert 0.0 <= r <= 100.0, f"CPU reading out of bounds: {r}"

    # Verify MemoryBooster get_system_metrics returns smooth CPU without collision
    mb = MemoryBooster()
    metrics = mb.get_system_metrics()
    assert "cpu_percent" in metrics
    assert 0.0 <= metrics["cpu_percent"] <= 100.0

    print("  [✔] HardwareMonitor centralized locked CPU sampling verified without collision.")


def test_4_duplicate_finder_long_paths():
    print("[4/14] Testing DuplicateFinder to_long_path support on deep paths (>260 chars)...")
    from core.duplicate_finder import DuplicateFinder
    from core.utils import to_long_path

    # Construct a path exceeding MAX_PATH (260 characters)
    temp_dir = tempfile.mkdtemp(prefix="novacare_longpath_test_")
    try:
        deep_dir = temp_dir
        # Create nested folders to exceed 260 chars
        for i in range(12):
            deep_dir = os.path.join(deep_dir, f"subfolder_level_{i:02d}_very_deep_nesting")
        os.makedirs(to_long_path(deep_dir), exist_ok=True)

        long_file = os.path.join(deep_dir, "test_duplicate_target_sample_data.bin")
        assert len(long_file) > 260, f"Path should exceed 260 chars, length is {len(long_file)}"

        # Write data using to_long_path
        with open(to_long_path(long_file), "wb") as f:
            f.write(b"NovaCare Long Path Hash Test Content" * 50)

        # Calculate partial and full hashes
        partial_hash = DuplicateFinder._calc_partial_hash(long_file)
        full_hash = DuplicateFinder._calc_full_md5(long_file)

        assert partial_hash is not None, "Partial hash failed on >260 char path"
        assert full_hash is not None, "Full hash failed on >260 char path"
        assert len(full_hash) == 32, "Full MD5 hash should be 32 hex characters"
    finally:
        shutil.rmtree(to_long_path(temp_dir), ignore_errors=True)

    print("  [✔] DuplicateFinder safely handles long paths (>260 chars) without WinError 206.")


def test_5_desktop_widget_64bit_win32_signatures():
    print("[5/14] Testing DesktopPerformanceWidget 64-bit Win32 types & set_click_through...")
    from ui.desktop_widget import DesktopPerformanceWidget, _get_window_long, _set_window_long
    import ctypes

    if sys.platform == 'win32':
        assert _get_window_long is not None
        assert _set_window_long is not None
        # Verify 64-bit restype and argtypes
        from ctypes import wintypes
        LONG_PTR = ctypes.c_ssize_t
        assert _get_window_long.restype == LONG_PTR
        assert _get_window_long.argtypes[0] == wintypes.HWND
        assert _get_window_long.argtypes[1] == ctypes.c_int

        assert _set_window_long.restype == LONG_PTR
        assert _set_window_long.argtypes[0] == wintypes.HWND
        assert _set_window_long.argtypes[1] == ctypes.c_int
        assert _set_window_long.argtypes[2] == LONG_PTR

    widget = DesktopPerformanceWidget()
    widget.set_click_through(False)
    assert widget.click_through is False
    widget.set_click_through(True)
    assert widget.click_through is True
    widget.set_click_through(False)
    widget.close()

    print("  [✔] DesktopPerformanceWidget Win32 API 64-bit types and handles verified.")


def test_6_is_critical_system_file_protections():
    print("[6/14] Testing is_critical_system_file extended directory protections...")
    from core.disk_analyzer import is_critical_system_file

    # 1. Program Files
    assert is_critical_system_file(r"C:\Program Files\Internet Explorer\iexplore.exe")
    assert is_critical_system_file(r"D:\Program Files\SomeApp\binary.exe")

    # 2. Program Files (x86)
    assert is_critical_system_file(r"C:\Program Files (x86)\Common Files\system.dll")
    assert is_critical_system_file(r"E:\Program Files (x86)\Steam\steam.exe")

    # 3. ProgramData
    assert is_critical_system_file(r"C:\ProgramData\Microsoft\Windows\Start Menu")
    assert is_critical_system_file(r"D:\ProgramData\Packages\data.cache")

    # 4. $Recycle.Bin
    assert is_critical_system_file(r"C:\$Recycle.Bin\S-1-5-21-12345\file.txt")
    assert is_critical_system_file(r"E:\$recycle.bin")

    # 5. System Volume Information
    assert is_critical_system_file(r"C:\System Volume Information\tracking.log")
    assert is_critical_system_file(r"D:\system volume information\wpsettings.dat")

    # 6. Windows SystemRoot and extended-length path prefix
    assert is_critical_system_file(r"C:\Windows\System32\ntoskrnl.exe")
    assert is_critical_system_file(r"\\?\C:\Windows\System32\cmd.exe")
    assert is_critical_system_file(r"\\?\C:\Program Files\Common Files\system.dll")
    assert is_critical_system_file(r"D:\Windows\System32\hal.dll")
    assert is_critical_system_file(r"E:\windows\explorer.exe")

    # 7. Unprotected user document
    assert not is_critical_system_file(r"C:\Users\Gurpi\Documents\my_custom_notes.txt")

    print("  [✔] is_critical_system_file protected directories verified across all drives.")


def test_7_privacy_tweaker_service_rollback():
    print("[7/14] Testing PrivacyTweaker anti-spy service rollback (enable=False)...")
    from core.privacy_tweaker import PrivacyTweaker

    tweaker = PrivacyTweaker()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        # 1. Test enable=True (stops and disables services)
        _, _, stopped = tweaker.apply_all_anti_spy(enable=True)
        assert len(stopped) == 2, "Expected 2 services stopped on enable=True"

        # Check sc config start=disabled called
        disabled_calls = [
            call for call in mock_run.call_args_list
            if "start=disabled" in " ".join(call[0][0])
        ]
        assert len(disabled_calls) == 2, f"Expected 2 start=disabled calls, got {len(disabled_calls)}"

        # 2. Test enable=False (restores start=auto and starts services)
        mock_run.reset_mock()
        _, _, restored = tweaker.apply_all_anti_spy(enable=False)
        assert len(restored) == 2, "Expected 2 services restored on enable=False"

        auto_calls = [
            call for call in mock_run.call_args_list
            if "start=auto" in " ".join(call[0][0])
        ]
        assert len(auto_calls) == 2, f"Expected 2 start=auto calls, got {len(auto_calls)}"

        start_calls = [
            call for call in mock_run.call_args_list
            if "net" in " ".join(call[0][0]) and "start" in " ".join(call[0][0])
        ]
        assert len(start_calls) == 2, f"Expected 2 net start calls, got {len(start_calls)}"

    print("  [✔] PrivacyTweaker service rollback logic verified.")


def test_8_auto_cleaner_threshold_cooldown():
    print("[8/14] Testing AutoCleaner threshold mode 30-minute cooldown...")
    from core.auto_cleaner import AutoCleaner
    from core.config import ConfigManager
    from datetime import datetime, timedelta

    cfg = ConfigManager()
    cleaner = AutoCleaner()

    cfg.set("auto_clean_enabled", True)
    cfg.set("auto_clean_schedule", "threshold")
    cfg.set("auto_clean_threshold_mb", 500)

    # Simulate recent scan 5 minutes ago with junk below threshold
    recent_scan = (datetime.now() - timedelta(minutes=5)).isoformat()
    cfg.set("last_threshold_scan_time", recent_scan)
    cfg.set("last_threshold_junk_bytes", 100 * 1024 * 1024) # 100MB

    with patch.object(cleaner.junk_cleaner, "scan_all") as mock_scan:
        should_run, reason = cleaner.should_trigger()
        # Full scan should NOT have been performed because of cooldown
        mock_scan.assert_not_called()
        assert should_run is False
        assert "bekleme süresinde" in reason.lower()

    # Simulate scan 35 minutes ago (cooldown expired)
    expired_scan = (datetime.now() - timedelta(minutes=35)).isoformat()
    cfg.set("last_threshold_scan_time", expired_scan)

    with patch.object(cleaner.junk_cleaner, "scan_all") as mock_scan:
        mock_cat = MagicMock()
        mock_cat.size = 600 * 1024 * 1024 # 600MB > 500MB
        mock_scan.return_value = [mock_cat]

        should_run, reason = cleaner.should_trigger()
        # Scan should now run
        mock_scan.assert_called_once()
        assert should_run is True
        assert "500 mb sınırını aştı" in reason.lower()

    # Clean up config
    cfg.set("auto_clean_schedule", "daily")

    print("  [✔] AutoCleaner threshold cooldown verified.")


def test_9_main_window_tray_exit_cleanup():
    print("[9/14] Testing MainWindow tray exit clean closeEvent & cleanup_workers...")
    from ui.main_window import MainWindow

    mw = MainWindow()
    mw.hide()

    orig_cleanup = mw.cleanup_workers
    cleaned_up = []
    def wrapped_cleanup():
        cleaned_up.append(True)
        orig_cleanup()

    mw.cleanup_workers = wrapped_cleanup

    with patch.object(app, "quit"):
        mw._exit_application()

    assert mw._force_exit is True
    assert len(cleaned_up) > 0, "cleanup_workers must be invoked on _exit_application"
    app.processEvents()

    print("  [✔] MainWindow tray exit guarantees closeEvent and cleanup_workers execution.")



def test_10_duplicate_finder_reparse_point_skip():
    print("[10/14] Testing DuplicateFinder reparse point (junction) skipping...")
    from core.duplicate_finder import DuplicateFinder


    df = DuplicateFinder()

    # Test with mock os.walk containing simulated junction directory
    fake_dirs = ["normal_folder", "junction_folder", ".hidden_folder"]

    temp_dir = tempfile.gettempdir()
    with patch("os.walk") as mock_walk, \
         patch("core.duplicate_finder.is_reparse_point") as mock_is_reparse:

        def reparse_side_effect(path):
            return "junction_folder" in path

        mock_is_reparse.side_effect = reparse_side_effect
        mock_walk.return_value = [
            (temp_dir, fake_dirs, ["file1.txt"])
        ]

        # Scan with cancel after root to inspect dirs filtering
        cancel_called = [False]
        def cancel_check():
            if cancel_called[0]:
                return True
            cancel_called[0] = True
            return False

        df.scan_duplicates([temp_dir], cancel_check=cancel_check)

        # junction_folder and .hidden_folder should be pruned from fake_dirs
        assert "junction_folder" not in fake_dirs
        assert ".hidden_folder" not in fake_dirs
        assert "normal_folder" in fake_dirs


    print("  [✔] DuplicateFinder directory junctions correctly pruned.")


def test_11_registry_cleaner_startup_path_resolution():
    print("[11/14] Testing RegistryCleaner PATH resolution in _scan_startup_keys...")
    from core.registry_cleaner import RegistryCleaner
    import winreg

    rc = RegistryCleaner()

    # Test path resolution for PATH-based executables
    assert shutil.which("explorer.exe") is not None or shutil.which("cmd.exe") is not None

    # Simulate scanning a key with valid command 'explorer.exe'
    with patch("winreg.OpenKey"), \
         patch("winreg.QueryInfoKey", side_effect=[(0, 2, 0), OSError, OSError, OSError, OSError]), \
         patch("winreg.EnumValue") as mock_enum:

        mock_enum.side_effect = [
            ("ExplorerStartup", "explorer.exe", winreg.REG_SZ),
            ("InvalidBrokenApp", r"C:\BogusPathNonExistent\broken.exe", winreg.REG_SZ)
        ]

        rc._scan_startup_keys()


        # Only the truly broken app should be flagged, not explorer.exe
        issue_exes = [iss.value_data for iss in rc.issues]
        assert "explorer.exe" not in issue_exes, "explorer.exe should resolve via PATH and not be flagged"
        assert any("broken.exe" in v for v in issue_exes), "Broken executable must be flagged"

    print("  [✔] RegistryCleaner checks PATH before declaring startup entries invalid.")


def test_12_registry_cleaner_uninstaller_subkey_tree_deletion():
    print("[12/14] Testing RegistryCleaner uninstaller subkey tree deletion...")
    from core.registry_cleaner import RegistryCleaner, RegistryIssue

    rc = RegistryCleaner()
    issue = RegistryIssue(
        id="uninst_HKCU_TestAppGuid_0",
        category="Bozuk Kaldırma Bilgisi",
        root_name="HKCU",
        sub_key=r"Software\Microsoft\Windows\CurrentVersion\Uninstall\TestAppGuid",
        value_name="",
        value_data=r"C:\App\unins000.exe",
        value_type=1,
        reason="Kaldırma programı mevcut değil"
    )

    with patch("core.registry_cleaner.delete_registry_key_tree") as mock_delete_tree, \
         patch.object(rc, "create_backup", return_value="dummy_backup.json"):

        mock_delete_tree.return_value = True

        fixed, failed, _ = rc.fix_issues([issue])

        assert fixed == 1
        assert failed == 0
        mock_delete_tree.assert_called_once()
        call_sub = mock_delete_tree.call_args[0][1]
        assert "TestAppGuid" in call_sub

    print("  [✔] RegistryCleaner uninstaller fixes safely delete the entire subkey tree.")


def test_13_hardware_monitor_acpi_exponential_backoff():
    print("[13/14] Testing HardwareMonitor ACPI polling exponential backoff...")
    from core.hardware_monitor import HardwareMonitor

    # Verify HardwareMonitor._calc_acpi_backoff_sleep directly on the actual class
    assert HardwareMonitor._calc_acpi_backoff_sleep(0) == 5.0
    assert HardwareMonitor._calc_acpi_backoff_sleep(1) == 15.0
    assert HardwareMonitor._calc_acpi_backoff_sleep(3) == 60.0
    assert HardwareMonitor._calc_acpi_backoff_sleep(6) == 300.0
    assert HardwareMonitor._calc_acpi_backoff_sleep(9) == 900.0
    assert HardwareMonitor._calc_acpi_backoff_sleep(12) == 1800.0

    print("  [✔] HardwareMonitor ACPI exponential backoff calculation verified.")


def test_14_hardware_monitor_adapter_ram_overflow():
    print("[14/14] Testing HardwareMonitor AdapterRAM 32-bit signed overflow conversion...")
    from core.hardware_monitor import HardwareMonitor

    # Test HardwareMonitor._normalize_adapter_ram directly
    ram_tests = [
        (-1073741824, 3072),            # (-1GB + 4GB = 3GB)
        (-2147483648, 2048),            # (-2GB + 4GB = 2GB)
        (8589934592, 8192),             # 8GB normal int64
        (0, 0),                         # 0 bytes
        (None, 0),                      # None / missing
    ]

    for raw_ram, expected_mb in ram_tests:
        norm = HardwareMonitor._normalize_adapter_ram(raw_ram)
        mb = int(norm / (1024 ** 2))
        assert mb == expected_mb, f"Expected {expected_mb}MB for {raw_ram}, got {mb}MB"

    print("  [✔] HardwareMonitor AdapterRAM signed 32-bit overflow converted successfully.")


def run_all_tests():
    print("=" * 65)
    print("  NovaCare 14-Point Comprehensive Audit Verification Suite")
    print("=" * 65)

    test_1_disk_analyzer_delete_file_safely()
    test_2_duplicate_finder_imports_and_guard()
    test_3_hardware_monitor_cpu_smoothness()
    test_4_duplicate_finder_long_paths()
    test_5_desktop_widget_64bit_win32_signatures()
    test_6_is_critical_system_file_protections()
    test_7_privacy_tweaker_service_rollback()
    test_8_auto_cleaner_threshold_cooldown()
    test_9_main_window_tray_exit_cleanup()
    test_10_duplicate_finder_reparse_point_skip()
    test_11_registry_cleaner_startup_path_resolution()
    test_12_registry_cleaner_uninstaller_subkey_tree_deletion()
    test_13_hardware_monitor_acpi_exponential_backoff()
    test_14_hardware_monitor_adapter_ram_overflow()

    print("\n" + "=" * 65)
    print("🎉 ALL 14 AUDIT DEFENSIVE FIXES VERIFIED AND PASSED 100%!")
    print("=" * 65)

if __name__ == "__main__":
    run_all_tests()
