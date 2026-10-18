"""
NovaCare System Suite - Desktop Performance Widget
Translucent, draggable desktop mini performance dock featuring real-time
CPU %, RAM %, Network Speed telemetry, and 1-Click RAM optimization.
"""
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QAction, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QCursor, QFont
from core.hardware_monitor import HardwareMonitor
from core.memory_booster import MemoryBooster
from core.config import ConfigManager
from core.utils import format_bytes, log_debug

class DesktopPerformanceWidget(QWidget):
    visibilityChanged = pyqtSignal(bool)
    request_restore_main = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.config = ConfigManager()
        self.hw_monitor = HardwareMonitor()
        self.mem_booster = MemoryBooster()
        self.drag_position = None
        self._is_boosting = False

        self.setFixedSize(240, 185)
        self._init_ui()
        self._setup_position()

        # Autonomous real-time telemetry timer (every 1.8s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1800)
        self._update_telemetry()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Frosted glassmorphic card container
        self.card = QFrame(self)
        self.card.setObjectName("DesktopWidgetCard")
        self.card.setStyleSheet("""
            QFrame#DesktopWidgetCard {
                background-color: rgba(13, 20, 36, 0.92);
                border: 1px solid rgba(56, 189, 248, 0.45);
                border-radius: 14px;
            }
            QLabel {
                color: #FFFFFF;
                background: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 10, 14, 12)
        card_layout.setSpacing(6)

        # 1. Header (Title, Drag Handle, Close Button)
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 13px; color: #38BDF8; font-weight: bold;")
        lbl_title = QLabel("NovaCare Monitör")
        lbl_title.setStyleSheet("font-weight: 800; font-size: 11.5px; color: #38BDF8; letter-spacing: 0.5px;")

        hdr.addWidget(lbl_icon)
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Widget'ı Gizle (Tepsiden tekrar açabilirsiniz)")
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        btn_close.clicked.connect(self.hide)
        hdr.addWidget(btn_close)
        card_layout.addLayout(hdr)

        # Separator line
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.08);")
        card_layout.addWidget(sep)

        # 2. Real-time Telemetry Metrics
        # CPU
        self.lbl_cpu = QLabel("⚡ CPU: %0  (0.0 GHz)")
        self.lbl_cpu.setStyleSheet("font-size: 11px; font-weight: 600; color: #F8FAFC;")
        card_layout.addWidget(self.lbl_cpu)

        # RAM
        self.lbl_ram = QLabel("🧠 RAM: %0  (0.0 / 0.0 GB)")
        self.lbl_ram.setStyleSheet("font-size: 11px; font-weight: 600; color: #A78BFA;")
        card_layout.addWidget(self.lbl_ram)

        # Network Speed (Down / Up)
        self.lbl_net = QLabel("🌐 Ağ:  ↓ 0 KB/s   ↑ 0 KB/s")
        self.lbl_net.setStyleSheet("font-size: 10.5px; font-weight: 600; color: #34D399;")
        card_layout.addWidget(self.lbl_net)

        card_layout.addSpacing(2)

        # 3. 1-Click Fast RAM Boost Button
        self.btn_boost = QPushButton("⚡  Hızlı RAM Temizle")
        self.btn_boost.setObjectName("BtnWidgetRamBoost")
        self.btn_boost.setCursor(Qt.PointingHandCursor)
        self.btn_boost.setFixedHeight(28)
        self.btn_boost.setStyleSheet("""
            QPushButton#BtnWidgetRamBoost {
                background-color: #0284C7;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 700;
                border-radius: 6px;
                border: 1px solid #38BDF8;
            }
            QPushButton#BtnWidgetRamBoost:hover {
                background-color: #0369A1;
                border-color: #7DD3FC;
            }
            QPushButton#BtnWidgetRamBoost:pressed {
                background-color: #075985;
            }
        """)
        self.btn_boost.clicked.connect(self._on_quick_ram_boost)
        card_layout.addWidget(self.btn_boost)

        root.addWidget(self.card)

    def _setup_position(self):
        """Restores saved position or sets default to bottom-right corner of screen."""
        saved_pos = self.config.get("desktop_widget_pos")
        screen = QApplication.primaryScreen()
        if not screen:
            self.move(100, 100)
            return

        avail = screen.availableGeometry()

        if saved_pos and isinstance(saved_pos, list) and len(saved_pos) == 2:
            x, y = saved_pos
            # Ensure coordinates are within current screen boundaries
            if avail.x() <= x <= (avail.x() + avail.width() - self.width()) and \
               avail.y() <= y <= (avail.y() + avail.height() - self.height()):
                self.move(x, y)
                return

        # Default: Bottom-right corner (above Windows taskbar with 24px padding)
        default_x = avail.x() + avail.width() - self.width() - 24
        default_y = avail.y() + avail.height() - self.height() - 24
        self.move(default_x, default_y)

    def snap_to_corner(self):
        """Snaps widget back to bottom-right corner."""
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = avail.x() + avail.width() - self.width() - 24
            y = avail.y() + avail.height() - self.height() - 24
            self.move(x, y)
            self.config.set("desktop_widget_pos", [x, y])

    def _update_telemetry(self):
        """Pulls latest hardware telemetry and updates UI widgets."""
        if not self.isVisible():
            return
        try:
            stats = self.hw_monitor.get_hardware_stats()
            self.update_stats(stats)
        except Exception as e:
            log_debug(f"DesktopPerformanceWidget telemetry error: {e}")

    def update_stats(self, stats: dict):
        """Updates display labels with new hardware metrics."""
        cpu_pct = stats.get("cpu_percent", 0)
        cpu_freq = stats.get("cpu_freq_ghz", 0.0)
        cpu_temp = stats.get("cpu_temp")
        ram_pct = stats.get("ram_percent", 0)
        ram_used = stats.get("ram_used_gb", 0)
        ram_total = stats.get("ram_total_gb", 0)
        down_str = stats.get("net_down_str", "0 KB/s")
        up_str = stats.get("net_up_str", "0 KB/s")

        temp_str = f" | {cpu_temp:.0f}°C" if cpu_temp is not None else ""
        self.lbl_cpu.setText(f"⚡ CPU: %{cpu_pct:.0f}  ({cpu_freq:.1f} GHz{temp_str})")
        self.lbl_ram.setText(f"🧠 RAM: %{ram_pct:.0f}  ({ram_used} / {ram_total} GB)")
        self.lbl_net.setText(f"🌐 Ağ:  ↓ {down_str}   ↑ {up_str}")

    def _on_quick_ram_boost(self):
        """Executes 1-click RAM purge and displays success confirmation."""
        if self._is_boosting:
            return
        self._is_boosting = True
        self.btn_boost.setText("⏳ Temizleniyor...")
        self.btn_boost.setEnabled(False)

        freed_bytes, count = self.mem_booster.optimize_ram()
        freed_str = format_bytes(freed_bytes)

        self.btn_boost.setText(f"✨ +{freed_str} Boşaltıldı!")
        self.btn_boost.setStyleSheet("""
            QPushButton#BtnWidgetRamBoost {
                background-color: #047857;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: 700;
                border-radius: 6px;
                border: 1px solid #10B981;
            }
        """)

        # Refresh stats immediately
        QTimer.singleShot(400, self._update_telemetry)

        # Restore button after 2.5s
        def _restore():
            self.btn_boost.setText("⚡  Hızlı RAM Temizle")
            self.btn_boost.setStyleSheet("""
                QPushButton#BtnWidgetRamBoost {
                    background-color: #0284C7;
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #38BDF8;
                }
                QPushButton#BtnWidgetRamBoost:hover {
                    background-color: #0369A1;
                    border-color: #7DD3FC;
                }
            """)
            self.btn_boost.setEnabled(True)
            self._is_boosting = False

        QTimer.singleShot(2500, _restore)

    # Mouse & Window Events
    def mouseDoubleClickEvent(self, event):
        """Double clicking opens and focuses the NovaCare main suite."""
        self.request_restore_main.emit()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            new_pos = event.globalPos() - self.drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            # Persist window coordinates
            self.config.set("desktop_widget_pos", [self.x(), self.y()])
            event.accept()

    def contextMenuEvent(self, event):
        """Context menu on right-click."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #38BDF8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #0284C7;
                color: #FFFFFF;
            }
        """)

        act_open = QAction("⚡  NovaCare'i Aç", self)
        act_open.triggered.connect(self.request_restore_main.emit)
        menu.addAction(act_open)

        act_boost = QAction("🧠  Hızlı RAM Temizle", self)
        act_boost.triggered.connect(self._on_quick_ram_boost)
        menu.addAction(act_boost)

        act_snap = QAction("📍  Ekran Köşesine Hizala", self)
        act_snap.triggered.connect(self.snap_to_corner)
        menu.addAction(act_snap)

        menu.addSeparator()

        act_close = QAction("✕  Widget'ı Gizle", self)
        act_close.triggered.connect(self.hide)
        menu.addAction(act_close)

        menu.exec_(QCursor.pos())

    def showEvent(self, event):
        super().showEvent(event)
        self.visibilityChanged.emit(True)
        self._update_telemetry()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibilityChanged.emit(False)
