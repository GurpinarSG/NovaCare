"""
NovaCare System Suite - Master Main Window
Sidebar navigation, stacked view switcher, and system tray integration.
"""
import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QButtonGroup, QFrame, QSystemTrayIcon,
    QMenu, QAction, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from ui.styles import (
    get_stylesheet, get_active_theme_colors, MAIN_STYLESHEET,
    BG_SIDEBAR, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
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

class SilentAutoInstallThread(QThread):
    finished = pyqtSignal(str) # batch_path or error

    def __init__(self, updater: GitHubUpdater, download_url: str, new_commit_sha: str = "", new_version: str = ""):
        super().__init__()
        self.updater = updater
        self.download_url = download_url
        self.new_commit_sha = new_commit_sha
        self.new_version = new_version

    def run(self):
        try:
            batch = self.updater.download_and_prepare_update(
                self.download_url,
                new_commit_sha=self.new_commit_sha,
                new_version=self.new_version
            )
            self.finished.emit(batch)
        except Exception as e:
            self.finished.emit(f"ERROR:{e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.auto_check_thread = None
        self.auto_install_thread = None
        self.prepared_update_batch = None
        self.setWindowTitle("NovaCare System Care Suite 2026")
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)

        # Apply user/system theme
        self.current_theme = self.config.get("theme", "system")
        self.setStyleSheet(get_stylesheet(self.current_theme))

        self._setup_icon()
        self._init_ui()
        self._setup_tray()
        self._setup_auto_update()

    def _setup_icon(self):
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
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

    def apply_theme(self, theme_mode: str):
        """Applies theme dynamically across the entire application and all views."""
        self.current_theme = theme_mode
        self.config.set("theme", theme_mode)
        qss = get_stylesheet(theme_mode)
        self.setStyleSheet(qss)
        if hasattr(self, 'tray_menu'):
            self.tray_menu.setStyleSheet(qss)
        if hasattr(self, 'view_dashboard') and hasattr(self.view_dashboard, 'gauge'):
            self.view_dashboard.gauge.update()

    def _setup_auto_update(self):
        """Schedules a silent background update check 3 seconds after application launch."""
        if self.config.get("auto_check_updates", True):
            QTimer.singleShot(3000, self._run_background_update_check)

    def _run_background_update_check(self):
        repo = self.config.get("github_repo", "GurpinarSG/NovaCare")
        self.auto_check_thread = AutoUpdateCheckThread(repo)
        self.auto_check_thread.finished.connect(self._on_auto_update_result)
        self.auto_check_thread.start()

    def _on_auto_update_result(self, result):
        if isinstance(result, UpdateInfo) and result.available:
            # Highlight Settings nav button
            if len(self.nav_buttons) > 9:
                self.nav_buttons[9].setText("⚙️  Ayarlar & Güncelleme 🔴")

            # If auto install is enabled, download and prepare in background automatically!
            if self.config.get("auto_install_updates", True) and result.download_url:
                updater = GitHubUpdater(self.config.get("github_repo", "GurpinarSG/NovaCare"))
                self.auto_install_thread = SilentAutoInstallThread(
                    updater,
                    result.download_url,
                    new_commit_sha=result.new_commit_sha,
                    new_version=result.latest_version
                )
                self.auto_install_thread.finished.connect(lambda batch: self._on_auto_install_finished(batch, result))
                self.auto_install_thread.start()
            else:
                # Show system tray notification
                if hasattr(self, 'tray_icon'):
                    self.tray_icon.showMessage(
                        "NovaCare Güncellemesi Mevcut",
                        f"Yeni sürüm ({result.latest_version}) yayınlandı.",
                        QSystemTrayIcon.Information,
                        5000
                    )

                if self.config.get("notify_on_update", True):
                    ans = QMessageBox.information(
                        self,
                        "Yeni Sürüm Mevcut!",
                        f"NovaCare için yeni bir sürüm yayınlandı ({result.latest_version}).\n\n"
                        f"Güncelleme ayrıntılarını görmek ve yüklemek için Ayarlar & Güncelleme sekmesine gitmek ister misiniz?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if ans == QMessageBox.Yes:
                        self.nav_buttons[9].setChecked(True)
                        self.stack.setCurrentIndex(9)
                        self.view_settings.check_for_updates_manual()

    def _on_auto_install_finished(self, batch_path: str, info: UpdateInfo):
        if batch_path.startswith("ERROR:"):
            return

        self.prepared_update_batch = batch_path

        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "NovaCare Güncellemesi Hazır",
                f"Yeni sürüm ({info.latest_version}) arka planda otomatik olarak hazırlandı.",
                QSystemTrayIcon.Information,
                5000
            )

        if self.config.get("notify_on_update", True):
            ans = QMessageBox.question(
                self,
                "Güncelleştirme Hazır!",
                f"NovaCare için yeni sürüm ({info.latest_version}) arka planda otomatik olarak indirildi ve hazırlandı!\n\n"
                "Güncellemeyi şimdi uygulamak ve uygulamayı yeniden başlatmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ans == QMessageBox.Yes:
                updater = GitHubUpdater(self.config.get("github_repo", "GurpinarSG/NovaCare"))
                updater.launch_updater_and_exit(batch_path)

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip("NovaCare System Care Suite 2026")

        self.tray_menu = QMenu()
        self.tray_menu.setStyleSheet(get_stylesheet(self.current_theme))

        act_show = QAction("⚡  NovaCare'i Göster", self)
        act_show.triggered.connect(self.showNormal)
        self.tray_menu.addAction(act_show)

        act_boost = QAction("🧠  Hızlı RAM Temizle", self)
        act_boost.triggered.connect(self._tray_boost_ram)
        self.tray_menu.addAction(act_boost)

        self.tray_menu.addSeparator()

        act_exit = QAction("❌  Çıkış", self)
        act_exit.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(self.tray_menu)
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

    def closeEvent(self, event):
        if self.config.get("close_to_tray", False):
            event.ignore()
            self.hide()
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "NovaCare Çalışıyor",
                    "NovaCare arka planda sisteminizi korumaya devam ediyor.",
                    QSystemTrayIcon.Information,
                    2000
                )
            return

        # Clean shutdown of worker threads
        try:
            if self.auto_check_thread and self.auto_check_thread.isRunning():
                self.auto_check_thread.quit()
                self.auto_check_thread.wait(300)
            if self.auto_install_thread and self.auto_install_thread.isRunning():
                self.auto_install_thread.quit()
                self.auto_install_thread.wait(300)
            if hasattr(self.view_memory, 'loader_worker') and self.view_memory.loader_worker and self.view_memory.loader_worker.isRunning():
                self.view_memory.loader_worker.quit()
                self.view_memory.loader_worker.wait(300)
            if hasattr(self.view_uninstaller, 'scan_worker') and self.view_uninstaller.scan_worker and self.view_uninstaller.scan_worker.isRunning():
                self.view_uninstaller.scan_worker.quit()
                self.view_uninstaller.scan_worker.wait(300)
        except Exception:
            pass

        event.accept()
