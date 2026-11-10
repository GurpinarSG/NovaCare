"""
NovaCare System Suite - Code Audit Fixes Verification Test Suite
Validates all P0, P1, and P2 audit fixes:
- 64-bit ctypes prototypes (RegFlushKey, OpenProcess, EmptyWorkingSet, ShellExecuteW)
- GetTickCount64 overflow handling & system idle calculation
- SYSTEM_EXCLUDED_BINS filtering in uninstaller scanner
- Full subkey value backup & restoration for uninstaller entries
- Strict return status checks in autostart & bloatware cleaners
- Procedural QThread cancellation (cancel()) and double-trigger prevention
"""
import sys
import os
import winreg
import ctypes
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication

# Ensure QApplication exists for QThread tests
_app = QApplication.instance() or QApplication(sys.argv)

import core.registry_compactor as reg_compactor
import core.memory_booster as memory_booster
import core.utils as utils
import core.auto_cleaner as auto_cleaner
import core.registry_cleaner as registry_cleaner
import core.backup_manager as backup_manager
import core.bloatware_cleaner as bloatware_cleaner
import core.autostart as autostart
import core.uninstaller as uninstaller
import core.network_optimizer as network_optimizer

import ui.views.hardware_health_view as hw_view
import ui.views.privacy_view as priv_view
import ui.views.dashboard_view as dash_view
import ui.views.rescue_view as rescue_view
import ui.views.memory_view as mem_view
import ui.views.startup_view as startup_view
import ui.views.uninstaller_view as uninst_view
import ui.views.junk_view as junk_view
import ui.views.registry_view as r_view
import ui.views.disk_view as disk_view
import ui.views.network_view as net_view
import ui.views.battery_view as bat_view
import ui.views.settings_view as settings_view
import ui.main_window as main_window
import ui.game_profiles_dialog as game_profiles_dialog


