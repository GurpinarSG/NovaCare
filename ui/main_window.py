"""
NovaCare System Suite - Master Main Window
Sidebar navigation, stacked view switcher, and system tray integration.
"""
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QButtonGroup, QFrame, QSystemTrayIcon,
    QMenu, QAction, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from ui.styles import (
    MAIN_STYLESHEET, BG_SIDEBAR, BORDER_COLOR, COLOR_ACCENT,
    COLOR_SUCCESS, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from ui.views import (
    DashboardView,
    JunkView,
    RegistryView,
    StartupView,
    UninstallerView,
    MemoryView,
    DiskView,
    PrivacyView,
    RescueView,
    SettingsView
)
from core.utils import is_admin
from core.memory_booster import MemoryBooster
from core.config import ConfigManager
from core.updater import GitHubUpdater, UpdateInfo

class AutoUpdateCheckThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, repo: str):
        super().__init__()
        self.repo = repo

    def run(self):
        try:
            updater = GitHubUpdater(self.repo)
            info = updater.check_for_updates()
            self.finished.emit(info)
        except Exception as e:
            self.finished.emit(e)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.auto_check_thread = None
        self.setWindowTitle("NovaCare System Care Suite 2026")
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(MAIN_STYLESHEET)

        self._setup_icon()
        self._init_ui()
        self._setup_tray()
        self._setup_auto_update()

    def _setup_icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
            self.setWindowIcon(self.app_icon)
            return

        # Programmatically create a crisp, modern vector app icon
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#00D2FF"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 14, 14)

        p.setPen(QColor("#050B14"))
        font = QFont("Segoe UI", 32, QFont.Bold)
        p.setFont(font)
        p.drawText(pix.rect(), Qt.AlignCenter, "⚡")
        p.end()

        self.app_icon = QIcon(pix)
        self.setWindowIcon(self.app_icon)

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("SidebarWidget")
        sidebar.setFixedWidth(250)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 20, 12, 16)
        side_layout.setSpacing(6)

        # Branding
        brand_row = QHBoxLayout()
        logo_lbl = QLabel("⚡")
        logo_lbl.setStyleSheet("font-size: 26px; color: #00D2FF;")
        
        v_brand = QVBoxLayout()
        lbl_brand = QLabel("NovaCare")
        lbl_brand.setObjectName("SidebarBrand")
        lbl_sub = QLabel("ULTIMATE CARE 2026")
        lbl_sub.setObjectName("SidebarSubtitle")
        v_brand.addWidget(lbl_brand)
        v_brand.addWidget(lbl_sub)

        brand_row.addWidget(logo_lbl)
        brand_row.addSpacing(6)
        brand_row.addLayout(v_brand)
        brand_row.addStretch()
        side_layout.addLayout(brand_row)

        side_layout.addSpacing(18)

        # Nav Buttons & ButtonGroup
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        nav_items = [
            ("🚀  Tek Tıkla Bakım", 0),
            ("🧹  Gereksiz Dosya Temizliği", 1),
            ("🛠️  Kayıt Defteri Onarımı", 2),
            ("⚡  Başlangıç Yöneticisi", 3),
            ("📦  Program Kaldırıcı", 4),
            ("🧠  RAM & Süreç Yöneticisi", 5),
            ("📊  Disk Alanı Analizi", 6),
            ("🛡️  Gizlilik & Optimizasyon", 7),
            ("💾  Kurtarma Merkezi", 8),
            ("⚙️  Ayarlar & Güncelleme", 9)
        ]

        self.nav_buttons: list[QPushButton] = []
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)
            self.btn_group.addButton(btn, idx)
            side_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.btn_group.buttonClicked[int].connect(self._on_nav_clicked)

        side_layout.addStretch()

        # Admin Badge
        admin_card = QFrame()
        admin_card.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.35);
            border-radius: 8px;
            padding: 8px 10px;
        """)
        a_lay = QHBoxLayout(admin_card)
        a_lay.setContentsMargins(6, 4, 6, 4)
        lbl_admin = QLabel("🛡️  Yönetici Modu Aktif" if is_admin() else "⚠️  Standart Kullanıcı Modu")
        lbl_admin.setStyleSheet(f"color: {COLOR_SUCCESS if is_admin() else TEXT_SECONDARY}; font-weight: 700; font-size: 11px;")
        a_lay.addWidget(lbl_admin)
        side_layout.addWidget(admin_card)

        root_layout.addWidget(sidebar)

        # 2. Main Stacked Views Area
        self.stack = QStackedWidget()
        
        self.view_dashboard = DashboardView(self)
        self.view_junk = JunkView(self)
        self.view_registry = RegistryView(self)
        self.view_startup = StartupView(self)
        self.view_uninstaller = UninstallerView(self)
        self.view_memory = MemoryView(self)
        self.view_disk = DiskView(self)
        self.view_privacy = PrivacyView(self)
        self.view_rescue = RescueView(self)
        self.view_settings = SettingsView(self)

        self.stack.addWidget(self.view_dashboard)    # 0
        self.stack.addWidget(self.view_junk)         # 1
        self.stack.addWidget(self.view_registry)     # 2
        self.stack.addWidget(self.view_startup)      # 3
        self.stack.addWidget(self.view_uninstaller)  # 4
        self.stack.addWidget(self.view_memory)       # 5
        self.stack.addWidget(self.view_disk)         # 6
        self.stack.addWidget(self.view_privacy)      # 7
        self.stack.addWidget(self.view_rescue)       # 8
        self.stack.addWidget(self.view_settings)     # 9

        root_layout.addWidget(self.stack)

    def _on_nav_clicked(self, index: int):
        self.stack.setCurrentIndex(index)

    def _setup_auto_update(self):
        """Schedules a silent background update check 3 seconds after application launch."""
        if self.config.get("auto_check_updates", True):
            QTimer.singleShot(3000, self._run_background_update_check)

    def _run_background_update_check(self):
        repo = self.config.get("github_repo", "Gurpi/antigravity")
        self.auto_check_thread = AutoUpdateCheckThread(repo)
        self.auto_check_thread.finished.connect(self._on_auto_update_result)
        self.auto_check_thread.start()

    def _on_auto_update_result(self, result):
        if isinstance(result, UpdateInfo) and result.available:
            # Highlight Settings nav button
            if len(self.nav_buttons) > 9:
                self.nav_buttons[9].setText("⚙️  Ayarlar & Güncelleme 🔴")

            # Show system tray notification
            if hasattr(self, 'tray_icon'):
                self.tray_icon.showMessage(
                    "NovaCare Güncellemesi Mevcut",
                    f"Yeni NovaCare v{result.latest_version} sürümü yayınlandı. Güncellemek için tıklayın.",
                    QSystemTrayIcon.Information,
                    5000
                )

            # If user wants a notification dialog
            if self.config.get("notify_on_update", True):
                ans = QMessageBox.information(
                    self,
                    "Yeni Sürüm Mevcut!",
                    f"NovaCare için yeni bir sürüm yayınlandı!\n\n"
                    f"• Yeni Sürüm: v{result.latest_version}\n"
                    f"• Mevcut Sürüm: v{result.current_version}\n\n"
                    f"Güncelleme ayrıntılarını görmek ve yüklemek için Ayarlar & Güncelleme sekmesine gitmek ister misiniz?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ans == QMessageBox.Yes:
                    self.nav_buttons[9].setChecked(True)
                    self.stack.setCurrentIndex(9)
                    self.view_settings.check_for_updates_manual()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip("NovaCare System Care Suite 2026")

        menu = QMenu()
        menu.setStyleSheet(MAIN_STYLESHEET)

        act_show = QAction("⚡ NovaCare'i Göster", self)
        act_show.triggered.connect(self.showNormal)
        menu.addAction(act_show)

        act_boost = QAction("🧠 Hızlı RAM Temizle", self)
        act_boost.triggered.connect(self._tray_boost_ram)
        menu.addAction(act_boost)

        menu.addSeparator()

        act_exit = QAction("Çıkış", self)
        act_exit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_exit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def _tray_boost_ram(self):
        booster = MemoryBooster()
        freed, count = booster.optimize_ram()
        from core.utils import format_bytes
        self.tray_icon.showMessage(
            "RAM Hızlandırıldı",
            f"{format_bytes(freed)} bellek başarıyla boşaltıldı!",
            QSystemTrayIcon.Information,
            3000
        )
