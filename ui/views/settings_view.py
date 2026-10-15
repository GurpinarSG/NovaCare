"""
NovaCare System Suite - Settings & Updater View
Allows manual update checks, automatic update configuration, GitHub repository customization,
and 1-click update installation.
"""
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QLineEdit, QCheckBox, QRadioButton, QButtonGroup, QTextEdit, QMessageBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.config import ConfigManager, CURRENT_VERSION
from core.updater import GitHubUpdater, UpdateInfo
from core.utils import format_bytes
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

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

    def __init__(self, updater: GitHubUpdater, download_url: str, new_commit_sha: str = ""):
        super().__init__()
        self.updater = updater
        self.download_url = download_url
        self.new_commit_sha = new_commit_sha

    def run(self):
        try:
            batch_path = self.updater.download_and_prepare_update(
                self.download_url,
                new_commit_sha=self.new_commit_sha,
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
        lbl_sub = QLabel("GitHub üzerinden otomatik veya manuel güncellemeleri denetleyin ve genel tercihlerinizi yönetin.")
        lbl_sub.setObjectName("ViewSubtitle")
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)

        # 1. Update Card
        card_update = QFrame()
        card_update.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 20px 24px;
        """)
        u_layout = QVBoxLayout(card_update)
        u_layout.setSpacing(16)

        # Section Title
        lbl_u_title = QLabel("🔄  GitHub Yazılım Güncelleştirmesi")
        lbl_u_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        u_layout.addWidget(lbl_u_title)

        # Version status row
        ver_row = QHBoxLayout()
        self.lbl_cur_ver = QLabel(f"Yüklü Sürüm: <b>v{CURRENT_VERSION}</b>")
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

        btn_row.addWidget(self.btn_check_now)
        btn_row.addStretch()
        u_layout.addLayout(btn_row)

        # GitHub Repo Setting Row
        repo_row = QHBoxLayout()
        lbl_repo = QLabel("GitHub Deposu (owner/repo):")
        lbl_repo.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 600;")
        self.txt_repo = QLineEdit(self.config.get("github_repo", "GurpinarSG/NovaCare"))
        self.txt_repo.setFixedWidth(260)

        self.btn_save_repo = QPushButton("Depoyu Kaydet")
        self.btn_save_repo.setProperty("class", "secondary-btn")
        self.btn_save_repo.clicked.connect(self._save_repo)

        repo_row.addWidget(lbl_repo)
        repo_row.addWidget(self.txt_repo)
        repo_row.addWidget(self.btn_save_repo)
        repo_row.addStretch()
        u_layout.addLayout(repo_row)

        # GitHub Personal Access Token (PAT) Row
        token_row = QHBoxLayout()
        lbl_token = QLabel("GitHub Erişim Belirteci (PAT):")
        lbl_token.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 600;")

        self.txt_token = QLineEdit(self.config.get("github_token", ""))
        self.txt_token.setEchoMode(QLineEdit.Password)
        self.txt_token.setFixedWidth(260)

        self.btn_toggle_token = QPushButton("👁️")
        self.btn_toggle_token.setToolTip("Tokeni Göster / Gizle")
        self.btn_toggle_token.setFixedWidth(36)
        self.btn_toggle_token.clicked.connect(self._toggle_token_visibility)

        self.btn_save_token = QPushButton("Tokeni Kaydet & Doğrula")
        self.btn_save_token.setProperty("class", "secondary-btn")
        self.btn_save_token.clicked.connect(self._save_and_verify_token)

        self.lbl_token_status = QLabel("🟢 Bağlı (GurpinarSG)" if self.config.get("github_token") else "⚪ Token Tanımlanmadı")
        self.lbl_token_status.setStyleSheet(f"color: {COLOR_SUCCESS if self.config.get('github_token') else TEXT_MUTED}; font-weight: 600; font-size: 11px;")

        token_row.addWidget(lbl_token)
        token_row.addWidget(self.txt_token)
        token_row.addWidget(self.btn_toggle_token)
        token_row.addWidget(self.btn_save_token)
        token_row.addWidget(self.lbl_token_status)
        token_row.addStretch()
        u_layout.addLayout(token_row)

        # Update Mode Selector Box
        mode_box = QFrame()
        mode_box.setStyleSheet(f"background-color: rgba(0, 210, 255, 0.05); border: 1px solid {BORDER_COLOR}; border-radius: 8px; padding: 10px 14px;")
        m_lay = QVBoxLayout(mode_box)
        m_lay.setSpacing(6)
        lbl_mode_head = QLabel("🎯  <b>Güncelleme Algılama Yöntemi:</b>")
        lbl_mode_head.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 13px;")
        m_lay.addWidget(lbl_mode_head)

        self.radio_mode_branch = QRadioButton("⚡  <b>Anında Klasör/Dal Takibi (Önerilen)</b> — GitHub'da dosya düzenlendiğinde veya yüklendiğinde anında algılar.")
        self.radio_mode_release = QRadioButton("🏷️  <b>Resmi Sürüm Takibi</b> — Yalnızca GitHub Releases altında resmi sürüm (v1.0.1 vb.) yayınlandığında günceller.")

        is_branch = (self.config.get("update_mode", "branch") == "branch")
        self.radio_mode_branch.setChecked(is_branch)
        self.radio_mode_release.setChecked(not is_branch)

        self.radio_mode_branch.toggled.connect(lambda checked: self.config.set("update_mode", "branch" if checked else "release"))

        m_lay.addWidget(self.radio_mode_branch)
        m_lay.addWidget(self.radio_mode_release)
        u_layout.addWidget(mode_box)

        # Automatic update toggles
        self.chk_auto = QCheckBox("Uygulama açılışında güncellemeleri otomatik olarak denetle")
        self.chk_auto.setChecked(self.config.get("auto_check_updates", True))
        self.chk_auto.stateChanged.connect(lambda s: self.config.set("auto_check_updates", s == Qt.Checked))
        u_layout.addWidget(self.chk_auto)

        self.chk_notify = QCheckBox("Yeni sürüm tespit edildiğinde anında bildirim penceresi göster")
        self.chk_notify.setChecked(self.config.get("notify_on_update", True))
        self.chk_notify.stateChanged.connect(lambda s: self.config.set("notify_on_update", s == Qt.Checked))
        u_layout.addWidget(self.chk_notify)

        content_layout.addWidget(card_update)

        # 2. Update Available Panel (Hidden by default, shown when update found)
        self.panel_new_version = QFrame()
        self.panel_new_version.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 2px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 20px 24px;
        """)
        self.panel_new_version.setVisible(False)
        nv_layout = QVBoxLayout(self.panel_new_version)
        nv_layout.setSpacing(12)

        self.lbl_nv_title = QLabel("🚀  Yeni Sürüm Bulundu!")
        self.lbl_nv_title.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {COLOR_ACCENT};")
        nv_layout.addWidget(self.lbl_nv_title)

        self.lbl_nv_details = QLabel("")
        self.lbl_nv_details.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        nv_layout.addWidget(self.lbl_nv_details)

        lbl_log_head = QLabel("Değişiklik Günlüğü ve Yenilikler:")
        lbl_log_head.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 600;")
        nv_layout.addWidget(lbl_log_head)

        self.txt_changelog = QTextEdit()
        self.txt_changelog.setReadOnly(True)
        self.txt_changelog.setFixedHeight(120)
        self.txt_changelog.setStyleSheet(f"""
            background-color: #121721;
            border: 1px solid {BORDER_COLOR};
            border-radius: 8px;
            padding: 8px;
            color: {TEXT_PRIMARY};
            font-size: 12px;
        """)
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

        # 3. General Preferences Card
        card_gen = QFrame()
        card_gen.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 20px 24px;
        """)
        g_layout = QVBoxLayout(card_gen)
        g_layout.setSpacing(14)

        lbl_g_title = QLabel("⚙️  Genel Uygulama Tercihleri")
        lbl_g_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        g_layout.addWidget(lbl_g_title)

        self.chk_auto_reg = QCheckBox("Kayıt defteri onarımları öncesinde her zaman otomatik geri yükleme yedeği al")
        self.chk_auto_reg.setChecked(self.config.get("auto_backup_registry", True))
        self.chk_auto_reg.stateChanged.connect(lambda s: self.config.set("auto_backup_registry", s == Qt.Checked))
        g_layout.addWidget(self.chk_auto_reg)

        self.chk_tray = QCheckBox("Uygulama simgesini Windows Sistem Tepsisinde (System Tray) çalışır durumda tut")
        self.chk_tray.setChecked(self.config.get("minimize_to_tray", True))
        self.chk_tray.stateChanged.connect(lambda s: self.config.set("minimize_to_tray", s == Qt.Checked))
        g_layout.addWidget(self.chk_tray)

        content_layout.addWidget(card_gen)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _save_repo(self):
        repo = self.txt_repo.text().strip()
        if not repo or "/" not in repo:
            QMessageBox.warning(self, "Geçersiz Depo", "Lütfen 'kullanıcı/depo' formatında geçerli bir GitHub depo adı girin (Örn: Gurpi/antigravity).")
            return
        self.config.set("github_repo", repo)
        self.updater.repo = repo
        QMessageBox.information(self, "Kaydedildi", f"GitHub deposu '{repo}' olarak güncellendi.")

    def _toggle_token_visibility(self):
        if self.txt_token.echoMode() == QLineEdit.Password:
            self.txt_token.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_token.setText("🔒")
        else:
            self.txt_token.setEchoMode(QLineEdit.Password)
            self.btn_toggle_token.setText("👁️")

    def _save_and_verify_token(self):
        token = self.txt_token.text().strip()
        self.config.set("github_token", token)
        self.updater.token = token

        if not token:
            self.lbl_token_status.setText("⚪ Token Temizlendi")
            self.lbl_token_status.setStyleSheet(f"color: {TEXT_MUTED}; font-weight: 600; font-size: 11px;")
            QMessageBox.information(self, "Token", "GitHub erişim belirteci kaldırıldı.")
            return

        self.btn_save_token.setEnabled(False)
        self.btn_save_token.setText("⏳ Doğrulanıyor...")
        valid, result = self.updater.verify_token()
        self.btn_save_token.setEnabled(True)
        self.btn_save_token.setText("Tokeni Kaydet & Doğrula")

        if valid:
            self.lbl_token_status.setText(f"🟢 Bağlı ({result})")
            self.lbl_token_status.setStyleSheet(f"color: {COLOR_SUCCESS}; font-weight: 700; font-size: 11px;")
            QMessageBox.information(self, "Token Doğrulandı", f"Tebrikler! GitHub belirteciniz doğrulandı.\n\nBağlı Hesap: @{result}\nÖzel depo ve 5.000 istek/saat erişim hakkı aktif.")
        else:
            self.lbl_token_status.setText("🔴 Geçersiz Token")
            self.lbl_token_status.setStyleSheet(f"color: {COLOR_DANGER}; font-weight: 700; font-size: 11px;")
            QMessageBox.warning(self, "Doğrulama Başarısız", f"Token doğrulanamadı:\n{result}")

    def check_for_updates_manual(self):
        """Triggers manual check with loading state."""
        self.btn_check_now.setEnabled(False)
        self.btn_check_now.setText("⏳  GitHub Denetleniyor...")
        self.lbl_status_badge.setText("⏳  Denetleniyor...")

        repo = self.txt_repo.text().strip()
        token = self.txt_token.text().strip()
        mode = "branch" if self.radio_mode_branch.isChecked() else "release"
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
            sz_str = format_bytes(info.download_size) if info.download_size > 0 else "Otomatik Arşiv (Zipball)"
            self.lbl_nv_details.setText(f"<b>Başlık:</b> {info.release_title}  |  <b>Tarih:</b> {info.published_at}  |  <b>Boyut:</b> {sz_str}")
            self.txt_changelog.setPlainText(info.changelog)
            self.panel_new_version.setVisible(True)

            QMessageBox.information(
                self,
                "Yeni Değişiklikler Bulundu!",
                f"GitHub üzerinde yeni güncellemeler tespit edildi:\n\n"
                f"• Değişiklik/Sürüm: {info.latest_version}\n"
                f"• Başlık: {info.release_title}\n\n"
                f"Aşağıdaki 'Şimdi İndir ve Güncellemeyi Yükle' butonuna tıklayarak doğrudan uygulayabilirsiniz."
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
                "Sisteminiz Güncel",
                f"Tebrikler! GitHub deposundaki en güncel sürüm ({info.latest_version}) bilgisayarınızda yüklü."
            )

    def _download_and_install(self):
        if not self.latest_update_info or not self.latest_update_info.download_url:
            QMessageBox.warning(self, "Hata", "İndirme bağlantısı bulunamadı.")
            return

        confirm = QMessageBox.question(
            self,
            "Güncellemeyi Başlat",
            f"NovaCare ({self.latest_update_info.latest_version}) paketi indirilip kurulacaktır.\n"
            "İşlem bittiğinde uygulama otomatik olarak yeniden başlatılacak. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_download_install.setEnabled(False)
        self.progress_download.setVisible(True)
        self.lbl_download_status.setVisible(True)
        self.progress_download.setValue(0)
        self.lbl_download_status.setText("Güncelleme paketi GitHub üzerinden indiriliyor...")

        new_sha = self.latest_update_info.new_commit_sha or ""
        self.download_thread = DownloadUpdateThread(
            self.updater,
            self.latest_update_info.download_url,
            new_commit_sha=new_sha
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
