"""
NovaCare System Suite - General Health & Hardware Diagnostics View
Unified view combining Physical Disk S.M.A.R.T. diagnostics, hardware sensors,
and battery wear & power telemetry into a single comprehensive health category.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PyQt5.QtCore import Qt
from core.battery_reporter import is_battery_present
from ui.views.hardware_health_view import HardwareHealthView
from ui.views.battery_view import BatteryView
from ui.styles import get_active_theme_colors

class GeneralHealthView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.has_battery = is_battery_present()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(14)

        # Header
        lbl_title = QLabel("Genel Sistem Sağlığı & Donanım Teşhisi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Fiziksel SSD/HDD disk sağlığı, S.M.A.R.T. güvenilirlik sayaçları, donanım sıcaklıkları ve güç/batarya durumunu tek merkezden takip edin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Tabs Container
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 1. Disk Health & S.M.A.R.T. Hardware View
        self.view_hardware = HardwareHealthView(self)
        self.tabs.addTab(self.view_hardware, "💾  Disk Sağlığı & S.M.A.R.T.")

        # 2. Battery & Power Health (only for laptops/battery devices)
        if self.has_battery:
            self.view_battery = BatteryView(self)
            self.tabs.addTab(self.view_battery, "🔋  Pil & Güç Sağlığı")
        else:
            self.view_battery = None
            # On desktop without battery, hide tab bar for pure full-width experience
            self.tabs.tabBar().setVisible(False)

        main_layout.addWidget(self.tabs)

    def on_tab_activated(self):
        """Triggered when Genel Sağlık is clicked in sidebar."""
        if hasattr(self.view_hardware, 'on_activated'):
            self.view_hardware.on_activated()
        if self.view_battery and hasattr(self.view_battery, 'on_activated'):
            self.view_battery.on_activated()

    def set_sub_tab(self, index: int):
        """Navigate to a specific sub-tab (0: Disk Health, 1: Battery Health)."""
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)
