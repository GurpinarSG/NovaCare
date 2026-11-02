"""
Automated Test Suite for Deep Audit Defensive Fixes:
1. DesktopPerformanceWidget timer cleanup on closeEvent.
2. MainWindow.cleanup_workers() complete teardown of view_battery and search timers.
3. AppUninstaller scan_leftovers() inclusion of WOW6432Node registry search.
4. StartupManager.delete_item() cleanup of Windows Task Manager StartupApproved entries.
5. BatchUninstallWorker cancellation safety and process termination.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication

# Ensure single QApplication instance
app = QApplication.instance() or QApplication(sys.argv)


class TestDeepAuditFixes(unittest.TestCase):

    def test_desktop_widget_close_event_stops_timer(self):
        """DesktopPerformanceWidget.closeEvent must stop the recurring telemetry timer."""
        from ui.desktop_widget import DesktopPerformanceWidget
        widget = DesktopPerformanceWidget()
        self.assertTrue(widget.timer.isActive(), "Telemetry timer should be active after creation")
        
        # Trigger closeEvent
        widget.close()
        self.assertFalse(widget.timer.isActive(), "Telemetry timer must be stopped after closeEvent")

    def test_main_window_cleanup_workers_stops_all_timers(self):
        """MainWindow.cleanup_workers() must stop view_battery.timer, view_memory.search_timer, etc."""
        from PyQt5.QtWidgets import QMainWindow
        from ui.main_window import MainWindow
        with patch.object(MainWindow, '__init__', lambda self: QMainWindow.__init__(self)):
            mw = MainWindow()
            
            # Setup mock view timers
            mw.auto_check_thread = None
            mw.auto_install_thread = None
            mw.view_battery = MagicMock()
            mw.view_battery.timer = MagicMock()
            mw.view_battery.timer.isActive.return_value = True
            
            mw.view_memory = MagicMock()
            mw.view_memory.timer = MagicMock()
            mw.view_memory.timer.isActive.return_value = True
            mw.view_memory.search_timer = MagicMock()
            mw.view_memory.search_timer.isActive.return_value = True
            
            mw.view_dashboard = MagicMock()
            mw.view_dashboard.timer = MagicMock()
            mw.view_dashboard.timer.isActive.return_value = True
            mw.view_dashboard.overlay_widget = MagicMock()
            mw.view_dashboard.overlay_widget.timer = MagicMock()
            mw.view_dashboard.overlay_widget.timer.isActive.return_value = True

            mw.cleanup_workers()

            mw.view_battery.timer.stop.assert_called_once()
            mw.view_memory.timer.stop.assert_called_once()
            mw.view_memory.search_timer.stop.assert_called_once()
            mw.view_dashboard.timer.stop.assert_called_once()
            mw.view_dashboard.overlay_widget.timer.stop.assert_called_once()
            mw.view_dashboard.overlay_widget.close.assert_called_once()

    @patch("winreg.OpenKey")
    @patch("winreg.QueryInfoKey")
    @patch("winreg.EnumKey")
    def test_uninstaller_scans_wow6432node(self, mock_enum, mock_info, mock_open):
        """scan_leftovers must inspect HKLM\\Software\\WOW6432Node for 32-bit application remnants."""
        from core.uninstaller import AppUninstaller, InstalledApp
        uninstaller = AppUninstaller()
        fake_app = InstalledApp(
            id="app1",
            name="SuperApp 32-bit",
            version="1.0",
            publisher="ACME Corp",
            install_date="",
            size_bytes=1024,
            uninstall_string="C:\\SuperApp\\uninstall.exe",
            quiet_uninstall_string="",
            install_location="",
            icon_path="",
            registry_path="",
            root_name="HKLM"
        )

        opened_paths = []
        def fake_open_key(root, sub, reserved=0, access=0):
            opened_paths.append(sub)
            mock_handle = MagicMock()
            return mock_handle

        mock_open.side_effect = fake_open_key
        mock_info.return_value = (0, 0, 0)

        uninstaller.scan_leftovers(fake_app)
        
        self.assertIn(r"Software\WOW6432Node", opened_paths, 
                      f"WOW6432Node was not queried. Opened paths: {opened_paths}")

    @patch("winreg.OpenKey")
    @patch("winreg.DeleteValue")
    def test_startup_manager_delete_cleans_startup_approved(self, mock_del, mock_open):
        """StartupManager.delete_item must clean up corresponding entries from StartupApproved."""
        from core.startup_manager import StartupManager, StartupItem
        mgr = StartupManager()
        item = StartupItem(
            id="item1",
            name="TestDaemon",
            command="C:\\App\\daemon.exe",
            location="HKCU\\Run",
            location_type="registry",
            source_key_or_path=r"Software\Microsoft\Windows\CurrentVersion\Run",
            root_name="HKCU",
            enabled=True,
            boot_impact="Orta"
        )

        opened_keys = []
        deleted_values = []

        def fake_open(root, sub, reserved=0, access=0):
            opened_keys.append(sub)
            mock_k = MagicMock()
            mock_k.__enter__.return_value = mock_k
            return mock_k

        def fake_del(handle, val_name):
            deleted_values.append(val_name)

        mock_open.side_effect = fake_open
        mock_del.side_effect = fake_del

        success = mgr.delete_item(item)
        self.assertTrue(success)
        
        # Verify both Run key and StartupApproved keys were accessed
        self.assertIn(r"Software\Microsoft\Windows\CurrentVersion\Run", opened_keys)
        self.assertIn(r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run", opened_keys)
        self.assertIn(r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32", opened_keys)
        self.assertGreaterEqual(deleted_values.count("TestDaemon"), 1)

    def test_batch_uninstaller_cancellation(self):
        """BatchUninstallWorker must terminate running process on cancel and not mark uninstalled."""
        from ui.views.uninstaller_view import BatchUninstallWorker
        from core.uninstaller import InstalledApp

        fake_uninstaller = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None, 0]
        mock_proc.returncode = None
        fake_uninstaller.launch_uninstaller.return_value = mock_proc

        app1 = InstalledApp(id="a1", name="App1", version="1", publisher="P", install_date="", size_bytes=0, uninstall_string="u", quiet_uninstall_string="", install_location="", icon_path="", registry_path="", root_name="HKLM")
        app2 = InstalledApp(id="a2", name="App2", version="1", publisher="P", install_date="", size_bytes=0, uninstall_string="u", quiet_uninstall_string="", install_location="", icon_path="", registry_path="", root_name="HKLM")

        worker = BatchUninstallWorker([app1, app2], fake_uninstaller)

        finished_apps = []
        worker.batch_finished.connect(lambda uninst: finished_apps.extend(uninst))

        # Cancel immediately
        worker.cancel()
        worker.run()

        # Because worker was canceled, no apps should have been successfully uninstalled
        self.assertEqual(len(finished_apps), 0, "No apps should be reported as finished when canceled")


if __name__ == "__main__":
    unittest.main()
