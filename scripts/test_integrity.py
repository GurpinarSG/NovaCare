"""
NovaCare System Suite - Integrity & Concurrency Verification Test
"""
import sys
import os

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

# Import all core modules
import core.utils
import core.config
import core.security
import core.junk_cleaner
import core.registry_cleaner
import core.privacy_tweaker
import core.startup_manager
import core.memory_booster
import core.game_booster
import core.hardware_monitor
import core.disk_analyzer
import core.network_optimizer
import core.battery_reporter
import core.bloatware_cleaner
import core.cookie_shield
import core.backup_manager
import core.uninstaller
import core.auto_cleaner
import core.updater
import core.autostart

print("✓ All core modules imported successfully.")

# Import all UI modules
import ui.styles
import ui.components
import ui.views.dashboard_view
import ui.views.junk_view
import ui.views.registry_view
import ui.views.startup_view
import ui.views.uninstaller_view
import ui.views.memory_view
import ui.views.disk_view
import ui.views.privacy_view
import ui.views.network_view
import ui.views.battery_view
import ui.views.rescue_view
import ui.views.settings_view
import ui.main_window

print("✓ All UI modules imported successfully.")

# Test Junk Cleaner scan
jc = core.junk_cleaner.JunkCleaner()
cats = jc.scan_all()
print(f"✓ Junk Cleaner scanned {len(cats)} categories successfully.")

# Test Registry Cleaner scan
rc = core.registry_cleaner.RegistryCleaner()
issues = rc.scan_all()
print(f"✓ Registry Cleaner scanned {len(issues)} issues successfully.")

# Test Hardware Monitor
hm = core.hardware_monitor.HardwareMonitor()
stats = hm.get_hardware_stats()
print(f"✓ Hardware stats: CPU={stats['cpu_percent']}%, RAM={stats['ram_percent']}%.")

# Test DashboardScanWorker directly
w = ui.views.dashboard_view.DashboardScanWorker()
w.run()
print("✓ DashboardScanWorker completed run without error.")

# Test RegScanThread
rw = ui.views.registry_view.RegScanThread(rc)
rw.run()
print("✓ RegScanThread completed run without error.")

# Test DNSBenchmarkWorker
dw = ui.views.network_view.DNSBenchmarkWorker()
dw.run()
print("✓ DNSBenchmarkWorker completed run without error.")

# Test StartupScanWorker
sm = core.startup_manager.StartupManager()
sw = ui.views.startup_view.StartupScanWorker(sm)
sw.run()
print("✓ StartupScanWorker completed run without error.")

# Test BatteryHardwareWorker
br = core.battery_reporter.BatteryReporter()
bw = ui.views.battery_view.BatteryHardwareWorker(br)
bw.run()
print("✓ BatteryHardwareWorker completed run without error.")

# Test SmartReporter & Hardware Health
import core.smart_reporter
import ui.views.hardware_health_view
import ui.desktop_widget
import ui.game_profiles_dialog

sr = core.smart_reporter.SmartReporter()
disks = sr.get_disks_health()
print(f"✓ SmartReporter scanned {len(disks)} physical disks successfully.")

# Test GameProfileManager
gpm = core.game_booster.GameProfileManager()
profs = gpm.get_profiles()
print(f"✓ GameProfileManager loaded {len(profs)} profiles successfully.")

# Test DesktopPerformanceWidget instantiation
dw = ui.desktop_widget.DesktopPerformanceWidget()
dw.update_stats(stats)
print("✓ DesktopPerformanceWidget instantiated and updated successfully.")

# Test Version Consistency
from core.config import load_base_version, CURRENT_VERSION
from scripts.installer_wizard import _load_app_version

base_v = load_base_version()
assert base_v == "1.2.7", f"Expected version 1.2.7, got {base_v}"
assert CURRENT_VERSION == "1.2.7", f"Expected CURRENT_VERSION 1.2.7, got {CURRENT_VERSION}"
wizard_v = _load_app_version()
assert wizard_v == "1.2.7", f"Expected wizard version 1.2.7, got {wizard_v}"
print(f"✓ Version consistency verified across modules: v{base_v}")

# Test MainWindow instantiation and teardown
mw = ui.main_window.MainWindow()
print(f"✓ MainWindow instantiated with {len(mw.nav_buttons)} nav buttons and {mw.stack.count()} views.")

# Test all tab transitions
for idx in range(mw.stack.count()):
    mw._on_nav_clicked(idx)
print(f"✓ All {mw.stack.count()} views navigated and rendered successfully.")

# Teardown workers cleanly for test exit
mw.cleanup_workers()
mw.close()
app.processEvents()

print("\n>>> ALL INTEGRITY & WORKER THREAD CHECKS PASSED PERFECTLY! <<<")
os._exit(0)
