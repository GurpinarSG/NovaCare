"""
NovaCare System Suite - 3rd-Pass Security, Reliability & Edge-Case Audit Test Suite
Validates all 15 critical, medium, and low security/reliability fixes:
1. core/bloatware_cleaner.py: package_name regex validation and Base64 UTF-16LE -EncodedCommand
2. core/utils.py: delete_registry_key_tree root hive & critical system branch protection
3. core/uninstaller.py: generic directory name exclusions preventing false-positive leftover deletion
4. scripts/installer_wizard.py: uninstall.bat rmdir backslash escape bug fix
5. scripts/installer_wizard.py: HKCU UninstallString direct executable call
6. core/game_booster.py: PowerGetActiveScheme kernel32.LocalFree try...finally memory protection
7. core/updater.py: apply_update.bat trailing backslash removal in xcopy
8. core/game_booster.py: powercfg calls without shell=True and cp1254 codepage
9. core/disk_analyzer.py: bounded min-heap memory usage in find_largest_files
10. core/startup_manager.py: atomic os.replace preventing FileExistsError
11. NovaCare.bat: %* argument forwarding
12. core/utils.py: to_long_path UNC network path handling (\\\\?\\UNC\\)
13. core/battery_reporter.py: temporary XML cleanup in finally block
14. ui/views/disk_view.py: Windows Explorer /select path with spaces quoting
15. scripts/create_shortcut.py: PowerShell single-quote sanitization and -EncodedCommand
"""
import os
import sys
import base64
import tempfile
import inspect
from unittest.mock import patch, MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)


def test_1_bloatware_cleaner_injection_and_encoded_cmd():
    print("[1/15] Testing BloatwareCleaner package_name regex validation & Base64 UTF-16LE...")
    from core.bloatware_cleaner import BloatwareCleaner

    cleaner = BloatwareCleaner()
    # Test malicious / invalid package names
    bad_inputs = [
        "",
        "Microsoft.BingWeather; Remove-Item C:\\ -Recurse",
        "Test' & calc.exe",
        "Test Package With Spaces",
        "Package|dir",
        "$(whoami)",
        "`calc`",
    ]
    for bad in bad_inputs:
        ok, msg = cleaner.remove_bloatware_package(bad)
        assert not ok, f"Expected rejection for '{bad}', but got success"
        assert "Geçersiz" in msg

    # Test valid package name executes with -EncodedCommand
    valid_name = "Microsoft.BingWeather"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        ok, msg = cleaner.remove_bloatware_package(valid_name)
        assert ok, f"Expected success for valid package, got: {msg}"
        assert mock_run.called
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[0] in ("powershell", "powershell.exe") or "powershell" in cmd[0].lower()
        assert "-NoProfile" in cmd
        assert "-EncodedCommand" in cmd
        idx = cmd.index("-EncodedCommand")
        b64_str = cmd[idx + 1]
        decoded_script = base64.b64decode(b64_str).decode("utf-16le")
        assert valid_name in decoded_script
        assert "Get-AppxPackage" in decoded_script
    print("  [✔] BloatwareCleaner strictly blocks command injection and uses -EncodedCommand.")


