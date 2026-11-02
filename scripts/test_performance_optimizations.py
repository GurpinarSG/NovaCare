"""
NovaCare System Suite 2026 - Performance & Optimization Verification Suite
Validates async worker threads, non-blocking UI operations, CPU/battery idling,
caching mechanisms, and disk I/O optimizations.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

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
from PyQt5.QtGui import QShowEvent, QHideEvent
app = QApplication.instance() or QApplication(sys.argv)

from ui.views.memory_view import RamBoostWorker, MemoryView
from ui.views.network_view import DnsApplyWorker, NetworkView
from ui.views.battery_view import BatteryReportWorker
from ui.views.privacy_view import AntiSpyApplyWorker
from ui.views.settings_view import AutostartWorker, SettingsView
from core.network_optimizer import DNSServerInfo
from ui.desktop_widget import DesktopPerformanceWidget
from ui.main_window import MainWindow
from core.hardware_monitor import HardwareMonitor
from core.game_booster import GameProfileManager
from core.duplicate_finder import DuplicateFinder
from core.junk_cleaner import JunkCleaner, JunkFilePath, CleanerCategory
from core.cookie_shield import CookieShield


class TestPerformanceOptimizations(unittest.TestCase):

    def test_01_ram_boost_worker_async(self):
        """Verify RamBoostWorker executes optimize_ram in thread and emits signals."""
        mock_booster = MagicMock()
        mock_booster.optimize_ram.return_value = (104857600, 42)

        worker = RamBoostWorker(mock_booster)
        progress_msgs = []
        results = []

        worker.progress.connect(progress_msgs.append)
        worker.finished.connect(lambda f, c: results.append((f, c)))

        worker.start()
        worker.wait(3000)
        app.processEvents()

        mock_booster.optimize_ram.assert_called_once()
        self.assertEqual(len(progress_msgs), 1)
        self.assertEqual(results, [(104857600, 42)])

    def test_02_memory_view_boost_ram_non_blocking(self):
        """Verify MemoryView._boost_ram initiates worker without blocking GUI."""
        view = MemoryView()
        view.booster = MagicMock()
        view.booster.optimize_ram.return_value = (52428800, 15)

        with patch("ui.views.memory_view.QMessageBox.information") as mock_info:
            view._boost_ram()
            self.assertIsNotNone(view.boost_worker)
            self.assertTrue(view.boost_worker.isRunning() or view.boost_worker.isFinished())
            view.boost_worker.wait(3000)
            app.processEvents()
            mock_info.assert_called_once()
            self.assertTrue(view.btn_boost.isEnabled())

    def test_03_desktop_widget_async_boost_and_game_mode(self):
        """Verify DesktopPerformanceWidget RAM boost & game mode use async workers."""
        widget = DesktopPerformanceWidget()
        widget.mem_booster = MagicMock()
        widget.mem_booster.optimize_ram.return_value = (33554432, 8)

        widget._on_quick_ram_boost()
        self.assertTrue(widget._is_boosting)
        self.assertIsNotNone(widget.ram_boost_worker)
        widget.ram_boost_worker.wait(3000)
        app.processEvents()
        self.assertIn("✨", widget.btn_boost.text())

        # Test async game mode toggle
        widget.game_booster = MagicMock()
        widget.game_booster.is_game_mode_active.return_value = False
        widget.game_booster.activate.return_value = {"active": True}

        widget._toggle_game_mode()
        self.assertIsNotNone(widget.game_mode_worker)
        widget.game_mode_worker.wait(3000)
        app.processEvents()
        widget.game_booster.activate.assert_called_once()

    def test_04_dns_apply_worker_async(self):
        """Verify DnsApplyWorker applies DNS settings in background thread."""
        mock_opt = MagicMock()
        mock_opt.set_dns.return_value = (True, "DNS Güncellendi")
        mock_opt.reset_dns_to_dhcp.return_value = (True, "DHCP Güncellendi")

        worker = DnsApplyWorker(mock_opt, "set", "Ethernet", "1.1.1.1", "1.0.0.1", "Cloudflare")
        results = []
        worker.finished.connect(lambda ok, msg, act, ad, nm: results.append((ok, msg, act, ad, nm)))

        worker.start()
        worker.wait(3000)
        app.processEvents()

        mock_opt.set_dns.assert_called_once_with("Ethernet", "1.1.1.1", "1.0.0.1")
        self.assertEqual(results, [(True, "DNS Güncellendi", "set", "Ethernet", "Cloudflare")])

        # Test reset to DHCP
        worker2 = DnsApplyWorker(mock_opt, "reset_dhcp", "Ethernet")
        results2 = []
        worker2.finished.connect(lambda ok, msg, act, ad, nm: results2.append((ok, msg, act, ad, nm)))
        worker2.start()
        worker2.wait(3000)
        app.processEvents()
        mock_opt.reset_dns_to_dhcp.assert_called_once_with("Ethernet")
        self.assertEqual(results2, [(True, "DHCP Güncellendi", "reset_dhcp", "Ethernet", "")])

    def test_05_battery_report_worker_async(self):
        """Verify BatteryReportWorker generates HTML report without freezing."""
        mock_reporter = MagicMock()
        mock_reporter.generate_html_report.return_value = r"C:\Temp\BatteryReport.html"

        worker = BatteryReportWorker(mock_reporter)
        results = []
        worker.finished.connect(lambda ok, path: results.append((ok, path)))

        worker.start()
        worker.wait(3000)
        app.processEvents()

        mock_reporter.generate_html_report.assert_called_once()
        self.assertEqual(results, [(True, r"C:\Temp\BatteryReport.html")])

    def test_06_antispy_apply_worker_async(self):
        """Verify AntiSpyApplyWorker runs sequential net stop/sc commands asynchronously."""
        mock_tweaker = MagicMock()
        mock_tweaker.apply_all_anti_spy.return_value = (11, 0, ["DiagTrack", "dmwappushservice"])

        worker = AntiSpyApplyWorker(mock_tweaker, enable=True)
        results = []
        worker.finished.connect(lambda s, f, svcs, en: results.append((s, f, svcs, en)))

        worker.start()
        worker.wait(3000)
        app.processEvents()

        mock_tweaker.apply_all_anti_spy.assert_called_once_with(enable=True)
        self.assertEqual(results, [(11, 0, ["DiagTrack", "dmwappushservice"], True)])

    def test_07_autostart_worker_async(self):
        """Verify AutostartWorker manages schtasks in background without GUI hitch."""
        with patch("ui.views.settings_view.set_autostart", return_value=True) as mock_set:
            worker = AutostartWorker(enable=True)
            results = []
            worker.finished.connect(lambda en, ok: results.append((en, ok)))

            worker.start()
            worker.wait(3000)
            app.processEvents()

            mock_set.assert_called_once_with(True)
            self.assertEqual(results, [(True, True)])

    def test_08_hardware_monitor_throttling_and_backoff(self):
        """Verify HardwareMonitor set_throttled and ACPI backoff sleep logic."""
        mon = HardwareMonitor()
        mon.set_throttled(True)
        self.assertTrue(getattr(mon, "_is_throttled", False))

        mon.set_throttled(False)
        self.assertFalse(getattr(mon, "_is_throttled", False))

        # Check existing backoff values
        self.assertEqual(HardwareMonitor._calc_acpi_backoff_sleep(0), 5.0)
        self.assertEqual(HardwareMonitor._calc_acpi_backoff_sleep(1), 15.0)
        self.assertEqual(HardwareMonitor._calc_acpi_backoff_sleep(3), 60.0)
        self.assertEqual(HardwareMonitor._calc_acpi_backoff_sleep(6), 300.0)

    def test_09_game_profile_manager_in_memory_caching(self):
        """Verify GameProfileManager caches validated profiles in memory to avoid 3s disk I/O."""
        mgr = GameProfileManager()
        # Save profiles to manager without global mock leakage
        mgr.save_profiles([
            {"id": "test_game", "name": "Test Game", "exe": "game.exe", "path": sys.executable, "auto_boost": True}
        ])

        with patch("os.path.exists", return_value=True) as mock_exists:
            profs1 = mgr.get_profiles()
            self.assertEqual(len(profs1), 1)
            initial_calls = mock_exists.call_count

            # Subsequent fetch within 60s returns cached in memory without calling os.path.exists again
            profs2 = mgr.get_profiles()
            self.assertEqual(len(profs2), 1)
            self.assertEqual(mock_exists.call_count, initial_calls)

            # Saving profiles invalidates cache immediately
            mgr.save_profiles([{"id": "new_game", "name": "New", "exe": "new.exe"}])
            self.assertEqual(mgr._cached_profiles[0]["id"], "new_game")

    def test_10_main_window_pause_resume_timers_on_idling(self):
        """Verify MainWindow pauses view timers and throttles HardwareMonitor when minimized/tray."""
        win = MainWindow()

        # Simulate minimizing / hiding
        win._pause_view_timers()
        self.assertTrue(HardwareMonitor()._is_throttled)

        # Restore
        win._resume_view_timers()
        self.assertFalse(HardwareMonitor()._is_throttled)

        # Cleanup
        win.cleanup_workers()

    def test_11_duplicate_finder_small_file_optimization_and_frozenset(self):
        """Verify DuplicateFinder uses frozenset and reuses partial hash for files <= 8192 bytes."""
        self.assertIsInstance(DuplicateFinder.PROTECTED_DIR_PATTERNS, frozenset)

        finder = DuplicateFinder()
        # Create temp dir with two identical small files (<= 8192 bytes)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            f1 = os.path.join(td, "a.txt")
            f2 = os.path.join(td, "b.txt")
            content = b"Small file content for MD5 verification test 12345"
            with open(f1, "wb") as f:
                f.write(content)
            with open(f2, "wb") as f:
                f.write(content)

            with patch.object(DuplicateFinder, "_calc_full_md5", wraps=DuplicateFinder._calc_full_md5) as mock_full:
                groups = finder.scan_duplicates([td], min_size_bytes=10)
                self.assertEqual(len(groups), 1)
                self.assertEqual(len(groups[0].files), 2)
                # _calc_full_md5 should NOT be called for files <= 8192 bytes!
                mock_full.assert_not_called()

    def test_12_junk_cleaner_precomputed_size_tracking(self):
        """Verify JunkFilePath preserves string properties and clean_categories avoids getsize syscalls."""
        path_str = r"C:\Windows\Temp\test.tmp"
        junk_p = JunkFilePath(path_str, 2048)

        self.assertIsInstance(junk_p, str)
        self.assertEqual(junk_p, path_str)
        self.assertTrue(junk_p.startswith(r"C:\Windows"))
        self.assertEqual(junk_p.size, 2048)

        cleaner = JunkCleaner()
        test_cat = CleanerCategory(
            id="test_opt",
            name="Test",
            description="",
            icon="🧪",
            found_files=[junk_p]
        )
        cleaner.categories = [test_cat]

        with patch("core.junk_cleaner.safe_remove_file", return_value=True), \
             patch("os.path.getsize") as mock_getsize:
            freed, cleaned, failed = cleaner.clean_categories({"test_opt"})
            self.assertEqual(freed, 2048)
            self.assertEqual(cleaned, 1)
            # os.path.getsize must NOT be called since size was already tracked
            mock_getsize.assert_not_called()

    def test_13_cookie_shield_fast_fail_on_running_browser(self):
        """Verify CookieShield scan_cookies uses fast 0.05s timeout when browser is running."""
        shield = CookieShield()
        shield.get_browser_targets = MagicMock(return_value=[
            {
                'browser': 'Google Chrome',
                'exe': 'chrome.exe',
                'type': 'chromium',
                'profile': 'Default',
                'path': r'C:\NonExistent\Cookies'
            }
        ])
        shield.get_running_process_names = MagicMock(return_value={'chrome.exe'})

        with patch("sqlite3.connect") as mock_connect:
            mock_connect.side_effect = Exception("database is locked")
            res = shield.scan_cookies()
            self.assertIn("Google Chrome", res['locked_browsers'])
            mock_connect.assert_called_once_with(r'C:\NonExistent\Cookies', timeout=0.05)

    def test_14_main_window_hide_and_show_events(self):
        """Verify MainWindow hideEvent and showEvent correctly pause and resume view timers and throttle state."""
        win = MainWindow()

        # hideEvent should pause timers and throttle hardware monitor
        win.hideEvent(QHideEvent())
        self.assertTrue(HardwareMonitor()._is_throttled)

        # showEvent should resume timers and unthrottle hardware monitor
        win.showEvent(QShowEvent())
        self.assertFalse(HardwareMonitor()._is_throttled)

        win.cleanup_workers()

    def test_15_settings_view_autostart_toggle_and_failure_rollback(self):
        """Verify SettingsView autostart toggle executes asynchronously and rolls back on failure."""
        view = SettingsView()

        # 1. Failure case: set_autostart returns False
        with patch("ui.views.settings_view.set_autostart", return_value=False), \
             patch("ui.views.settings_view.QMessageBox.warning") as mock_warn:
            view.chk_autostart.setChecked(True)
            self.assertFalse(view.chk_autostart.isEnabled())
            self.assertIsNotNone(view.autostart_worker)

            view.autostart_worker.wait(3000)
            app.processEvents()

            mock_warn.assert_called_once()
            self.assertTrue(view.chk_autostart.isEnabled())
            self.assertFalse(view.chk_autostart.isChecked())
            self.assertFalse(view.config.get("autostart_on_boot"))

        # 2. Success case: set_autostart returns True
        with patch("ui.views.settings_view.set_autostart", return_value=True):
            view.config.set("widget_autostart_prompted", True)
            view.chk_autostart.setChecked(True)
            view.autostart_worker.wait(3000)
            app.processEvents()

            self.assertTrue(view.chk_autostart.isEnabled())
            self.assertTrue(view.chk_autostart.isChecked())
            self.assertTrue(view.config.get("autostart_on_boot"))

    def test_16_dns_apply_ui_locks_and_table_controls(self):
        """Verify NetworkView disables adapter combo and table during DNS change and restores them."""
        view = NetworkView()
        view.optimizer = MagicMock()
        view.optimizer.set_dns.return_value = (True, "DNS Ayarlandı")

        view.combo_adapters.clear()
        view.combo_adapters.addItem("Ethernet0", "Ethernet0")
        view.combo_adapters.setCurrentIndex(0)

        srv = DNSServerInfo("google", "Google", "Google", "8.8.8.8", "8.8.4.4", "Hızlı")
        with patch("ui.views.network_view.QMessageBox.information"):
            view._apply_dns(srv)
            self.assertFalse(view.combo_adapters.isEnabled())
            self.assertFalse(view.table.isEnabled())

            self.assertIsNotNone(view.dns_apply_worker)
            view.dns_apply_worker.wait(3000)
            app.processEvents()

            self.assertTrue(view.combo_adapters.isEnabled())
            self.assertTrue(view.table.isEnabled())

    def test_17_game_profile_manager_class_level_cache(self):
        """Verify GameProfileManager synchronizes in-memory cache across distinct manager instances."""
        mgr1 = GameProfileManager()
        mgr2 = GameProfileManager()

        test_data = [
            {"id": "sync_test_id", "name": "Sync Test Game", "exe": "sync_game.exe", "path": sys.executable, "auto_boost": True}
        ]
        mgr1.save_profiles(test_data)

        profs2 = mgr2.get_profiles()
        self.assertEqual(len(profs2), 1)
        self.assertEqual(profs2[0]["id"], "sync_test_id")

    def test_18_main_window_cleanup_workers_all_new_threads(self):
        """Verify MainWindow.cleanup_workers safely quits and waits for all new asynchronous workers."""
        win = MainWindow()

        mock_workers = []
        for i in range(6):
            mw = MagicMock()
            mw.isRunning.return_value = True
            mock_workers.append(mw)

        win._tray_boost_worker = mock_workers[0]
        win.view_memory.boost_worker = mock_workers[1]
        win.view_battery.report_worker = mock_workers[2]
        win.view_privacy.antispy_worker = mock_workers[3]
        win.view_network.dns_apply_worker = mock_workers[4]
        win.view_settings.autostart_worker = mock_workers[5]

        win.cleanup_workers()

        for mw in mock_workers:
            mw.quit.assert_called_once()
            mw.wait.assert_called_once_with(300)


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare Performance & Responsiveness Optimization Tests")
    print("=" * 65)
    unittest.main()