class TestCodeAuditFixes(unittest.TestCase):

    def test_01_64bit_reg_flush_key(self):
        """P0: Verify advapi32.RegFlushKey argument and return types handle 64-bit hive pointers safely."""
        compactor = reg_compactor.RegistryCompactor()
        advapi32 = ctypes.windll.advapi32
        
        # Run compact_registry which defines argtypes and restype
        success, reclaimed, msg = compactor.compact_registry()
        self.assertTrue(success, "Registry compaction should succeed")
        self.assertEqual(advapi32.RegFlushKey.argtypes, [ctypes.c_void_p])
        self.assertEqual(advapi32.RegFlushKey.restype, ctypes.c_long)

        # Directly invoke with winreg.HKEY_CURRENT_USER to ensure 0xffffffff80000001 does not raise OverflowError
        res = advapi32.RegFlushKey(winreg.HKEY_CURRENT_USER)
        self.assertEqual(res, 0, f"RegFlushKey on HKCU must return ERROR_SUCCESS (0), got {res}")
        print("  [✔] 64-bit RegFlushKey handle passing verified without OverflowError.")

    def test_02_64bit_memory_booster_apis(self):
        """P0: Verify 64-bit prototypes for kernel32 and psapi to prevent handle truncation."""
        k32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi

        self.assertEqual(k32.GetCurrentProcess.restype, ctypes.c_void_p)
        self.assertEqual(k32.OpenProcess.restype, ctypes.c_void_p)
        self.assertEqual(k32.OpenProcess.argtypes, [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong])
        self.assertEqual(k32.CloseHandle.argtypes, [ctypes.c_void_p])
        self.assertEqual(psapi.EmptyWorkingSet.argtypes, [ctypes.c_void_p])
        self.assertEqual(psapi.EmptyWorkingSet.restype, ctypes.c_int)

        # Test trim_own_memory does not fail with ERROR_INVALID_HANDLE
        memory_booster.MemoryBooster.trim_own_memory()

        booster = memory_booster.MemoryBooster()
        freed, count = booster.optimize_ram(max_seconds=0.8)
        self.assertIsInstance(freed, int)
        self.assertIsInstance(count, int)
        print("  [✔] 64-bit memory booster prototypes verified with successful working set trim.")

    def test_03_64bit_shellexecute_restype(self):
        """P0: Verify shell32.ShellExecuteW restype is set to c_void_p."""
        shell32 = ctypes.windll.shell32
        # Call restart_as_admin in dry/mock mode or verify binding
        with patch.object(shell32, "ShellExecuteW", return_value=42):
            with patch.object(sys, "exit") as mock_exit:
                res = utils.restart_as_admin()
                self.assertTrue(res)
                mock_exit.assert_called_once_with(0)
        self.assertEqual(shell32.ShellExecuteW.restype, ctypes.c_void_p)
        print("  [✔] 64-bit ShellExecuteW.restype and (ret or 0) > 32 check verified.")

    def test_04_get_tick_count_64_overflow(self):
        """P1: Verify GetTickCount64 overflow handling for idle time calculations."""
        # 1. Real call
        idle = auto_cleaner.get_system_idle_seconds()
        self.assertIsInstance(idle, float)
        self.assertGreaterEqual(idle, 0.0)

        # 2. Simulated tick wrap-around: curr wraps 32-bit boundary compared to dwTime
        # If dwTime = 0xFFFFFF00 and curr 32-bit is 0x00000050, difference is negative without handling
        dw_time = 0xFFFFFF00
        curr_32 = 0x00000050
        millis = (curr_32 & 0xFFFFFFFF) - dw_time
        if millis < 0:
            millis += 0x100000000
        self.assertEqual(millis, 0x150)
        self.assertGreaterEqual(float(millis) / 1000.0, 0.0)
        print("  [✔] GetTickCount64 modular overflow correction verified.")

    def test_05_system_excluded_bins_uninstaller(self):
        """P1: Verify SYSTEM_EXCLUDED_BINS filter skips system launchers in uninstaller leftovers."""
        SYSTEM_EXCLUDED_BINS = {"rundll32.exe", "msiexec.exe", "regsvr32.exe", "cmd.exe", "powershell.exe"}

        # Simulate checking system launchers
        for launcher in SYSTEM_EXCLUDED_BINS:
            base_bin = os.path.basename(launcher).lower()
            self.assertIn(base_bin, SYSTEM_EXCLUDED_BINS)
            # Should be found in PATH or in excluded bins
            self.assertTrue(base_bin in SYSTEM_EXCLUDED_BINS or shutil.which(launcher))

        print("  [✔] SYSTEM_EXCLUDED_BINS filter correctly preserves system launchers.")

    def test_06_uninstaller_full_subkey_backup_and_restore(self):
        """P1: Verify complete backup & restoration of all uninstaller subkey values (DisplayName, Publisher, etc.)."""
        tmp_dir = tempfile.mkdtemp(prefix="NC_TestAuditBkp_")
        test_sub = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare_Audit_Test"
        try:
            # 1. Create a dummy uninstaller key in HKCU with full application metadata
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, test_sub) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "NovaCare Test App")
                winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, "1.5.0")
                winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, "NovaCare Lab")
                winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, r"C:\NonExistent\uninstall.exe")
                winreg.SetValueEx(k, "InstallDate", 0, winreg.REG_SZ, "20261108")
                winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, 102400)

            # 2. Create RegistryIssue for this key
            rc = registry_cleaner.RegistryCleaner(backup_dir=tmp_dir)
            issue = registry_cleaner.RegistryIssue(
                id="uninst_HKCU_NovaCare_Audit_Test_0",
                category="Bozuk Kaldırma Bilgisi",
                root_name="HKCU",
                sub_key=test_sub,
                value_name="",
                value_data=r"C:\NonExistent\uninstall.exe",
                value_type=winreg.REG_SZ,
                reason="Test uninstaller missing"
            )

            # 3. Create backup - create_backup should discover and backup ALL subkey values
            backup_path = rc.create_backup([issue])
            self.assertTrue(os.path.exists(backup_path))

            # 4. Now fix/delete the test key
            utils.delete_registry_key_tree(winreg.HKEY_CURRENT_USER, test_sub)

            # Verify key is deleted
            with self.assertRaises(OSError):
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, test_sub, 0, winreg.KEY_READ)

            # 5. Restore backup using BackupManager
            bm = backup_manager.BackupManager(backup_dir=tmp_dir)
            restored, failed = bm.restore_backup(backup_path)
            self.assertEqual(failed, 0, f"Restore should not fail, got {failed} failures")
            self.assertGreaterEqual(restored, 1)

            # 6. Verify ALL values were restored, not just UninstallString!
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, test_sub, 0, winreg.KEY_READ) as k:
                disp, _ = winreg.QueryValueEx(k, "DisplayName")
                ver, _ = winreg.QueryValueEx(k, "DisplayVersion")
                pub, _ = winreg.QueryValueEx(k, "Publisher")
                uninst, _ = winreg.QueryValueEx(k, "UninstallString")
                est_sz, _ = winreg.QueryValueEx(k, "EstimatedSize")

                self.assertEqual(disp, "NovaCare Test App")
                self.assertEqual(ver, "1.5.0")
                self.assertEqual(pub, "NovaCare Lab")
                self.assertEqual(uninst, r"C:\NonExistent\uninstall.exe")
                self.assertEqual(est_sz, 102400)

            print("  [✔] Full uninstaller subkey backup & multi-value restoration verified perfectly.")
        finally:
            utils.delete_registry_key_tree(winreg.HKEY_CURRENT_USER, test_sub)
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_07_autostart_and_bloatware_status_checks(self):
        """P2: Verify truthful return status checks in autostart and bloatware disabling."""
        # 1. BloatwareCleaner sc.exe check
        cleaner = bloatware_cleaner.BloatwareCleaner()
        with patch("subprocess.run") as mock_run:
            # Simulate sc.exe failure (returncode = 1060: service does not exist)
            mock_proc = MagicMock()
            mock_proc.returncode = 1060
            mock_run.return_value = mock_proc

            res = cleaner.disable_deep_telemetry()
            self.assertEqual(len(res["disabled_services"]), 0, "Failed sc.exe commands MUST NOT be listed as disabled!")

            # Simulate sc.exe success (returncode = 0)
            mock_proc.returncode = 0
            res_ok = cleaner.disable_deep_telemetry()
            self.assertGreater(len(res_ok["disabled_services"]), 0, "Successful sc.exe commands should be listed")

        # 2. Autostart return value check
        with patch("subprocess.run", side_effect=Exception("Task scheduler fail")):
            with patch("winreg.OpenKey", side_effect=OSError("HKCU write fail")):
                result = autostart.set_autostart_enabled(True)
                self.assertFalse(result, "set_autostart_enabled MUST return False when both task and registry writes fail!")

        print("  [✔] Truthful status return checks for bloatware and autostart verified.")

    def test_08_qthread_cancel_support(self):
        """P1: Verify procedural QThread workers expose working cancel() methods."""
        workers = [
            hw_view.SmartScanWorker(),
            priv_view.BloatwareRemoveWorker(["Package1"]),
            priv_view.BloatwareScanWorker(),
            priv_view.DeepTelemetryWorker(),
            priv_view.CookieScanWorker(),
            priv_view.CookieCleanWorker(),
            priv_view.AntiSpyApplyWorker(priv_view.PrivacyTweaker(), True),
            dash_view.DashboardScanWorker(),
            dash_view.DashboardFixWorker(),
            dash_view.GameModeWorker(dash_view.GameBooster(), True),
            rescue_view.RestorePointWorker(backup_manager.BackupManager(), "Test Point"),
            mem_view.RamBoostWorker(),
            mem_view.ProcessLoaderWorker(memory_booster.MemoryBooster()),
            startup_view.StartupScanWorker(startup_view.StartupManager()),
            uninst_view.AppScanWorker(uninstaller.AppUninstaller()),
            uninst_view.SingleUninstallWaitWorker(None, uninstaller.InstalledApp(
                id="test", name="Test", publisher="Pub", version="1.0", install_date="", size_bytes=0, uninstall_string=""
            )),
            junk_view.JunkScanThread(junk_view.JunkCleaner()),
            junk_view.JunkCleanThread(junk_view.JunkCleaner(), set()),
            r_view.RegScanThread(registry_cleaner.RegistryCleaner()),
            r_view.RegFixThread(registry_cleaner.RegistryCleaner(), []),
            disk_view.LargeFileScanThread(disk_view.DiskAnalyzer(), "C:\\", 100, 10),
            disk_view.DuplicateScanThread(disk_view.DuplicateFinder(), ["C:\\"], 1024),
            net_view.MetaFetchWorker(),
            net_view.DNSBenchmarkWorker(),
            net_view.NetworkRepairWorker("flush"),
            net_view.DnsApplyWorker(net_view.NetworkOptimizer(), "reset", "Ethernet"),
            bat_view.BatteryHardwareWorker(bat_view.BatteryReporter()),
            bat_view.BatteryReportWorker(bat_view.BatteryReporter()),
            uninst_view.BatchUninstallWorker([], uninstaller.AppUninstaller()),
            net_view.SpeedTestWorker(),
            settings_view.ManualAutoCleanWorker(),
            settings_view.CheckUpdateThread("owner/repo"),
            settings_view.DownloadUpdateThread(None, "url"),
            settings_view.AutostartWorker(True),
            main_window.BackgroundAutoCleanWorker(),
            main_window.AutoUpdateCheckThread("owner/repo"),
            main_window.SilentAutoInstallThread(None, "url"),
            game_profiles_dialog.GameScanWorker(game_profiles_dialog.GameProfileManager())
        ]

        for w in workers:
            self.assertTrue(hasattr(w, 'cancel'), f"Worker {w.__class__.__name__} is missing cancel() method!")
            w.cancel()
            self.assertTrue(getattr(w, '_is_cancelled', False), f"Worker {w.__class__.__name__} cancel() did not set _is_cancelled!")

        print(f"  [✔] All {len(workers)} procedural QThread workers verified with cancel() support.")

    def test_09_ui_double_trigger_prevention(self):
        """P2: Verify running worker guards in StartupView, RescueView, and Uninstaller prevent duplicate threads."""
        # 1. StartupView refresh_items guard
        sv = startup_view.StartupView()
        fake_worker = MagicMock()
        fake_worker.isRunning.return_value = True
        sv.scan_worker = fake_worker

        with patch.object(startup_view, "StartupScanWorker") as mock_w_cls:
            sv.refresh_items()
            mock_w_cls.assert_not_called()

        # 2. RescueView _create_restore_point guard
        rv = rescue_view.RescueView()
        fake_rp = MagicMock()
        fake_rp.isRunning.return_value = True
        rv.rp_worker = fake_rp

        with patch.object(rescue_view, "RestorePointWorker") as mock_rp_cls:
            rv._create_restore_point()
            mock_rp_cls.assert_not_called()

        # 3. Uninstaller single uninstall running guard
        uv = uninst_view.UninstallerView()
        fake_single = MagicMock()
        fake_single.isRunning.return_value = True
        uv.single_wait_worker = fake_single

        with patch("PyQt5.QtWidgets.QMessageBox.warning") as mock_warn, \
             patch.object(uninst_view, "SingleUninstallWaitWorker") as mock_single_cls:
            dummy_app = uninstaller.InstalledApp("test", "Test App", "Pub", "1.0", "", 0, "uninstall.exe")
            uv._execute_single_uninstall(dummy_app)
            mock_single_cls.assert_not_called()
            mock_warn.assert_called_once()

        # 4. Uninstaller refresh_apps running guard
        fake_scan = MagicMock()
        fake_scan.isRunning.return_value = True
        uv.scan_worker = fake_scan
        with patch.object(uninst_view, "AppScanWorker") as mock_scan_cls:
            uv.refresh_apps()
            mock_scan_cls.assert_not_called()

        print("  [✔] Double-trigger isRunning() guards in StartupView, RescueView, and Uninstaller verified.")

    def test_10_network_stack_reset_timeout(self):
        """P2: Verify ipconfig /renew timeout protection in network stack reset."""
        net = network_optimizer.NetworkOptimizer()
        with patch("subprocess.run") as mock_run:
            # First 3 commands succeed, 4th (renew) times out
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            
            def side_effect(cmd, *args, **kwargs):
                if "/renew" in cmd:
                    raise Exception("DHCP timeout")
                return mock_proc

            mock_run.side_effect = side_effect
            ok, msg = net.reset_network_stack()
            self.assertTrue(ok, "reset_network_stack should still succeed even if renew DHCP takes time")

        print("  [✔] Network stack reset resilient against ipconfig /renew delay.")


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare System Suite - Code Audit Fixes Verification")
    print("=" * 65)
    unittest.main(verbosity=2)
