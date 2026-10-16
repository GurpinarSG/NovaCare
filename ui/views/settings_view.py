"""
NovaCare System Suite - Settings & Updater View
Allows manual update checks, automatic update configuration, GitHub repository customization,
and 1-click update installation.
"""
import os
import sys
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QLineEdit, QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QMessageBox, QFrame, QScrollArea, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.config import ConfigManager, CURRENT_VERSION
from core.updater import GitHubUpdater, UpdateInfo
from core.auto_cleaner import AutoCleaner
from core.utils import format_bytes, is_admin, restart_as_admin
from core.security import mask_token
from core.autostart import is_autostart_enabled, set_autostart
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class ManualAutoCleanWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.cleaner = AutoCleaner()

    def run(self):
        res = self.cleaner.execute_cleanup()
        self.finished.emit(res)

class CheckUpdateThread(QThread):
    finished = pyqtSignal(object) # UpdateInfo or Exception

    def __init__(self, repo: str, token: str = "", mode: str = "branch"):
        super().__init__()
        self.repo = repo
        self.token = token
        self.mode = mode

    def run(self):
        updater = GitHubUpdater(self.repo, token=self.token)
        try:
            info = updater.check_for_updates(mode=self.mode)
            self.finished.emit(info)
        except Exception as e:
            self.finished.emit(e)

class DownloadUpdateThread(QThread):
    progress = pyqtSignal(int, int) # downloaded, total
    finished = pyqtSignal(str)      # batch_path or error

    def __init__(self, updater: GitHubUpdater, download_url: str, new_commit_sha: str = "", new_version: str = ""):
        super().__init__()
        self.updater = updater
        self.download_url = download_url
        self.new_commit_sha = new_commit_sha
        self.new_version = new_version

    def run(self):
        try:
            batch_path = self.updater.download_and_prepare_update(
                self.download_url,
                new_commit_sha=self.new_commit_sha,
                new_version=self.new_version,
                progress_callback=lambda d, t: self.progress.emit(d, t)
            )
            self.finished.emit(batch_path)
        except Exception as e:
            self.finished.emit(f"ERROR:{e}")

class SettingsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.updater = GitHubUpdater(self.config.get("github_repo"))
        self.latest_update_info: UpdateInfo | None = None
        self.check_thread = None
        self.download_thread = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header
        lbl_title = QLabel("Ayarlar ve Güncelleştirme Merkezi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("En son güvenlik, performans ve sistem güncellemelerini denetleyin, tercihlerinizi yönetin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Scroll Area for spacious layout (fully transparent background)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent; background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)

        # 1. Update Card
        card_update = QFrame()
        card_update.setObjectName("CardFrame")
        u_layout = QVBoxLayout(card_update)
        u_layout.setContentsMargins(22, 20, 22, 20)
        u_layout.setSpacing(16)

        # Section Title
        lbl_u_title = QLabel("🔄  Yazılım ve Sürüm Güncelleştirmesi")
        lbl_u_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        u_layout.addWidget(lbl_u_title)

        # Version status row
        ver_row = QHBoxLayout()
        self.lbl_cur_ver = QLabel(f"Yüklü Sürüm: <b>{self.config.get_display_version()}</b>")
        self.lbl_cur_ver.setStyleSheet("font-size: 14px;")

        self.lbl_status_badge = QLabel("🟢  Sürümünüz Güncel")
        self.lbl_status_badge.setStyleSheet(f"""
            background-color: rgba(16, 185, 129, 0.15);
            color: {COLOR_SUCCESS};
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 6px;
        """)

        ver_row.addWidget(self.lbl_cur_ver)
        ver_row.addSpacing(16)
        ver_row.addWidget(self.lbl_status_badge)
        ver_row.addStretch()
        u_layout.addLayout(ver_row)

        # Last checked timestamp
        last_chk = self.config.get("last_update_check", "Henüz denetlenmedi")
        self.lbl_last_checked = QLabel(f"Son Güncelleme Denetimi: {last_chk}")
        self.lbl_last_checked.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        u_layout.addWidget(self.lbl_last_checked)

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_check_now = QPushButton("🔍  Güncelleştirmeleri Şimdi Denetle")
        self.btn_check_now.setProperty("class", "primary-btn")
        self.btn_check_now.setCursor(Qt.PointingHandCursor)
        self.btn_check_now.clicked.connect(self.check_for_updates_manual)

        self.btn_changelog = QPushButton("📜  Sürüm Güncelleme Notları")
        self.btn_changelog.setCursor(Qt.PointingHandCursor)
        self.btn_changelog.clicked.connect(self._toggle_changelog_display)

        btn_row.addWidget(self.btn_check_now)
        btn_row.addWidget(self.btn_changelog)
        btn_row.addStretch()
        u_layout.addLayout(btn_row)

        # Changelog / Release Notes Display Frame
        self.panel_changelog = QFrame()
        self.panel_changelog.setObjectName("SubCardFrame")
        self.panel_changelog.setStyleSheet("""
            QFrame#SubCardFrame {
                background-color: rgba(14, 22, 38, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)
        cl_layout = QVBoxLayout(self.panel_changelog)
        cl_layout.setContentsMargins(14, 12, 14, 12)
        cl_layout.setSpacing(10)

        cl_header = QHBoxLayout()
        lbl_cl_title = QLabel(f"📋  Son Sürüm Güncelleme Notları (v{CURRENT_VERSION})")
        lbl_cl_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #00D2FF;")

        btn_cl_full = QPushButton("Tüm Geçmişi Aç...")
        btn_cl_full.setCursor(Qt.PointingHandCursor)
        btn_cl_full.setStyleSheet("font-size: 11px; padding: 4px 10px;")
        btn_cl_full.clicked.connect(self._show_full_changelog_dialog)

        cl_header.addWidget(lbl_cl_title)
        cl_header.addStretch()
        cl_header.addWidget(btn_cl_full)
        cl_layout.addLayout(cl_header)

        self.txt_recent_changelog = QTextEdit()
        self.txt_recent_changelog.setReadOnly(True)
        self.txt_recent_changelog.setFixedHeight(140)
        self.txt_recent_changelog.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 15, 29, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 6px;
                color: #F8FAFC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                line-height: 1.4;
                padding: 8px;
            }
        """)
        cl_layout.addWidget(self.txt_recent_changelog)
        u_layout.addWidget(self.panel_changelog)
        self._load_recent_changelog()

        # Automatic update toggles
        self.chk_auto = QCheckBox("Uygulama açılışında güncellemeleri otomatik olarak denetle")
        self.chk_auto.setChecked(self.config.get("auto_check_updates", True))
        self.chk_auto.stateChanged.connect(lambda s: self.config.set("auto_check_updates", s == Qt.Checked))
        u_layout.addWidget(self.chk_auto)

        self.chk_auto_install = QCheckBox("⚡  Yeni sürüm çıktığında güncellemeyi otomatik indir ve arka planda yükle")
        self.chk_auto_install.setChecked(self.config.get("auto_install_updates", True))
        self.chk_auto_install.stateChanged.connect(lambda s: self.config.set("auto_install_updates", s == Qt.Checked))
        u_layout.addWidget(self.chk_auto_install)

        self.chk_notify = QCheckBox("Yeni sürüm tespit edildiğinde veya hazırlandığında bildirim göster")
        self.chk_notify.setChecked(self.config.get("notify_on_update", True))
        self.chk_notify.stateChanged.connect(lambda s: self.config.set("notify_on_update", s == Qt.Checked))
        u_layout.addWidget(self.chk_notify)

        content_layout.addWidget(card_update)

        # 2. Theme & Appearance Card
        card_theme = QFrame()
        card_theme.setObjectName("CardFrame")
        t_layout = QVBoxLayout(card_theme)
        t_layout.setContentsMargins(22, 20, 22, 20)
        t_layout.setSpacing(14)

        lbl_t_title = QLabel("🎨  Tema ve Görünüm Tercihi")
        lbl_t_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        t_layout.addWidget(lbl_t_title)

        lbl_t_sub = QLabel("Program renk ve kontrast görünümünü bilgisayarınızla tam uyumlu çalışacak şekilde ayarlayın.")
        lbl_t_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        lbl_t_sub.setWordWrap(True)
        t_layout.addWidget(lbl_t_sub)

        # Radio buttons for theme
        self.theme_group = QButtonGroup(self)
        theme_row = QHBoxLayout()
        theme_row.setSpacing(18)

        current_theme = self.config.get("theme", "system")

        self.rb_system = QRadioButton("🖥️  Sistem (Otomatik)")
        self.rb_dark = QRadioButton("🌙  Karanlık Tema")
        self.rb_light = QRadioButton("☀️  Açık Tema")

        if current_theme == "light":
            self.rb_light.setChecked(True)
        elif current_theme == "dark":
            self.rb_dark.setChecked(True)
        else:
            self.rb_system.setChecked(True)

        self.theme_group.addButton(self.rb_system, 0)
        self.theme_group.addButton(self.rb_dark, 1)
        self.theme_group.addButton(self.rb_light, 2)

        self.rb_system.toggled.connect(lambda chk: self._on_theme_changed("system") if chk else None)
        self.rb_dark.toggled.connect(lambda chk: self._on_theme_changed("dark") if chk else None)
        self.rb_light.toggled.connect(lambda chk: self._on_theme_changed("light") if chk else None)

        theme_row.addWidget(self.rb_system)
        theme_row.addWidget(self.rb_dark)
        theme_row.addWidget(self.rb_light)
        theme_row.addStretch()
        t_layout.addLayout(theme_row)

        content_layout.addWidget(card_theme)

        # 3. Update Available Panel (Hidden by default, shown when update found)
        self.panel_new_version = QFrame()
        self.panel_new_version.setObjectName("CardFrame")
        self.panel_new_version.setVisible(False)
        nv_layout = QVBoxLayout(self.panel_new_version)
        nv_layout.setContentsMargins(22, 20, 22, 20)
        nv_layout.setSpacing(12)

        self.lbl_nv_title = QLabel("🚀  Yeni Sürüm Bulundu!")
        self.lbl_nv_title.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {COLOR_ACCENT};")
        nv_layout.addWidget(self.lbl_nv_title)

        self.lbl_nv_details = QLabel("")
        self.lbl_nv_details.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        nv_layout.addWidget(self.lbl_nv_details)

        lbl_log_head = QLabel("Sürüm Notları ve Değişiklikler:")
        lbl_log_head.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 600;")
        nv_layout.addWidget(lbl_log_head)

        self.txt_changelog = QTextEdit()
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setFixedHeight(120)
        nv_layout.addWidget(self.txt_changelog)

        # Download progress bar
        self.progress_download = QProgressBar()
        self.progress_download.setVisible(False)
        self.progress_download.setFixedHeight(14)
        nv_layout.addWidget(self.progress_download)

        self.lbl_download_status = QLabel("")
        self.lbl_download_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        self.lbl_download_status.setVisible(False)
        nv_layout.addWidget(self.lbl_download_status)

        # Install Button
        self.btn_download_install = QPushButton("⬇️  Şimdi İndir ve Güncellemeyi Yükle")
        self.btn_download_install.setProperty("class", "success-btn")
        self.btn_download_install.setCursor(Qt.PointingHandCursor)
        self.btn_download_install.clicked.connect(self._download_and_install)
        nv_layout.addWidget(self.btn_download_install)

        content_layout.addWidget(self.panel_new_version)

        # 4. Automated Cleaning & Smart Maintenance Card
        card_auto_clean = QFrame()
        card_auto_clean.setObjectName("CardFrame")
        ac_layout = QVBoxLayout(card_auto_clean)
        ac_layout.setContentsMargins(22, 20, 22, 20)
        ac_layout.setSpacing(14)

        lbl_ac_title = QLabel("🧹  Otomatik Temizleme ve Akıllı Bakım (Auto-Clean)")
        lbl_ac_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #38BDF8;")
        ac_layout.addWidget(lbl_ac_title)

        lbl_ac_sub = QLabel("Bilgisayarınızın her zaman ilk günkü hızında kalması için gereksiz dosyaları ve RAM'i arka planda otomatik olarak temizleyin.")
        lbl_ac_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        ac_layout.addWidget(lbl_ac_sub)

        # Master toggle
        self.chk_auto_clean = QCheckBox("⚡  Otomatik sistem temizliğini ve arka plan bakımını etkinleştir")
        self.chk_auto_clean.setStyleSheet("font-weight: 700; font-size: 13px;")
        is_ac_enabled = self.config.get("auto_clean_enabled", True)
        self.chk_auto_clean.setChecked(is_ac_enabled)
        self.chk_auto_clean.stateChanged.connect(self._on_auto_clean_toggle)
        ac_layout.addWidget(self.chk_auto_clean)

        # Options Container (enabled/disabled with master switch)
        self.auto_clean_options_widget = QWidget()
        ac_opt_lay = QVBoxLayout(self.auto_clean_options_widget)
        ac_opt_lay.setContentsMargins(0, 4, 0, 4)
        ac_opt_lay.setSpacing(10)

        # Trigger / Schedule selector row
        sch_row = QHBoxLayout()
        sch_row.setSpacing(12)
        lbl_sch = QLabel("Temizleme Sıklığı / Tetikleyici:")
        lbl_sch.setStyleSheet("font-size: 12px; font-weight: 600;")
        sch_row.addWidget(lbl_sch)

        self.combo_schedule = QComboBox()
        self.combo_schedule.setMinimumWidth(260)
        self.combo_schedule.addItem("Günde Bir Kez (Önerilen)", "daily")
        self.combo_schedule.addItem("Her Windows Başlangıcında", "startup")
        self.combo_schedule.addItem("Haftada Bir Kez", "weekly")
        self.combo_schedule.addItem("Gereksiz Dosyalar 1 GB'ı Aştığında", "threshold")

        cur_sch = self.config.get("auto_clean_schedule", "daily")
        idx = self.combo_schedule.findData(cur_sch)
        if idx >= 0:
            self.combo_schedule.setCurrentIndex(idx)
        self.combo_schedule.currentIndexChanged.connect(self._on_schedule_changed)
        sch_row.addWidget(self.combo_schedule)
        sch_row.addStretch()
        ac_opt_lay.addLayout(sch_row)

        # Categories
        self.chk_ac_junk = QCheckBox("🗑️  Geçici dosyalar, Windows önbellekleri ve çöp kutusu (Junk Cleaner)")
        self.chk_ac_junk.setChecked(self.config.get("auto_clean_junk", True))
        self.chk_ac_junk.stateChanged.connect(lambda s: self.config.set("auto_clean_junk", s == Qt.Checked))
        ac_opt_lay.addWidget(self.chk_ac_junk)

        self.chk_ac_ram = QCheckBox("🧠  Yüksek bellek tüketiminde RAM'i otomatik boşalt (Memory Booster)")
        self.chk_ac_ram.setChecked(self.config.get("auto_clean_ram", True))
        self.chk_ac_ram.stateChanged.connect(lambda s: self.config.set("auto_clean_ram", s == Qt.Checked))
        ac_opt_lay.addWidget(self.chk_ac_ram)

        self.chk_ac_traces = QCheckBox("🛡️  Kullanıcı etkinlik geçmişi ve son açılan dosyalar (Gizlilik)")
        self.chk_ac_traces.setChecked(self.config.get("auto_clean_traces", False))
        self.chk_ac_traces.stateChanged.connect(lambda s: self.config.set("auto_clean_traces", s == Qt.Checked))
        ac_opt_lay.addWidget(self.chk_ac_traces)

        self.chk_ac_notify = QCheckBox("🔔  Otomatik temizlik yapıldığında sistem tepsisinde bildirim göster")
        self.chk_ac_notify.setChecked(self.config.get("auto_clean_notify", True))
        self.chk_ac_notify.stateChanged.connect(lambda s: self.config.set("auto_clean_notify", s == Qt.Checked))
        ac_opt_lay.addWidget(self.chk_ac_notify)

        # Status and Test Button Row
        stat_row = QHBoxLayout()
        stat_row.setSpacing(14)
        last_clean_disp = self.config.get("last_auto_clean_display", "Henüz yapılmadı")
        self.lbl_ac_last = QLabel(f"Son Otomatik Temizlik: <b>{last_clean_disp}</b>")
        self.lbl_ac_last.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        stat_row.addWidget(self.lbl_ac_last)
        stat_row.addStretch()

        self.btn_run_auto_clean_now = QPushButton("⚡  Şimdi Otomatik Temizliği Çalıştır")
        self.btn_run_auto_clean_now.setProperty("class", "secondary-btn")
        self.btn_run_auto_clean_now.setCursor(Qt.PointingHandCursor)
        self.btn_run_auto_clean_now.clicked.connect(self._run_auto_clean_manual)
        stat_row.addWidget(self.btn_run_auto_clean_now)
        ac_opt_lay.addLayout(stat_row)

        ac_layout.addWidget(self.auto_clean_options_widget)
        self.auto_clean_options_widget.setEnabled(is_ac_enabled)

        content_layout.addWidget(card_auto_clean)

        # 5. General Preferences Card
        card_gen = QFrame()
        card_gen.setObjectName("CardFrame")
        g_layout = QVBoxLayout(card_gen)
        g_layout.setContentsMargins(22, 20, 22, 20)
        g_layout.setSpacing(14)

        lbl_g_title = QLabel("⚙️  Genel Uygulama Tercihleri")
        lbl_g_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        g_layout.addWidget(lbl_g_title)

        self.chk_autostart = QCheckBox("🚀  Windows başladığında NovaCare'i arka planda otomatik olarak çalıştır")
        self.chk_autostart.setChecked(is_autostart_enabled())
        self.chk_autostart.stateChanged.connect(lambda s: set_autostart(s == Qt.Checked))
        g_layout.addWidget(self.chk_autostart)

        self.chk_auto_reg = QCheckBox("Kayıt defteri onarımları öncesinde her zaman otomatik geri yükleme yedeği al")
        self.chk_auto_reg.setChecked(self.config.get("auto_backup_registry", True))
        self.chk_auto_reg.stateChanged.connect(lambda s: self.config.set("auto_backup_registry", s == Qt.Checked))
        g_layout.addWidget(self.chk_auto_reg)

        self.chk_tray = QCheckBox("Uygulama simgesini Windows Sistem Tepsisinde (System Tray) çalışır durumda tut")
        self.chk_tray.setChecked(self.config.get("minimize_to_tray", True))
        self.chk_tray.stateChanged.connect(lambda s: self.config.set("minimize_to_tray", s == Qt.Checked))
        g_layout.addWidget(self.chk_tray)

        self.chk_close_to_tray = QCheckBox("Pencere [X] işaretinden kapatıldığında çıkış yapmak yerine Sistem Tepsisine küçült")
        self.chk_close_to_tray.setChecked(self.config.get("close_to_tray", True))
        self.chk_close_to_tray.stateChanged.connect(lambda s: self.config.set("close_to_tray", s == Qt.Checked))
        g_layout.addWidget(self.chk_close_to_tray)

        content_layout.addWidget(card_gen)

        # 6. Administrator Privileges Card
        card_admin = QFrame()
        card_admin.setObjectName("CardFrame")
        adm_layout = QVBoxLayout(card_admin)
        adm_layout.setContentsMargins(22, 20, 22, 20)
        adm_layout.setSpacing(14)

        lbl_adm_title = QLabel("🛡️  Yönetici İzinleri ve Ayrıcalık Tercihi")
        lbl_adm_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        adm_layout.addWidget(lbl_adm_title)

        adm_status_row = QHBoxLayout()
        adm_status_row.setSpacing(14)

        has_admin = is_admin()
        badge_text = "🟢  Yönetici Yetkisi Aktif (Maksimum Temizlik Derinliği)" if has_admin else "⚠️  Standart Kullanıcı Modu (Kısıtlı Derinlik)"
        badge_color = COLOR_SUCCESS if has_admin else COLOR_WARNING
        badge_bg = "rgba(16, 185, 129, 0.15)" if has_admin else "rgba(251, 191, 36, 0.15)"

        lbl_adm_badge = QLabel(badge_text)
        lbl_adm_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_color};
            font-weight: 700;
            padding: 5px 14px;
            border-radius: 6px;
        """)
        adm_status_row.addWidget(lbl_adm_badge)

        if not has_admin:
            btn_restart_admin = QPushButton("🛡️  Yönetici Olarak Yeniden Başlat")
            btn_restart_admin.setProperty("class", "primary-btn")
            btn_restart_admin.setCursor(Qt.PointingHandCursor)
            btn_restart_admin.clicked.connect(self._handle_restart_as_admin)
            adm_status_row.addWidget(btn_restart_admin)

        adm_status_row.addStretch()
        adm_layout.addLayout(adm_status_row)

        lbl_adm_desc = QLabel(
            "💡 <b>Neden Yönetici Yetkisi Gerekli?</b><br>"
            "NovaCare yönetici ayrıcalıklarıyla çalıştırıldığında Windows Prefetch, Bellek Dökümleri, geçici sistem günlükleri, "
            "kilitli DLL/sistem kalıntıları ve <code>HKEY_LOCAL_MACHINE</code> kayıt defteri anahtarlarına tam erişim sağlar. "
            "Bu sayede standart temizlemeye kıyasla <b>çok daha derin, kapsamlı ve kalıcı</b> bir temizleme elde edilir."
        )
        lbl_adm_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        lbl_adm_desc.setWordWrap(True)
        adm_layout.addWidget(lbl_adm_desc)

        self.chk_always_admin = QCheckBox("🛡️  NovaCare açılışında her zaman Yönetici Yetkisi talep et (Önerilen)")
        self.chk_always_admin.setChecked(self.config.get("always_run_as_admin", True))
        self.chk_always_admin.stateChanged.connect(lambda s: self.config.set("always_run_as_admin", s == Qt.Checked))
        adm_layout.addWidget(self.chk_always_admin)

        content_layout.addWidget(card_admin)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _handle_restart_as_admin(self):
        confirm = QMessageBox.question(
            self,
            "Yönetici Olarak Yeniden Başlat",
            "NovaCare tam yönetici ayrıcalıklarıyla yeniden başlatılacak.\n\n"
            "Yönetici modu; kilitli sistem dosyalarını, Windows önbelleklerini ve sistem kayıt defterini "
            "çok daha derinlemesine temizlemenize olanak tanır.\n\n"
            "Uygulama şimdi Yönetici olarak yeniden başlatılsın mı?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            restart_as_admin()

    def _on_theme_changed(self, mode: str):
        self.config.set("theme", mode)
        main_win = self.window()
        if hasattr(main_win, 'apply_theme'):
            main_win.apply_theme(mode)

    def check_for_updates_manual(self):
        """Triggers manual check with loading state."""
        self.btn_check_now.setEnabled(False)
        self.btn_check_now.setText("⏳  Güncelleştirmeler Denetleniyor...")
        self.lbl_status_badge.setText("⏳  Denetleniyor...")

        repo = self.config.get("github_repo", "GurpinarSG/NovaCare")
        token = self.config.get_secure_token()
        mode = self.config.get("update_mode", "branch")
        self.check_thread = CheckUpdateThread(repo, token=token, mode=mode)
        self.check_thread.finished.connect(self._on_check_finished)
        self.check_thread.start()

    def _on_check_finished(self, result):
        self.btn_check_now.setEnabled(True)
        self.btn_check_now.setText("🔍  Güncelleştirmeleri Şimdi Denetle")

        # Update last checked timestamp
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.config.set("last_update_check", now_str)
        self.lbl_last_checked.setText(f"Son Güncelleme Denetimi: {now_str}")

        if isinstance(result, Exception):
            self.lbl_status_badge.setText("⚠️  Bağlantı Hatası")
            self.lbl_status_badge.setStyleSheet(f"""
                background-color: rgba(239, 68, 68, 0.15);
                color: {COLOR_DANGER};
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 6px;
            """)
            QMessageBox.warning(self, "Güncelleme Denetimi", f"Güncelleme denetlenirken hata oluştu:\n{result}")
            return

        info: UpdateInfo = result
        self.latest_update_info = info

        if info.available:
            self.lbl_status_badge.setText(f"🟡  Yeni Güncelleme Mevcut ({info.latest_version})")
            self.lbl_status_badge.setStyleSheet(f"""
                background-color: rgba(245, 158, 11, 0.15);
                color: {COLOR_WARNING};
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 6px;
            """)

            # Populate new version card
            sz_str = format_bytes(info.download_size) if info.download_size > 0 else "Otomatik Güncelleme Paketi"
            self.lbl_nv_details.setText(f"<b>Güncelleme:</b> {info.release_title}  |  <b>Tarih:</b> {info.published_at}  |  <b>Paket:</b> {sz_str}")
            self.txt_changelog.setPlainText(info.changelog)
            self.panel_new_version.setVisible(True)

            QMessageBox.information(
                self,
                "Yeni Güncelleştirme Mevcut",
                f"NovaCare için yeni bir sürüm güncellemesi tespit edildi ({info.latest_version}):\n\n"
                f"• Güncelleme Başlığı: {info.release_title}\n"
                f"• Yayın Tarihi: {info.published_at}\n\n"
                f"Aşağıdaki 'Şimdi İndir ve Güncellemeyi Yükle' butonuna tıklayarak yeni özellikleri ve iyileştirmeleri anında uygulayabilirsiniz."
            )
        else:
            self.lbl_status_badge.setText("🟢  Sürümünüz Güncel")
            self.lbl_status_badge.setStyleSheet(f"""
                background-color: rgba(16, 185, 129, 0.15);
                color: {COLOR_SUCCESS};
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 6px;
            """)
            self.panel_new_version.setVisible(False)
            QMessageBox.information(
                self,
                "Uygulamanız Güncel",
                f"Uygulamanız güncel! En son NovaCare sürümünü kullanıyorsunuz ({self.config.get_display_version()}).\n\n"
                f"Bilgisayarınız en güncel optimizasyon ve güvenlik yamalarıyla korunmaktadır."
            )

    def _download_and_install(self):
        if not self.latest_update_info or not self.latest_update_info.download_url:
            QMessageBox.warning(self, "Hata", "İndirme bağlantısı bulunamadı.")
            return

        confirm = QMessageBox.question(
            self,
            "Güncelleştirmeyi Başlat",
            f"NovaCare ({self.latest_update_info.latest_version}) sürüm güncellemesi indirilip kurulacaktır.\n\n"
            "İşlem bittiğinde uygulama otomatik olarak yeniden başlatılacaktır. Devam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_download_install.setEnabled(False)
        self.progress_download.setVisible(True)
        self.lbl_download_status.setVisible(True)
        self.progress_download.setValue(0)
        self.lbl_download_status.setText("Güncelleme paketi güvenli sunucudan indiriliyor...")

        new_sha = self.latest_update_info.new_commit_sha or ""
        new_ver = self.latest_update_info.latest_version or ""
        self.download_thread = DownloadUpdateThread(
            self.updater,
            self.latest_update_info.download_url,
            new_commit_sha=new_sha,
            new_version=new_ver
        )
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_download.setValue(pct)
            self.lbl_download_status.setText(f"İndiriliyor: {format_bytes(downloaded)} / {format_bytes(total)} (%{pct})")
        else:
            self.lbl_download_status.setText(f"İndiriliyor: {format_bytes(downloaded)}...")

    def _on_download_finished(self, result: str):
        self.btn_download_install.setEnabled(True)

        if result.startswith("ERROR:"):
            self.progress_download.setVisible(False)
            self.lbl_download_status.setText("İndirme başarısız!")
            QMessageBox.critical(self, "İndirme Hatası", f"Güncelleme dosyası indirilemedi:\n{result[6:]}")
            return

        self.progress_download.setValue(100)
        self.lbl_download_status.setText("İndirme ve hazırlık tamamlandı! Yeniden başlatılıyor...")

        QMessageBox.information(
            self,
            "Güncelleme Hazır",
            "Güncelleme dosyaları başarıyla hazırlandı.\n\n"
            "Uygulama şimdi kapanacak ve yeni sürüm başlatılacaktır."
        )

        # Launch the updater batch script and quit
        self.updater.launch_updater_and_exit(result)

    def _on_auto_clean_toggle(self, state: int):
        enabled = (state == Qt.Checked)
        self.config.set("auto_clean_enabled", enabled)
        if hasattr(self, 'auto_clean_options_widget'):
            self.auto_clean_options_widget.setEnabled(enabled)

    def _on_schedule_changed(self):
        sch = self.combo_schedule.currentData()
        if sch:
            self.config.set("auto_clean_schedule", sch)

    def _run_auto_clean_manual(self):
        self.btn_run_auto_clean_now.setEnabled(False)
        self.btn_run_auto_clean_now.setText("⏳  Temizleniyor...")
        self.manual_clean_worker = ManualAutoCleanWorker()
        self.manual_clean_worker.finished.connect(self._on_manual_clean_finished)
        self.manual_clean_worker.start()

    def _on_manual_clean_finished(self, res: dict):
        self.btn_run_auto_clean_now.setEnabled(True)
        self.btn_run_auto_clean_now.setText("⚡  Şimdi Otomatik Temizliği Çalıştır")
        disp = res.get("timestamp", "")
        self.lbl_ac_last.setText(f"Son Otomatik Temizlik: <b>{disp}</b>")

        QMessageBox.information(
            self,
            "Otomatik Temizlik Tamamlandı",
            f"Otomatik bakım başarıyla tamamlandı!\n\n"
            f"• Temizlenen Gereksiz Dosya: {res['freed_junk_str']} ({res['cleaned_files_count']} dosya)\n"
            f"• Boşaltılan Bellek (RAM): {res['freed_ram_str']}\n"
            f"• Toplam Kazanılan Alan: {res['total_freed_str']}"
        )

    def _get_changelog_text(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        cl_path = os.path.join(base_dir, "CHANGELOG.md")
        if os.path.exists(cl_path):
            try:
                with open(cl_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        return (
            "# 📋 NovaCare Sürüm Güncelleme Notları\n\n"
            "## 🚀 [v1.0.1] - 2026-10-16 (Güncel Sürüm)\n"
            "• Pencere Boyutu & Düzen: Ekrana duyarlı (responsive) dinamik pencere boyutu eklendi. 768p ve yüksek DPI ekranlarda görev çubuğu taşması önlendi.\n"
            "• Metin Kaydırma: Tüm 11 sekmedeki alt başlıklara kelime kaydırma (word-wrap) eklendi; yazıların ekrandan taşması giderildi.\n"
            "• Denetim Masası Kaldırma: Yerel uninstaller motoru (--uninstall) entegre edildi; Windows Ayarlar / Denetim Masası üzerinden sorunsuz kaldırma sağlandı.\n"
            "• Kurulum Sihirbazı: Koyu tema, düzeltilen yazı ve kontrast sorunları, net ve okunaklı tasarım.\n"
            "• Yönetici Ayrıcalığı: Ayarlar ekranında yönetici olarak başlatma seçeneği ve temizleme ekranlarında derin temizlik vurgusu.\n"
            "• Güvenlik: GitHub API belirteçleri Windows DPAPI ile şifrelendi.\n"
            "• Performans: Çoklu iş parçacığı ve bellek yönetimi iyileştirmeleri.\n\n"
            "## 📦 [v1.0.0] - 2026-10-15 (İlk Kararlı Sürüm)\n"
            "• Tek Tıkla Bakım, Çöp Dosya Temizliği, Kayıt Defteri Onarımı, Başlangıç Yöneticisi, Bloatware & Gizlilik Koruması, Ağ/DNS Optimizasyonu, Kurtarma Merkezi modülleri."
        )

    def _load_recent_changelog(self):
        full_text = self._get_changelog_text()
        # Extract v1.0.1 section or first 800 chars
        lines = full_text.splitlines()
        v101_lines = []
        capture = False
        for line in lines:
            if "v1.0.1" in line:
                capture = True
            elif capture and line.startswith("## ") and "v1.0.1" not in line:
                break
            if capture:
                v101_lines.append(line)
        recent_text = "\n".join(v101_lines) if v101_lines else full_text[:600]
        self.txt_recent_changelog.setPlainText(recent_text.strip())

    def _toggle_changelog_display(self):
        self.panel_changelog.setVisible(not self.panel_changelog.isVisible())

    def _show_full_changelog_dialog(self):
        from PyQt5.QtWidgets import QDialog, QTextBrowser, QDialogButtonBox
        dialog = QDialog(self)
        dialog.setWindowTitle("NovaCare - Sürüm Güncelleme Notları")
        dialog.resize(650, 480)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0A0F1D;
            }
            QTextBrowser {
                background-color: #111827;
                border: 1px solid #1E293B;
                border-radius: 8px;
                color: #F8FAFC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 12px;
            }
            QPushButton {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 22px;
                color: #F8FAFC;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        d_lay = QVBoxLayout(dialog)
        d_lay.setContentsMargins(20, 20, 20, 16)
        d_lay.setSpacing(14)

        lbl = QLabel("📜  NovaCare Sürüm Güncelleme Notları")
        lbl.setStyleSheet("font-size: 17px; font-weight: 800; color: #00D2FF;")
        d_lay.addWidget(lbl)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setPlainText(self._get_changelog_text())
        d_lay.addWidget(browser)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_close = btn_box.button(QDialogButtonBox.Close)
        if btn_close:
            btn_close.setText("Kapat")
        btn_box.rejected.connect(dialog.reject)
        d_lay.addWidget(btn_box)

        dialog.exec_()


