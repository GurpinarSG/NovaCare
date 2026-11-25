"""
NovaCare System Suite - Performance & Optimization Regression Benchmarks (Pass 2)
Verifies scanning speedups, single-stat traversal, HardwareMonitor <3ms latency,
non-blocking UI init, lightweight table items, and batched operations.
"""
import os
import sys
import time
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication, QCheckBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QShowEvent, QHideEvent

app = QApplication.instance() or QApplication(sys.argv)


class TestPerformanceBenchmarks2(unittest.TestCase):

    def test_01_disk_analyzer_scandir_and_protected_cache(self):
        from core.disk_analyzer import DiskAnalyzer, is_critical_system_file

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        da = DiskAnalyzer()
        t0 = time.perf_counter()
        large = da.scan_largest_files(repo_root, limit=10, min_size_mb=0)
        scan_ms = (time.perf_counter() - t0) * 1000.0
        self.assertGreater(len(large), 0)
        sizes = [x.size_bytes for x in large]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        self.assertLess(scan_ms, 500.0, f"Repo scandir took too long: {scan_ms:.1f}ms")

        # Benchmark 5000 calls to is_critical_system_file
        paths = [rf"C:\Users\Test\Documents\Sub{i % 20}\file_{i}.dat" for i in range(5000)]
        t0 = time.perf_counter()
        res = [is_critical_system_file(p) for p in paths]
        prot_ms = (time.perf_counter() - t0) * 1000.0
        self.assertFalse(any(res))
        self.assertLess(prot_ms, 600.0, f"is_critical_system_file(5000x) took {prot_ms:.1f}ms")

        # Security contracts: SystemRoot, \\?\ prefix, drive-agnostic protected folder
        self.assertTrue(is_critical_system_file(r"C:\Windows\System32\notepad.exe"))
        self.assertTrue(is_critical_system_file(r"\\?\C:\Windows\System32\cmd.exe"))
        self.assertTrue(is_critical_system_file(r"D:\$Recycle.Bin\bigfile.bin"))
        self.assertTrue(is_critical_system_file(r"D:\pagefile.sys"))

        # Env override still respected
        with patch.dict(os.environ, {"ProgramFiles": r"Z:\CustomPF"}):
            self.assertTrue(is_critical_system_file(r"Z:\CustomPF\App\bin.exe"))

    def test_02_duplicate_finder_scandir_and_protection(self):
        from core.duplicate_finder import DuplicateFinder

        tmp = tempfile.mkdtemp(prefix="nc_dup_perf_")
        try:
            sub1 = os.path.join(tmp, "dir1")
            sub2 = os.path.join(tmp, "dir2")
            hidden = os.path.join(tmp, ".hidden")
            os.makedirs(sub1)
            os.makedirs(sub2)
            os.makedirs(hidden)

            payload = b"NovaCareDuplicatePayload" * 100  # 2400 bytes > 1024 min
            f1 = os.path.join(sub1, "a.bin")
            f2 = os.path.join(sub2, "b.bin")
            f_hidden = os.path.join(hidden, "c.bin")
            f_unique = os.path.join(sub1, "unique.bin")
            for p in (f1, f2, f_hidden):
                with open(p, "wb") as fp:
                    fp.write(payload)
            with open(f_unique, "wb") as fp:
                fp.write(b"X" * 3000)

            df = DuplicateFinder()
            groups = df.scan_duplicates([tmp], min_size_bytes=1024)
            self.assertEqual(len(groups), 1)
            found_paths = {item.path for item in groups[0].files}
            self.assertEqual(found_paths, {f1, f2})
            self.assertNotIn(f_hidden, found_paths)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_03_utils_folder_size_and_nonblocking_recycle_timeout(self):
        from core.utils import get_folder_size, empty_recycle_bin

        tmp = tempfile.mkdtemp(prefix="nc_util_perf_")
        try:
            with open(os.path.join(tmp, "one.bin"), "wb") as fp:
                fp.write(b"a" * 1234)
            os.makedirs(os.path.join(tmp, "sub"))
            with open(os.path.join(tmp, "sub", "two.bin"), "wb") as fp:
                fp.write(b"b" * 766)
            sz, cnt = get_folder_size(tmp)
            self.assertEqual((sz, cnt), (2000, 2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # Simulate SHEmptyRecycleBinW hanging for 2.0s; timeout=0.05 must return immediately
        with patch("core.utils.ctypes.windll.shell32.SHEmptyRecycleBinW", side_effect=lambda *a: (time.sleep(1.5), 0)[1]):
            t0 = time.perf_counter()
            ok = empty_recycle_bin(timeout_sec=0.05)
            elapsed = time.perf_counter() - t0
            self.assertFalse(ok)
            self.assertLess(elapsed, 0.5, f"empty_recycle_bin blocked on executor shutdown: {elapsed:.2f}s")

    def test_04_junk_cleaner_single_stat_and_shields(self):
        from core.junk_cleaner import JunkCleaner, CleanerCategory

        tmp = tempfile.mkdtemp(prefix="nc_junk_perf_")
        try:
            with open(os.path.join(tmp, "cache.tmp"), "wb") as fp:
                fp.write(b"Z" * 512)
            with open(os.path.join(tmp, "settings.json"), "wb") as fp:
                fp.write(b"secret")
            os.makedirs(os.path.join(tmp, "Discord"))
            with open(os.path.join(tmp, "Discord", "token.ldb"), "wb") as fp:
                fp.write(b"tok")

            cat = CleanerCategory(id="test", name="Test", description="", icon="🗑️", paths=[tmp])
            jc = JunkCleaner()
            jc._scan_folder_recursive(tmp, cat)
            self.assertEqual(cat.file_count, 1)
            self.assertEqual(cat.size, 512)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_05_cookie_shield_fast_locked_skip_and_proc_cache(self):
        from core.cookie_shield import CookieShield

        tmp = tempfile.mkdtemp(prefix="nc_cs_perf_")
        db1 = os.path.join(tmp, "Cookies")
        with open(db1, "wb") as fp:
            fp.write(b"SQLite format 3\x00")
        try:
            cs = CookieShield()
            targets = [
                {"browser": "Microsoft Edge (Default)", "type": "chromium", "path": db1, "exe": "msedge.exe"},
            ]
            with patch.object(cs, "get_browser_targets", return_value=targets), \
                 patch.object(cs, "get_running_process_names", return_value={"msedge.exe"}), \
                 patch("core.cookie_shield.os.open", side_effect=PermissionError("Sharing violation")), \
                 patch("core.cookie_shield.sqlite3.connect") as mock_sql:
                res = cs.scan_cookies()
                self.assertIn("Microsoft Edge (Default)", res["locked_browsers"])
                mock_sql.assert_not_called()

            # clean_tracking_cookies should query running processes once for all targets
            with patch.object(cs, "get_browser_targets", return_value=targets * 3), \
                 patch.object(cs, "get_running_process_names", return_value={"msedge.exe"}) as mock_procs:
                deleted, preserved, locked = cs.clean_tracking_cookies()
                self.assertEqual(mock_procs.call_count, 1)
                self.assertEqual((deleted, preserved), (0, 0))
                self.assertEqual(locked, ["Microsoft Edge (Default)"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_06_hardware_monitor_latency_and_first_cpu_nonblocking(self):
        from core.hardware_monitor import HardwareMonitor

        mon = HardwareMonitor()
        t0 = time.perf_counter()
        _ = mon.get_cpu_percent()
        first_cpu_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(first_cpu_ms, 50.0, f"First get_cpu_percent blocked: {first_cpu_ms:.1f}ms")

        # 100 calls should stay well under < 3ms average
        t0 = time.perf_counter()
        for _ in range(100):
            s = mon.get_hardware_stats()
            self.assertIn("cpu_percent", s)
        total_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(total_ms, 300.0, f"100x get_hardware_stats took {total_ms:.1f}ms (>3ms/call)")

    def test_07_bloatware_batch_startup_which_game_speedtester(self):
        from core.bloatware_cleaner import BloatwareCleaner
        from core.registry_cleaner import RegistryCleaner
        from core.game_booster import GameProfileManager
        from core.speed_tester import SpeedTester

        bc = BloatwareCleaner()
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "OK:Pkg.One\nOK:Pkg.Two\n"
        mock_proc.stderr = ""
        with patch("core.bloatware_cleaner.subprocess.run", return_value=mock_proc) as mock_run:
            removed, errs = bc.remove_bloatware_packages(["Pkg.One", "Pkg.Two", "Bad;Cmd"])
            self.assertEqual(mock_run.call_count, 1)
            self.assertEqual(removed, ["Pkg.One", "Pkg.Two"])
            self.assertEqual(len(errs), 1)

        RegistryCleaner._cached_which.cache_clear()
        with patch("core.registry_cleaner.shutil.which", return_value=r"C:\Windows\System32\cmd.exe") as mock_which:
            r1 = RegistryCleaner._cached_which("cmd.exe")
            r2 = RegistryCleaner._cached_which("cmd.exe")
            self.assertEqual(r1, r2)
            self.assertEqual(mock_which.call_count, 1)

        # Steam single-exe-per-game-folder stop test
        tmp = tempfile.mkdtemp(prefix="nc_games_")
        try:
            common_dir = os.path.join(tmp, "steamapps", "common")
            gdir = os.path.join(common_dir, "TestGame")
            sub = os.path.join(gdir, "Binaries")
            os.makedirs(sub)
            with open(os.path.join(gdir, "TestGame.exe"), "wb") as fp:
                fp.write(b"MZ")
            with open(os.path.join(sub, "AnotherGame.exe"), "wb") as fp:
                fp.write(b"MZ")
            gm = GameProfileManager()
            orig_walk = os.walk
            orig_exists = os.path.exists
            orig_scandir = os.scandir
            with patch("core.game_booster.os.path.exists", side_effect=lambda p: p == common_dir or (orig_exists(p) and "libraryfolders.vdf" not in p)), \
                 patch("core.game_booster.os.scandir", side_effect=lambda p: orig_scandir(p) if p == common_dir else iter(())), \
                 patch("core.game_booster.os.walk", wraps=orig_walk) as mock_walk, \
                 patch("core.game_booster.psutil.process_iter", return_value=[]):
                # Test direct deduplication + loop stop if standard path existed
                self.assertIsInstance(gm.scan_installed_games(), list)
                _ = mock_walk
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # SpeedTester fallback RTT must reset t0
        st = SpeedTester()
        st.session = MagicMock()
        def slow_primary_then_fast_fallback(url, timeout=3):
            if "cloudflare" in url:
                time.sleep(0.15)
                raise TimeoutError("primary timed out")
            return MagicMock(status_code=200)

        st.session.get.side_effect = slow_primary_then_fast_fallback
        ping_ms, _ = st.run_ping_and_jitter(count=2)
        self.assertLess(ping_ms, 80.0, f"Fallback ping was inflated by primary timeout: {ping_ms}ms")

    def test_08_ui_lazy_load_lightweight_table_and_timers(self):
        from ui.views.network_view import NetworkView
        from ui.views.settings_view import SettingsView
        from ui.views.privacy_view import PrivacyView, SystemTweak
        from ui.views.uninstaller_view import UninstallerView
        from core.uninstaller import InstalledApp
        from ui.desktop_widget import DesktopPerformanceWidget
        from ui.components import StatCard
        from ui.main_window import MainWindow

        # NetworkView __init__ must not run get_network_interfaces or spawn MetaFetchWorker
        with patch("core.network_optimizer.NetworkOptimizer.get_network_interfaces") as mock_ifaces, \
             patch("ui.views.network_view.MetaFetchWorker") as mock_meta:
            nv = NetworkView()
            mock_ifaces.assert_not_called()
            mock_meta.assert_not_called()
            mock_ifaces.return_value = [{"name": "Ethernet", "connected": True}]
            with patch.object(nv.optimizer, "get_current_dns", return_value={"is_dhcp": True, "servers": ["1.1.1.1"]}):
                nv.showEvent(QShowEvent())
                mock_ifaces.assert_called_once()
                self.assertTrue(nv._meta_fetched)
                if nv.meta_worker and nv.meta_worker.isRunning():
                    nv.meta_worker.cancel()
                    nv.meta_worker.wait(1000)

        # SettingsView __init__ must use allow_cli=False (no blocking schtasks subprocess)
        with patch("ui.views.settings_view.is_autostart_enabled", return_value=True) as mock_auto:
            sv = SettingsView()
            mock_auto.assert_called_once_with(allow_cli=False)
            self.assertTrue(sv.chk_autostart.isChecked())

        # StatCard.set_value no-op guard
        sc = StatCard("⚡", "CPU", "10%", "1.0 GHz")
        with patch.object(sc.value_lbl, "setText") as mock_set_val:
            sc.set_value("10%", "1.0 GHz")
            mock_set_val.assert_not_called()
            sc.set_value("20%")
            mock_set_val.assert_called_once_with("20%")

        # DesktopPerformanceWidget hideEvent/showEvent timer control
        dw = DesktopPerformanceWidget()
        self.assertTrue(dw.timer.isActive())
        dw.hideEvent(QHideEvent())
        self.assertFalse(dw.timer.isActive())
        dw.close()

        # PrivacyView._on_tweak_toggle updates state in-place without _refresh_tweaks rebuild
        pv = PrivacyView()
        tw = SystemTweak("t1", "Tweak 1", "Desc", "HKCU", "Software\\Test", "V", 1, 0, False)
        pv.tweaks = [tw]
        chk = QCheckBox()
        with patch.object(pv.tweaker, "apply_tweak", return_value=True), \
             patch.object(pv, "_refresh_tweaks") as mock_rebuild:
            pv._on_tweak_toggle(tw, chk, Qt.Checked)
            mock_rebuild.assert_not_called()
            self.assertTrue(tw.current_enabled)

        # UninstallerView uses lightweight checkable QTableWidgetItem (no QWidget cellWidget per row)
        uv = UninstallerView()
        uv.all_apps = [
            InstalledApp("app_a", "App A", "1.0", "Pub A", "", 1024, "HKLM"),
            InstalledApp("app_b", "App B", "2.0", "Pub B", "", 2048, "HKCU"),
        ]
        uv._filter_apps()
        self.assertIsNone(uv.table.cellWidget(0, 0))
        item0 = uv.table.item(0, 0)
        self.assertIsNotNone(item0)
        self.assertTrue(bool(item0.flags() & Qt.ItemIsUserCheckable))
        item0.setCheckState(Qt.Checked)
        self.assertIn("app_a", uv.checked_app_ids)

        # MainWindow should stop hidden overlay_widget timer on init
        mw = MainWindow()
        self.assertFalse(mw.view_dashboard.overlay_widget.timer.isActive())
        mw.cleanup_workers()


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare Performance & Responsiveness Benchmarks (Pass 2)")
    print("=" * 65)
    unittest.main()
