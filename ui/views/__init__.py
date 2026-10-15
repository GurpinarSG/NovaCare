"""
NovaCare System Suite - Views Package
"""
from ui.views.dashboard_view import DashboardView
from ui.views.junk_view import JunkView
from ui.views.registry_view import RegistryView
from ui.views.startup_view import StartupView
from ui.views.uninstaller_view import UninstallerView
from ui.views.memory_view import MemoryView
from ui.views.disk_view import DiskView
from ui.views.privacy_view import PrivacyView
from ui.views.rescue_view import RescueView
from ui.views.settings_view import SettingsView

__all__ = [
    "DashboardView",
    "JunkView",
    "RegistryView",
    "StartupView",
    "UninstallerView",
    "MemoryView",
    "DiskView",
    "PrivacyView",
    "RescueView",
    "SettingsView"
]
