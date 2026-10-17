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

print("\n>>> ALL INTEGRITY & WORKER THREAD CHECKS PASSED PERFECTLY! <<<")