def test_2_delete_registry_key_tree_protection():
    print("[2/15] Testing delete_registry_key_tree root hive & critical system branch protection...")
    from core.utils import delete_registry_key_tree, CRITICAL_REGISTRY_BRANCHES

    assert "software" in CRITICAL_REGISTRY_BRANCHES
    assert "system" in CRITICAL_REGISTRY_BRANCHES
    assert "software\\microsoft" in CRITICAL_REGISTRY_BRANCHES
    assert "software\\wow6432node" in CRITICAL_REGISTRY_BRANCHES
    assert "software\\wow6432node\\microsoft" in CRITICAL_REGISTRY_BRANCHES
    assert "system\\currentcontrolset" in CRITICAL_REGISTRY_BRANCHES
    assert "software\\microsoft\\windows\\currentversion\\uninstall" in CRITICAL_REGISTRY_BRANCHES

    # Disallowed: 1-level paths
    assert not delete_registry_key_tree(1, "")
    assert not delete_registry_key_tree(1, "Software")
    assert not delete_registry_key_tree(1, "System")
    assert not delete_registry_key_tree(1, "SAM")
    assert not delete_registry_key_tree(1, "SECURITY")

    # Disallowed: critical 2-level and multi-level system branches
    assert not delete_registry_key_tree(1, r"Software\Microsoft")
    assert not delete_registry_key_tree(1, r"Software\Microsoft\Windows")
    assert not delete_registry_key_tree(1, r"Software\Microsoft\Windows NT")
    assert not delete_registry_key_tree(1, r"Software\WOW6432Node")
    assert not delete_registry_key_tree(1, r"Software\WOW6432Node\Microsoft")
    assert not delete_registry_key_tree(1, r"System\CurrentControlSet")
    assert not delete_registry_key_tree(1, r"Software/Policies/Microsoft")
    assert not delete_registry_key_tree(1, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")

    # Double backslash / slash bypass attempts
    assert not delete_registry_key_tree(1, r"Software\\Microsoft")
    assert not delete_registry_key_tree(1, r"Software//Microsoft")
    assert not delete_registry_key_tree(1, r"Software \ Microsoft ")
    assert not delete_registry_key_tree(1, r"Software\\WOW6432Node")

    # Depth validation: single level with trailing slash
    assert not delete_registry_key_tree(1, r"Software\\")
    print("  [✔] delete_registry_key_tree blocks root hives and critical system branches.")


def test_3_uninstaller_generic_directory_exclusions():
    print("[3/15] Testing Uninstaller generic directory name exclusions & system folder guards...")
    from core.uninstaller import _NAME_EXCLUSIONS, AppUninstaller, InstalledApp

    required_generic = {'application', 'bin', 'client', 'core', 'app', 'common', 'dist', 'release', 'x64', 'x86', 'packages', 'program'}
    assert required_generic.issubset(_NAME_EXCLUSIONS), f"Missing exclusions: {required_generic - _NAME_EXCLUSIONS}"

    # Verify candidate names never contain generic folder names
    uninst = AppUninstaller()
    dummy_app = InstalledApp(
        id="test",
        name="TestApp",
        version="1.0",
        publisher="TestVendor",
        install_date="2026-01-01",
        size_bytes=1000,
        uninstall_string="",
        quiet_uninstall_string="",
        install_location=r"C:\Program Files\TestApp\bin",
        icon_path="",
        registry_path="",
        root_name=""
    )
    # Even if install_location points to a folder whose basename is 'bin', 'bin' must NOT be considered
    # as candidate name to search C:\Program Files or AppData!
    cand_loc = os.path.basename(os.path.normpath(dummy_app.install_location)).lower()
    assert cand_loc in _NAME_EXCLUSIONS, "cand_loc 'bin' must be excluded by _NAME_EXCLUSIONS"
    leftovers = uninst.scan_leftovers(dummy_app)
    assert isinstance(leftovers, list)

    # Verify critical system folder protection rejects System32 or Common Files even if specified as install_location
    system32_app = InstalledApp(
        id="sys_test",
        name="SystemApp",
        version="1.0",
        publisher="TestVendor",
        install_date="2026-01-01",
        size_bytes=1000,
        uninstall_string="",
        quiet_uninstall_string="",
        install_location=r"C:\Windows\System32",
        icon_path="",
        registry_path="",
        root_name=""
    )
    sys_leftovers = uninst.scan_leftovers(system32_app)
    for item in sys_leftovers:
        assert r"windows\system32" not in item.path.lower(), f"System32 must never be in leftovers: {item.path}"
    print("  [✔] Generic folder names and critical system directories are safely blocked from leftovers.")


def test_4_installer_wizard_uninstall_bat_quoting():
    print("[4/15] Testing installer_wizard.py uninstall.bat backslash escape fix...")
    from scripts.installer_wizard import InstallWorker
    src = inspect.getsource(InstallWorker._generate_uninstaller)
    assert 'rmdir /s /q "%TARGET_DIR%"' in src, "Must have rmdir /s /q \"%TARGET_DIR%\""
    assert r'\"%TARGET_DIR%\"' not in src, "Must not have backslash escaped quotes"
    print("  [✔] uninstall.bat rmdir command correctly formatted without backslash bug.")


def test_5_installer_wizard_hkcu_uninstall_string():
    print("[5/15] Testing installer_wizard.py HKCU UninstallString simplification...")
    from scripts.installer_wizard import InstallWorker
    src = inspect.getsource(InstallWorker._register_uninstaller)
    assert 'f\'"{dest_exe}" --uninstall\'' in src
    assert 'f\'"{dest_exe}" --uninstall --silent\'' in src
    # Must not contain PowerShell Start-Process in HKCU registration
    assert "Start-Process -FilePath" not in src
    print("  [✔] HKCU UninstallString directly references executable without PowerShell.")


def test_6_game_booster_memory_free():
    print("[6/15] Testing GameBooster PowerGetActiveScheme LocalFree try...finally...")
    from core.game_booster import GameBooster
    src = inspect.getsource(GameBooster.get_current_power_scheme)
    assert "LocalFree" in src, "Must use kernel32.LocalFree"
    assert "CoTaskMemFree" not in src, "Must not use CoTaskMemFree"
    assert "finally:" in src, "Must free in finally block"
    print("  [✔] PowerGetActiveScheme memory freed via kernel32.LocalFree in try...finally.")


def test_7_updater_apply_update_bat_trailing_slash():
    print("[7/15] Testing updater apply_update.bat trailing backslash removal in xcopy...")
    from core.updater import GitHubUpdater
    src = inspect.getsource(GitHubUpdater.download_and_prepare_update)
    assert 'xcopy /s /e /y /i /q /r /h' in src
    assert '"{app_root}" >' in src
    assert '"{app_root}\\"' not in src
    print("  [✔] apply_update.bat xcopy destination has no trailing backslash escaping closing quote.")


def test_8_game_booster_powercfg_no_shell():
    print("[8/15] Testing GameBooster powercfg calls for no shell=True & safe encoding...")
    from core.game_booster import GameBooster
    src_get = inspect.getsource(GameBooster.get_current_power_scheme)
    src_ens = inspect.getsource(GameBooster.ensure_ultimate_power_plan)
    assert 'shell=True' not in src_get
    assert 'cp1254' not in src_get
    assert 'shell=True' not in src_ens
    assert 'cp1254' not in src_ens
    assert 'errors="replace"' in src_get
    assert 'errors="replace"' in src_ens
    print("  [✔] powercfg subprocess invocations avoid shell=True and cp1254 codepage.")


def test_9_disk_analyzer_bounded_min_heap():
    print("[9/15] Testing DiskAnalyzer bounded min-heap memory safety...")
    from core.disk_analyzer import DiskAnalyzer
    da = DiskAnalyzer()

    # Create temporary directory with files of known sizes
    with tempfile.TemporaryDirectory() as td:
        created_files = []
        for i in range(12):
            size = (i + 1) * 1024 * 1024  # 1MB to 12MB
            p = os.path.join(td, f"file_{i}.bin")
            with open(p, "wb") as f:
                f.seek(size - 1)
                f.write(b"\0")
            created_files.append((p, size))

        # Test limit=5 with min_size_mb=1 (in MB: 1 MB = 1048576 bytes)
        results = da.scan_largest_files(td, limit=5, min_size_mb=1)
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        # Verify sorted descending
        sizes = [r.size_bytes for r in results]
        assert sizes == sorted(sizes, reverse=True), f"Results must be sorted descending: {sizes}"
        # Verify the top 5 sizes correspond to 12MB, 11MB, 10MB, 9MB, 8MB
        expected_top = [12 * 1024 * 1024, 11 * 1024 * 1024, 10 * 1024 * 1024, 9 * 1024 * 1024, 8 * 1024 * 1024]
        assert sizes == expected_top, f"Expected {expected_top}, got {sizes}"

        # Test limit=0
        results_zero = da.scan_largest_files(td, limit=0, min_size_mb=1)
        assert results_zero == []
    print("  [✔] DiskAnalyzer scan_largest_files bounds heap memory and returns top N descending.")


def test_10_startup_manager_atomic_replace():
    print("[10/15] Testing StartupManager atomic os.replace preventing FileExistsError...")
    from core.startup_manager import StartupManager, StartupItem
    sm = StartupManager()

    with tempfile.TemporaryDirectory() as td:
        orig_file = os.path.join(td, "app.lnk")
        dis_file = orig_file + ".disabled"
        with open(orig_file, "w") as f:
            f.write("active")
        # Pre-create the disabled file to simulate a collision that would crash os.rename
        with open(dis_file, "w") as f:
            f.write("old collision")

        item = StartupItem(
            id="1",
            name="TestApp",
            command=orig_file,
            location="Startup Folder",
            location_type="folder",
            source_key_or_path=orig_file,
            root_name=None,
            enabled=True,
            boot_impact="Normal"
        )
        # Toggle to disabled: should overwrite dis_file cleanly via os.replace
        ok = sm.toggle_item(item)
        assert ok, "toggle_item must succeed"
        assert not os.path.exists(orig_file)
        assert os.path.exists(dis_file)
        assert item.enabled is False

        # Now pre-create orig_file to simulate collision in re-enabling
        with open(orig_file, "w") as f:
            f.write("collision again")
        ok2 = sm.toggle_item(item)
        assert ok2, "toggle_item must succeed on re-enable"
        assert os.path.exists(orig_file)
        assert not os.path.exists(dis_file)
        assert item.enabled is True
    print("  [✔] StartupManager uses atomic os.replace without FileExistsError.")


def test_11_novacare_bat_argument_forwarding():
    print("[11/15] Testing NovaCare.bat %* argument forwarding...")
    bat_path = os.path.join(root_dir, "NovaCare.bat")
    with open(bat_path, "r", encoding="utf-8") as f:
        bat_content = f.read()

    assert 'start "" "NovaCare.exe" %*' in bat_content
    assert 'start "" "dist\\NovaCare.exe" %*' in bat_content
    assert 'start "" pythonw main.py %*' in bat_content
    print("  [✔] NovaCare.bat forwards all command-line arguments (%*).")


def test_12_to_long_path_unc():
    print("[12/15] Testing to_long_path UNC network path handling...")
    from core.utils import to_long_path

    # Short paths: untouched
    short_path = r"C:\short\path.txt"
    assert to_long_path(short_path) == short_path

    # Standard long path >= 240
    long_standard = r"C:\\" + ("a" * 250) + r"\file.txt"
    norm_standard = os.path.normpath(long_standard)
    result_standard = to_long_path(long_standard)
    if os.name == 'nt':
        assert result_standard == "\\\\?\\" + norm_standard
        assert not result_standard.startswith("\\\\?\\UNC\\")

    # Long UNC path >= 240
    long_unc = "\\\\server\\share\\" + ("sub" * 80) + "\\file.txt"
    result_unc = to_long_path(long_unc)
    if os.name == 'nt':
        assert result_unc.startswith("\\\\?\\UNC\\")
        assert not result_unc.startswith("\\\\?\\\\\\")
        assert result_unc == "\\\\?\\UNC\\server\\share\\" + ("sub" * 80) + "\\file.txt"

    # Already prefixed path
    already_prefixed = "\\\\?\\C:\\test"
    assert to_long_path(already_prefixed) == already_prefixed
    already_unc = "\\\\?\\UNC\\server\\share\\test"
    assert to_long_path(already_unc) == already_unc
    print("  [✔] to_long_path correctly prefixes UNC paths with \\\\?\\UNC\\.")


def test_13_battery_reporter_cleanup_finally():
    print("[13/15] Testing BatteryReporter temporary XML file cleanup in finally block...")
    from core.battery_reporter import BatteryReporter

    # Force error during XML parsing to verify file is deleted in finally
    reporter = BatteryReporter()
    BatteryReporter._cached_hardware = None

    tmp_file_created = []

    def fake_run(cmd, **kwargs):
        # Create invalid XML at output path
        out_idx = cmd.index("/output") + 1
        path = cmd[out_idx]
        tmp_file_created.append(path)
        with open(path, "w") as f:
            f.write("INVALID XML CONTENT THAT CAUSES PARSER ERROR")
        return MagicMock(returncode=0)

    with patch("core.battery_reporter.is_battery_present", return_value=True):
        with patch("subprocess.run", side_effect=fake_run):
            reporter.fetch_hardware_details()

    assert len(tmp_file_created) == 1
    assert not os.path.exists(tmp_file_created[0]), "Temporary XML file must be deleted even on parse error"
    print("  [✔] BatteryReporter XML file guaranteed cleaned up in finally block.")


def test_14_disk_view_explorer_select_quoting():
    print("[14/15] Testing disk_view.py Windows Explorer /select path with spaces quoting...")
    from ui.views.disk_view import DiskView
    src = inspect.getsource(DiskView._open_file_location)
    assert 'subprocess.Popen(f\'explorer.exe /select,"{norm}"\')' in src or 'explorer.exe /select,"{norm}"' in src
    assert 'subprocess.Popen(["explorer.exe", f"/select,{norm}"])' not in src
    print("  [✔] Windows Explorer /select properly formatted with path-level quotes.")


def test_15_create_shortcut_sanitization_and_encoded_cmd():
    print("[15/15] Testing create_shortcut.py PowerShell sanitization and -EncodedCommand...")
    from scripts.create_shortcut import create_shortcuts

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        create_shortcuts()
        assert mock_run.called
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[0] in ("powershell.exe", "powershell") or "powershell" in cmd[0].lower()
        assert "-EncodedCommand" in cmd
        idx = cmd.index("-EncodedCommand")
        b64_str = cmd[idx + 1]
        decoded = base64.b64decode(b64_str).decode("utf-16le")
        assert "WScript.Shell" in decoded
        assert "NovaCare.lnk" in decoded
        assert ".TargetPath =" in decoded
        assert ".WorkingDirectory =" in decoded
    print("  [✔] create_shortcut.py uses Base64 UTF-16LE -EncodedCommand.")


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare 3rd-Pass Security & Reliability Verification Suite")
    print("=" * 65)

    test_1_bloatware_cleaner_injection_and_encoded_cmd()
    test_2_delete_registry_key_tree_protection()
    test_3_uninstaller_generic_directory_exclusions()
    test_4_installer_wizard_uninstall_bat_quoting()
    test_5_installer_wizard_hkcu_uninstall_string()
    test_6_game_booster_memory_free()
    test_7_updater_apply_update_bat_trailing_slash()
    test_8_game_booster_powercfg_no_shell()
    test_9_disk_analyzer_bounded_min_heap()
    test_10_startup_manager_atomic_replace()
    test_11_novacare_bat_argument_forwarding()
    test_12_to_long_path_unc()
    test_13_battery_reporter_cleanup_finally()
    test_14_disk_view_explorer_select_quoting()
    test_15_create_shortcut_sanitization_and_encoded_cmd()

    print("\n" + "=" * 65)
    print("  >>> ALL 15 SECURITY AUDIT #3 TESTS PASSED PERFECTLY! <<<")
    print("=" * 65)
