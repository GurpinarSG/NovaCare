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
    COLOR_WARNING, COLOR_DANGER,
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
    NetworkView,
    BatteryView,
    RescueView,
    SettingsView
)
from core.utils import is_admin
from core.memory_booster import MemoryBooster
from core.config import ConfigManager
from core.updater import GitHubUpdater, UpdateInfo
from core.auto_cleaner import AutoCleaner
import time

def log_debug(msg: str):
    try:
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NovaCare')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'startup.log'), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

class BackgroundAutoCleanWorker(QThread):
    finished = pyqtSignal(dict)

    def run(self):
        cleaner = AutoCleaner()
        res = cleaner.execute_cleanup()
        self.finished.emit(res)

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
        log_debug("MainWindow.__init__ started")
        self.config = ConfigManager()
        self.auto_check_thread = None
        self.auto_install_thread = None
        self.prepared_update_batch = None
        self._visited_tabs: set[int] = {0}
        self.setWindowTitle("NovaCare System Care Suite 2026")

        # Responsive geometry calculation based on primary monitor's available workspace
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_w = min(1220, max(980, int(avail.width() * 0.85)))
            target_h = min(750, max(620, int(avail.height() * 0.88)))
            self.resize(target_w, target_h)
            self.setGeometry(
                avail.x() + (avail.width() - target_w) // 2,
                avail.y() + (avail.height() - target_h) // 2,
                target_w,
                target_h
            )
        else:
            self.resize(1180, 720)

        self.setMinimumSize(940, 580)

        # Apply user/system theme
        log_debug("MainWindow: applying theme...")
        self.current_theme = self.config.get("theme", "system")
        init_qss = get_stylesheet(self.current_theme)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.setStyleSheet(init_qss)
        self.setStyleSheet(init_qss)

        log_debug("MainWindow: setting up icon...")
        self._setup_icon()
        log_debug("MainWindow: setting up UI...")
        self._init_ui()
        log_debug("MainWindow: setting up tray...")
        self._setup_tray()
        log_debug("MainWindow: setting up auto update...")
        self._setup_auto_update()
        log_debug("MainWindow: setting up auto clean...")
        self._setup_auto_clean()
        log_debug("MainWindow.__init__ finished successfully")

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
        sidebar.setFixedWidth(240)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 16, 10, 14)
        side_layout.setSpacing(3)

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

        side_layout.addSpacing(14)

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
            ("🛡️  Gizlilik & Bloatware", 7),
            ("🌐  Ağ & DNS Optimize Edici", 8),
            ("🔋  Pil & Güç Sağlığı", 9),
            ("💾  Kurtarma Merkezi", 10),
            ("⚙️  Ayarlar & Güncelleme", 11)
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
        has_admin = is_admin()
        admin_card = QFrame()
        admin_card.setCursor(Qt.PointingHandCursor)
        admin_card.setToolTip("Yönetici izinlerini görüntülemek ve yapılandırmak için tıklayın")
        bg_col = "rgba(16, 185, 129, 0.12)" if has_admin else "rgba(251, 191, 36, 0.15)"
        border_col = "rgba(16, 185, 129, 0.35)" if has_admin else "rgba(251, 191, 36, 0.40)"
        text_col = COLOR_SUCCESS if has_admin else COLOR_WARNING
        admin_card.setStyleSheet(f"""
            background-color: {bg_col};
            border: 1px solid {border_col};
            border-radius: 8px;
            padding: 8px 10px;
        """)
        a_lay = QHBoxLayout(admin_card)
        a_lay.setContentsMargins(6, 4, 6, 4)
        lbl_admin = QLabel("🛡️  Yönetici Modu Aktif" if has_admin else "⚠️  Standart Mod (Yükselt)")
        lbl_admin.setStyleSheet(f"color: {text_col}; font-weight: 700; font-size: 11px;")
        a_lay.addWidget(lbl_admin)
        admin_card.mousePressEvent = lambda ev: self._navigate_to_settings_admin()
        side_layout.addWidget(admin_card)

        root_layout.addWidget(sidebar)

        # 2. Main Stacked Views Area
        self.stack = QStackedWidget()
        
        log_debug("Init view: DashboardView")
        self.view_dashboard = DashboardView(self)
        log_debug("Init view: JunkView")
        self.view_junk = JunkView(self)
        log_debug("Init view: RegistryView")
        self.view_registry = RegistryView(self)
        log_debug("Init view: StartupView")
        self.view_startup = StartupView(self)
        log_debug("Init view: UninstallerView")
        self.view_uninstaller = UninstallerView(self)
        log_debug("Init view: MemoryView")
        self.view_memory = MemoryView(self)
        log_debug("Init view: DiskView")
        self.view_disk = DiskView(self)
        log_debug("Init view: PrivacyView")
        self.view_privacy = PrivacyView(self)
        log_debug("Init view: NetworkView")
        self.view_network = NetworkView(self)
        log_debug("Init view: BatteryView")
        self.view_battery = BatteryView(self)
        log_debug("Init view: RescueView")
        self.view_rescue = RescueView(self)
        log_debug("Init view: SettingsView")
        self.view_settings = SettingsView(self)
        log_debug("All views created successfully.")

        self.stack.addWidget(self.view_dashboard)    # 0
        self.stack.addWidget(self.view_junk)         # 1
        self.stack.addWidget(self.view_registry)     # 2
        self.stack.addWidget(self.view_startup)      # 3
        self.stack.addWidget(self.view_uninstaller)  # 4
        self.stack.addWidget(self.view_memory)       # 5
        self.stack.addWidget(self.view_disk)         # 6
        self.stack.addWidget(self.view_privacy)      # 7
        self.stack.addWidget(self.view_network)      # 8
        self.stack.addWidget(self.view_battery)      # 9
        self.stack.addWidget(self.view_rescue)       # 10
        self.stack.addWidget(self.view_settings)     # 11

        root_layout.addWidget(self.stack)

    def _on_nav_clicked(self, index: int):
        self.stack.setCurrentIndex(index)
        is_first_visit = index not in self._visited_tabs
        self._visited_tabs.add(index)

        if index == 3 and is_first_visit and hasattr(self.view_startup, 'refresh_items'):
            self.view_startup.refresh_items()
        elif index == 4 and is_first_visit and hasattr(self.view_uninstaller, 'refresh_apps'):
            self.view_uninstaller.refresh_apps()
        elif index == 5 and hasattr(self.view_memory, 'refresh_processes'):
            self.view_memory.refresh_processes()
        elif index == 7 and is_first_visit and hasattr(self.view_privacy, 'lazy_init_scan'):
            self.view_privacy.lazy_init_scan()
        elif index == 8 and is_first_visit and hasattr(self.view_network, '_load_network_info'):
            self.view_network._load_network_info()
        elif index == 9 and hasattr(self.view_battery, 'refresh_metrics'):
            self.view_battery.refresh_metrics(query_hardware=False)

    def _navigate_to_settings_admin(self):
        if len(self.nav_buttons) > 11:
            self.nav_buttons[11].setChecked(True)
            self.stack.setCurrentIndex(11)

    def apply_theme(self, theme_mode: str):
        """Applies theme dynamically across the entire application and all views."""
        self.current_theme = theme_mode
        self.config.set("theme", theme_mode)
        qss = get_stylesheet(theme_mode)
        app_inst = QApplication.instance()
        if app_inst:
            app_inst.setStyleSheet(qss)
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
            if len(self.nav_buttons) > 10:
                self.nav_buttons[10].setText("⚙️  Ayarlar & Güncelleme 🔴")

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
                        self.nav_buttons[11].setChecked(True)
                        self.stack.setCurrentIndex(11)
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

    def _setup_auto_clean(self):
        """Initializes automated background cleaning monitor and scheduler."""
        self.auto_clean_worker = None
        # Initial check 12 seconds after launch
        QTimer.singleShot(12000, self._check_and_run_auto_clean)
        # Recurring check every 1 hour (3600 seconds)
        self.auto_clean_timer = QTimer(self)
        self.auto_clean_timer.timeout.connect(self._check_and_run_auto_clean)
        self.auto_clean_timer.start(3600 * 1000)

    def _check_and_run_auto_clean(self):
        cleaner = AutoCleaner()
        should_run, reason = cleaner.should_trigger()
        if should_run:
            self.auto_clean_worker = BackgroundAutoCleanWorker()
            self.auto_clean_worker.finished.connect(self._on_background_auto_clean_finished)
            self.auto_clean_worker.start()

    def _on_background_auto_clean_finished(self, res: dict):
        if self.config.get("auto_clean_notify", True) and hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
            total = res.get("total_freed_str", "0 B")
            files = res.get("cleaned_files_count", 0)
            self.tray_icon.showMessage(
                "NovaCare Otomatik Bakım Tamamlandı",
                f"Sisteminiz optimize edildi: {total} alan boşaltıldı ({files} dosya temizlendi).",
                QSystemTrayIcon.Information,
                4000
            )

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
        act_exit.triggered.connect(self._exit_application)
        self.tray_menu.addAction(act_exit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _exit_application(self):
        self._force_exit = True
        QApplication.instance().quit()

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
        if not getattr(self, '_force_exit', False) and self.config.get("close_to_tray", True):
            event.ignore()
            self.hide()
            from core.memory_booster import MemoryBooster
            MemoryBooster.trim_own_memory()
            if hasattr(self, 'tray_icon') and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "NovaCare Arka Planda Çalışıyor",
                    "NovaCare sisteminizi korumaya devam etmek için sistem tepsisine küçültüldü.",
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
            if hasattr(self, 'auto_clean_worker') and self.auto_clean_worker and self.auto_clean_worker.isRunning():
                self.auto_clean_worker.quit()
                self.auto_clean_worker.wait(300)
            if hasattr(self.view_dashboard, 'overlay_widget') and self.view_dashboard.overlay_widget:
                self.view_dashboard.overlay_widget.close()
        except Exception:
            pass

        event.accept()
