"""
NovaCare System Suite - Privacy Shield, Bloatware, Telemetry & Smart Cookie Shield View
Wipes user trace histories, removes pre-installed Windows bloatware apps,
terminates deep Windows telemetry tracking services, and intelligently purges
cross-site tracking cookies while protecting essential user login sessions.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QMessageBox, QFrame, QScrollArea, QProgressBar, QDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QListWidget,
    QAbstractItemView, QTabWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from core.privacy_tweaker import PrivacyTweaker, PrivacyTraceItem, SystemTweak
from core.bloatware_cleaner import BloatwareCleaner, BloatwareItem
from core.cookie_shield import CookieShield, CookieDomainItem, DEFAULT_WHITELIST
from core.utils import is_admin, log_debug
from ui.styles import (
    get_active_theme_colors, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER, COLOR_WARNING,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class BloatwareScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.cleaner = BloatwareCleaner()

    def run(self):
        items = []
        try:
            items = self.cleaner.scan_installed_bloatware()
        except Exception as e:
            log_debug(f"BloatwareScanWorker error: {e}")
        finally:
            self.finished.emit(items)

class BloatwareRemoveWorker(QThread):
    finished = pyqtSignal(int, list)  # count, errors

    def __init__(self, packages: list[str]):
        super().__init__()
        self.packages = packages
        self.cleaner = BloatwareCleaner()

    def run(self):
        removed = 0
        errs = []
        try:
            for pkg in self.packages:
                ok, msg = self.cleaner.remove_bloatware_package(pkg)
                if ok:
                    removed += 1
                else:
                    errs.append(f"{pkg}: {msg}")
        except Exception as e:
            log_debug(f"BloatwareRemoveWorker error: {e}")
            errs.append(str(e))
        finally:
            self.finished.emit(removed, errs)

class DeepTelemetryWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.cleaner = BloatwareCleaner()

    def run(self):
        res = {"success": False, "details": []}
        try:
            res = self.cleaner.disable_deep_telemetry()
        except Exception as e:
            log_debug(f"DeepTelemetryWorker error: {e}")
            res = {"success": False, "details": [f"Hata: {e}"]}
        finally:
            self.finished.emit(res)

class CookieScanWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.shield = CookieShield()

    def run(self):
        res = {}
        try:
            res = self.shield.scan_cookies()
        except Exception as e:
            log_debug(f"CookieScanWorker error: {e}")
        finally:
            self.finished.emit(res)

class CookieCleanWorker(QThread):
    finished = pyqtSignal(int, int, list)  # deleted, preserved, locked_browsers

    def __init__(self):
        super().__init__()
        self.shield = CookieShield()

    def run(self):
        deleted, preserved, locked = 0, 0, []
        try:
            deleted, preserved, locked = self.shield.clean_tracking_cookies()
        except Exception as e:
            log_debug(f"CookieCleanWorker error: {e}")
        finally:
            self.finished.emit(deleted, preserved, locked)

class CookieWhitelistDialog(QDialog):
    def __init__(self, shield: CookieShield, parent=None):
        super().__init__(parent)
        self.shield = shield
        self.setWindowTitle("🛡️  Korunan Siteleri Yönet (Oturum Kalkanı)")
        self.resize(560, 520)
        theme = get_active_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['BG_CARD']};
                color: {theme['TEXT_PRIMARY']};
            }}
            QListWidget {{
                background-color: {theme['BG_INPUT']};
                border: 1px solid {theme['BORDER_COLOR']};
                border-radius: 6px;
                color: {theme['TEXT_PRIMARY']};
                padding: 6px;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-radius: 4px;
                color: {theme['TEXT_PRIMARY']};
            }}
            QListWidget::item:hover {{
                background-color: {theme['BG_CARD_HOVER']};
            }}
            QListWidget::item:selected {{
                background-color: {theme['COLOR_ACCENT']};
                color: #FFFFFF;
            }}
            QLineEdit {{
                background-color: {theme['BG_INPUT']};
                border: 1px solid {theme['BORDER_COLOR']};
                border-radius: 6px;
                color: {theme['TEXT_PRIMARY']};
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {theme['COLOR_ACCENT']};
            }}
        """)
        self._init_ui()
        self._load_domains()

    def _init_ui(self):
        theme = get_active_theme_colors()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(14)

        lbl_title = QLabel("🛡️ Korunan Oturum Siteleri (Beyaz Liste)")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme['COLOR_ACCENT']};")
        lay.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Bu listedeki alan adlarına ait çerezler (oturum belirteçleri ve hesap giriş anahtarları) "
            "asla silinmez. Böylece Google, YouTube, Bankalar ve e-Devlet oturumlarınız sürekli açık kalır."
        )
        lbl_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 12px; line-height: 1.4;")
        lbl_desc.setWordWrap(True)
        lay.addWidget(lbl_desc)

        # Add domain row
        add_row = QHBoxLayout()
        self.txt_domain = QLineEdit()
        self.txt_domain.setPlaceholderText("Yeni site ekle (örnek: github.com veya spotify.com)")
        self.txt_domain.returnPressed.connect(self._add_domain)
        add_row.addWidget(self.txt_domain)

        btn_add = QPushButton("➕ Ekle")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._add_domain)
        add_row.addWidget(btn_add)
        lay.addLayout(add_row)

        # Domain List
        self.list_widget = QListWidget()
        lay.addWidget(self.list_widget)

        # Bottom Action Bar
        bot_bar = QHBoxLayout()
        btn_remove = QPushButton("🗑️ Seçileni Sil")
        btn_remove.setProperty("class", "danger-btn")
        btn_remove.setCursor(Qt.PointingHandCursor)
        btn_remove.clicked.connect(self._remove_selected)
        bot_bar.addWidget(btn_remove)

        btn_reset = QPushButton("🔄 Varsayılanlara Sıfırla")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_defaults)
        bot_bar.addWidget(btn_reset)

        bot_bar.addStretch()

        btn_close = QPushButton("Tamam")
        btn_close.setProperty("class", "success-btn")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        bot_bar.addWidget(btn_close)

        lay.addLayout(bot_bar)

    def _load_domains(self):
        self.list_widget.clear()
        domains = self.shield.get_whitelist()
        for d in sorted(domains):
            self.list_widget.addItem(d)

    def _add_domain(self):
        text = self.txt_domain.text().strip()
        if not text:
            return
        if self.shield.add_domain(text):
            self.txt_domain.clear()
            self._load_domains()
        else:
            QMessageBox.information(self, "Bilgi", "Bu alan adı zaten koruma listesinde mevcut veya geçersiz.")

    def _remove_selected(self):
        cur = self.list_widget.currentItem()
        if not cur:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden silmek istediğiniz bir alan adı seçin.")
            return
        d = cur.text()
        self.shield.remove_domain(d)
        self._load_domains()

    def _reset_defaults(self):
        reply = QMessageBox.question(
            self,
            "Varsayılana Sıfırla",
            "Korunan alan adları varsayılan popüler siteler listesine döndürülecektir. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.shield.reset_whitelist()
            self._load_domains()

class PrivacyView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tweaker = PrivacyTweaker()
        self.bloatware_cleaner = BloatwareCleaner()
        self.cookie_shield = CookieShield()

        self.traces: list[PrivacyTraceItem] = []
        self.tweaks: list[SystemTweak] = []
        self.bloatware_items: list[BloatwareItem] = []
        self.selected_bloatware: set[str] = set()
        
        self.scan_worker = None
        self.remove_worker = None
        self.telemetry_worker = None
        self.cookie_scan_worker = None
        self.cookie_clean_worker = None
        self.cookie_data: dict = {}

        self._init_ui()
        self._has_initialized = False

    def lazy_init_scan(self):
        """Called when user navigates to Privacy tab for the first time."""
        if self._has_initialized:
            return
        self._has_initialized = True
        self.refresh_all()

    def _init_ui(self):
        theme = get_active_theme_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(14)

        # Header
        lbl_title = QLabel("Gizlilik Kalkanı, Bloatware & Akıllı Çerez Kalkanı")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Kullanım geçmişinizi silin, gereksiz bloatware uygulamalarını ve telemetriyi kaldırın; oturumlarınızı koruyarak takip çerezlerini temizleyin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Main Sub-navigation Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # =========================================================================
        # TAB 1: SMART COOKIE SHIELD (Akıllı Çerez Kalkanı)
        # =========================================================================
        tab_cookies = QWidget()
        c_layout = QVBoxLayout(tab_cookies)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(12)

        lbl_c_desc = QLabel(
            "Oturum açtığınız popüler hesapları (Google, YouTube, GitHub, Bankalar, e-Devlet vb.) korurken; "
            "web sitelerindeki üçüncü taraf reklam takipçilerini, analiz izleyicilerini ve gizlilik açıklarını temizler."
        )
        lbl_c_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 12px; line-height: 1.4;")
        lbl_c_desc.setWordWrap(True)
        c_layout.addWidget(lbl_c_desc)

        # Stats Bar
        c_stats_frame = QFrame()
        c_stats_frame.setObjectName("ToolbarFrame")
        cs_lay = QHBoxLayout(c_stats_frame)
        cs_lay.setContentsMargins(14, 8, 14, 8)

        self.lbl_cookie_total = QLabel("📦 Toplam: 0 Çerez")
        self.lbl_cookie_total.setStyleSheet(f"font-weight: 700; color: {theme['TEXT_PRIMARY']}; font-size: 13px;")

        self.lbl_cookie_protected = QLabel("🛡️ Korunan Oturum: 0")
        self.lbl_cookie_protected.setStyleSheet(f"font-weight: 700; color: {theme['COLOR_SUCCESS']}; font-size: 13px;")

        self.lbl_cookie_tracking = QLabel("🗑️ Takip/Reklam: 0")
        self.lbl_cookie_tracking.setStyleSheet(f"font-weight: 700; color: {theme['COLOR_DANGER']}; font-size: 13px;")

        cs_lay.addWidget(self.lbl_cookie_total)
        cs_lay.addSpacing(20)
        cs_lay.addWidget(self.lbl_cookie_protected)
        cs_lay.addSpacing(20)
        cs_lay.addWidget(self.lbl_cookie_tracking)
        cs_lay.addStretch()
        c_layout.addWidget(c_stats_frame)

        # Cookie Action Buttons Bar
        c_bar = QHBoxLayout()
        c_bar.setSpacing(10)

        self.btn_scan_cookies = QPushButton("🔍  Çerezleri Tara")
        self.btn_scan_cookies.setProperty("class", "secondary-btn")
        self.btn_scan_cookies.setCursor(Qt.PointingHandCursor)
        self.btn_scan_cookies.clicked.connect(self._scan_cookies)
        c_bar.addWidget(self.btn_scan_cookies)

        self.btn_clean_cookies = QPushButton("🧹  Takip Çerezlerini Temizle (Oturumları Koru)")
        self.btn_clean_cookies.setProperty("class", "success-btn")
        self.btn_clean_cookies.setCursor(Qt.PointingHandCursor)
        self.btn_clean_cookies.setEnabled(False)
        self.btn_clean_cookies.clicked.connect(self._clean_tracking_cookies)
        c_bar.addWidget(self.btn_clean_cookies)

        self.btn_whitelist = QPushButton("🛡️  Korunan Siteleri Yönet")
        self.btn_whitelist.setCursor(Qt.PointingHandCursor)
        self.btn_whitelist.clicked.connect(self._open_whitelist_dialog)
        c_bar.addWidget(self.btn_whitelist)

        c_bar.addStretch()
        c_layout.addLayout(c_bar)

        # Locked Browser Alert Banner (Hidden by default)
        self.frame_browser_locked = QFrame()
        self.frame_browser_locked.setStyleSheet(f"""
            background-color: rgba(251, 191, 36, 0.12);
            border: 1px solid rgba(251, 191, 36, 0.35);
            border-radius: 8px;
            padding: 8px 12px;
        """)
        fbl_lay = QHBoxLayout(self.frame_browser_locked)
        fbl_lay.setContentsMargins(4, 2, 4, 2)
        self.lbl_locked_msg = QLabel("⚠️ Tarayıcı açık olduğu için çerez veritabanı kilitli.")
        self.lbl_locked_msg.setStyleSheet(f"color: {theme['COLOR_WARNING']}; font-weight: 600; font-size: 12px;")
        fbl_lay.addWidget(self.lbl_locked_msg)
        fbl_lay.addStretch()

        self.btn_close_browsers = QPushButton("🚪 Tarayıcıyı Kapat ve Yeniden Tara")
        self.btn_close_browsers.setCursor(Qt.PointingHandCursor)
        self.btn_close_browsers.setStyleSheet(f"""
            background-color: {theme['COLOR_WARNING']};
            color: #FFFFFF;
            font-weight: 700;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 11px;
            border: none;
        """)
        self.btn_close_browsers.clicked.connect(self._close_locked_browsers)
        fbl_lay.addWidget(self.btn_close_browsers)
        self.frame_browser_locked.hide()
        c_layout.addWidget(self.frame_browser_locked)

        # Cookie Table Preview (Takes full expanding tab height)
        self.table_cookies = QTableWidget()
        self.table_cookies.setColumnCount(4)
        self.table_cookies.setHorizontalHeaderLabels(["Tarayıcı", "Alan Adı (Host)", "Çerez Sayısı", "Koruma Durumu"])
        self.table_cookies.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_cookies.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_cookies.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_cookies.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table_cookies.verticalHeader().setVisible(False)
        self.table_cookies.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_cookies.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_cookies.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        c_layout.addWidget(self.table_cookies)

        self.tabs.addTab(tab_cookies, "🍪  Akıllı Çerez Kalkanı")

        # =========================================================================
        # TAB 2: BLOATWARE & TELEMETRY SHIELD
        # =========================================================================
        tab_bloatware = QWidget()
        b_layout = QVBoxLayout(tab_bloatware)
        b_layout.setContentsMargins(14, 14, 14, 14)
        b_layout.setSpacing(12)

        lbl_b_desc = QLabel("Windows ile yüklü gelen Cortana, Bing Hava Durumu, Bing Haberler, Xbox Game Bar gibi arka planda veri ve bellek harcayan uygulamaları kaldırın.")
        lbl_b_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 12px;")
        lbl_b_desc.setWordWrap(True)
        b_layout.addWidget(lbl_b_desc)

        # Bloatware Controls Bar
        b_bar = QHBoxLayout()
        b_bar.setSpacing(10)

        self.btn_scan_bloatware = QPushButton("🔍  Bloatware Tara")
        self.btn_scan_bloatware.setCursor(Qt.PointingHandCursor)
        self.btn_scan_bloatware.setProperty("class", "secondary-btn")
        self.btn_scan_bloatware.clicked.connect(self._scan_bloatware)
        b_bar.addWidget(self.btn_scan_bloatware)

        self.btn_remove_bloatware = QPushButton("🗑️  Seçilenleri Kaldır")
        self.btn_remove_bloatware.setProperty("class", "danger-btn")
        self.btn_remove_bloatware.setCursor(Qt.PointingHandCursor)
        self.btn_remove_bloatware.setEnabled(False)
        self.btn_remove_bloatware.clicked.connect(self._remove_selected_bloatware)
        b_bar.addWidget(self.btn_remove_bloatware)

        self.btn_deep_telemetry = QPushButton("🛑  Derin Telemetriyi Kapat")
        self.btn_deep_telemetry.setToolTip("Windows arka plan telemetri servislerini ve veri toplama politikalarını kalıcı olarak kapatır")
        self.btn_deep_telemetry.setCursor(Qt.PointingHandCursor)
        self.btn_deep_telemetry.clicked.connect(self._disable_deep_telemetry)
        b_bar.addWidget(self.btn_deep_telemetry)

        b_bar.addStretch()
        b_layout.addLayout(b_bar)

        self.lbl_bloatware_status = QLabel("Bloatware taraması bekleniyor...")
        self.lbl_bloatware_status.setStyleSheet(f"font-size: 12px; color: {theme['TEXT_SECONDARY']};")
        b_layout.addWidget(self.lbl_bloatware_status)

        # Scroll area for bloatware items
        scroll_b = QScrollArea()
        scroll_b.setWidgetResizable(True)
        scroll_b.setFrameShape(QFrame.NoFrame)
        scroll_b.setStyleSheet("background: transparent; border: none;")
        scroll_b.viewport().setStyleSheet("background: transparent; border: none;")
        scroll_b_widget = QWidget()
        scroll_b_widget.setStyleSheet("background: transparent;")
        self.bloatware_container = QVBoxLayout(scroll_b_widget)
        self.bloatware_container.setSpacing(6)
        scroll_b.setWidget(scroll_b_widget)
        b_layout.addWidget(scroll_b)

        self.tabs.addTab(tab_bloatware, "📦  Bloatware & Telemetri")

        # =========================================================================
        # TAB 3: PRIVACY TRACES
        # =========================================================================
        tab_traces = QWidget()
        traces_layout = QVBoxLayout(tab_traces)
        traces_layout.setContentsMargins(14, 14, 14, 14)
        traces_layout.setSpacing(12)

        lbl_traces_desc = QLabel("Windows Gezgini arama geçmişi, son açılan belgeler, Çalıştır kutusu ve sistem etkinlik izlerini tek tıkla silin.")
        lbl_traces_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 12px;")
        traces_layout.addWidget(lbl_traces_desc)

        # Traces Action Bar
        t_bar = QHBoxLayout()
        self.btn_clean_traces = QPushButton("🧹  Seçili İzleri Temizle")
        self.btn_clean_traces.setProperty("class", "success-btn")
        self.btn_clean_traces.setCursor(Qt.PointingHandCursor)
        self.btn_clean_traces.clicked.connect(self._clean_traces)

        self.lbl_traces_count = QLabel("0 iz bulundu")
        self.lbl_traces_count.setStyleSheet(f"color: {theme['COLOR_ACCENT']}; font-weight: 600;")

        t_bar.addWidget(self.btn_clean_traces)
        t_bar.addSpacing(16)
        t_bar.addWidget(self.lbl_traces_count)
        t_bar.addStretch()
        traces_layout.addLayout(t_bar)

        scroll_t = QScrollArea()
        scroll_t.setWidgetResizable(True)
        scroll_t.setFrameShape(QFrame.NoFrame)
        scroll_t.setStyleSheet("background: transparent; border: none;")
        scroll_t.viewport().setStyleSheet("background: transparent; border: none;")
        scroll_t_widget = QWidget()
        scroll_t_widget.setStyleSheet("background: transparent;")
        self.traces_container = QVBoxLayout(scroll_t_widget)
        self.traces_container.setSpacing(8)
        scroll_t.setWidget(scroll_t_widget)
        traces_layout.addWidget(scroll_t)

        self.tabs.addTab(tab_traces, "🛡️  Etkinlik İzleri")

        # =========================================================================
        # TAB 4: WINDOWS PRIVACY & TELEMETRY TWEAKS
        # =========================================================================
        tab_tweaks = QWidget()
        tweaks_layout = QVBoxLayout(tab_tweaks)
        tweaks_layout.setContentsMargins(14, 14, 14, 14)
        tweaks_layout.setSpacing(12)

        lbl_tweaks_desc = QLabel("Windows 10/11 telemetri politikalarını, kişiselleştirilmiş reklam kimliğini ve tanılama veri gönderimlerini kontrol edin.")
        lbl_tweaks_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 12px;")
        tweaks_layout.addWidget(lbl_tweaks_desc)

        scroll_tw = QScrollArea()
        scroll_tw.setWidgetResizable(True)
        scroll_tw.setFrameShape(QFrame.NoFrame)
        scroll_tw.setStyleSheet("background: transparent; border: none;")
        scroll_tw.viewport().setStyleSheet("background: transparent; border: none;")
        scroll_tw_widget = QWidget()
        scroll_tw_widget.setStyleSheet("background: transparent;")
        self.tweaks_container = QVBoxLayout(scroll_tw_widget)
        self.tweaks_container.setSpacing(10)
        scroll_tw.setWidget(scroll_tw_widget)
        tweaks_layout.addWidget(scroll_tw)

        self.tabs.addTab(tab_tweaks, "⚙️  Windows Ayarları")

        main_layout.addWidget(self.tabs)

    def refresh_all(self):
        self._refresh_traces()
        self._refresh_tweaks()
        self._scan_bloatware()
        self._scan_cookies()

    # -------------------------------------------------------------------------
    # SMART COOKIE SHIELD LOGIC
    # -------------------------------------------------------------------------
    def _scan_cookies(self):
        self.btn_scan_cookies.setEnabled(False)
        self.btn_scan_cookies.setText("🔍  Taranıyor...")
        self.cookie_scan_worker = CookieScanWorker()
        self.cookie_scan_worker.finished.connect(self._on_cookies_scanned)
        self.cookie_scan_worker.start()

    def _on_cookies_scanned(self, res: dict):
        self.btn_scan_cookies.setEnabled(True)
        self.btn_scan_cookies.setText("🔍  Çerezleri Tara")
        self.cookie_data = res

        total = res.get('total_cookies', 0)
        prot = res.get('protected_count', 0)
        track = res.get('tracking_count', 0)
        items: list[CookieDomainItem] = res.get('domain_items', [])
        locked: list[str] = res.get('locked_browsers', [])

        self.lbl_cookie_total.setText(f"📦 Toplam: {total:,} Çerez")
        self.lbl_cookie_protected.setText(f"🛡️ Korunan Oturum: {prot:,}")
        self.lbl_cookie_tracking.setText(f"🗑️ Takip/Reklam: {track:,}")

        # Browser lock warning banner
        if locked:
            names = ", ".join(locked)
            self.lbl_locked_msg.setText(f"⚠️ {names} açık olduğu için çerez veritabanı kilitli. Temizleme için kapatılması önerilir.")
            self.frame_browser_locked.show()
        else:
            self.frame_browser_locked.hide()

        # Update clean button state
        self.btn_clean_cookies.setEnabled(track > 0)

        # Populate table
        self.table_cookies.setRowCount(len(items))
        for row, it in enumerate(items):
            item_browser = QTableWidgetItem(it.browser)
            item_host = QTableWidgetItem(it.host)
            item_count = QTableWidgetItem(f"{it.count} adet")
            item_count.setTextAlignment(Qt.AlignCenter)

            theme = get_active_theme_colors()
            if it.is_protected:
                status_txt = "🛡️ Korunuyor (Oturum Açık)"
                col_hex = theme["COLOR_SUCCESS"]
            elif it.is_known_tracker:
                status_txt = "🚫 Bilinen Takip / Reklam"
                col_hex = theme["COLOR_DANGER"]
            else:
                status_txt = "⚪ Normal Çerez"
                col_hex = theme["TEXT_MUTED"]

            item_status = QTableWidgetItem(status_txt)
            item_status.setForeground(QColor(col_hex))

            self.table_cookies.setItem(row, 0, item_browser)
            self.table_cookies.setItem(row, 1, item_host)
            self.table_cookies.setItem(row, 2, item_count)
            self.table_cookies.setItem(row, 3, item_status)

    def _open_whitelist_dialog(self):
        dlg = CookieWhitelistDialog(self.cookie_shield, self)
        if dlg.exec_() == QDialog.Accepted:
            self._scan_cookies()

    def _close_locked_browsers(self):
        locked = self.cookie_data.get('locked_browsers', [])
        targets = self.cookie_shield.get_browser_targets()
        closed_any = False
        for t in targets:
            if t['browser'] in locked:
                self.cookie_shield.close_browser(t['exe'])
                closed_any = True

        if closed_any:
            QMessageBox.information(self, "Tarayıcılar Kapatıldı", "Kilitli tarayıcı süreçleri sonlandırıldı. Yeniden taranıyor...")
            self._scan_cookies()

    def _clean_tracking_cookies(self):
        track_count = self.cookie_data.get('tracking_count', 0)
        prot_count = self.cookie_data.get('protected_count', 0)
        locked = self.cookie_data.get('locked_browsers', [])

        if locked:
            ans = QMessageBox.warning(
                self,
                "Tarayıcılar Açık",
                f"Şu tarayıcılar şu an çalışıyor: {', '.join(locked)}\n\n"
                "Chromium veritabanları kilitli olduğu için çalışan tarayıcıların çerezleri temizlenemez.\n\n"
                "Çalışan tarayıcıları otomatik kapatıp temizliğe devam etmek istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if ans == QMessageBox.Cancel:
                return
            if ans == QMessageBox.Yes:
                self._close_locked_browsers()

        reply = QMessageBox.question(
            self,
            "Takip Çerezlerini Temizle",
            f"Sistemdeki {track_count:,} adet takip ve reklam çerezi temizlenecektir.\n\n"
            f"🛡️ Oturum Güvenliği: Google, YouTube, GitHub, Bankalar vb. {prot_count:,} adet oturum çerezine KESİNLİKLE DOKUNULMAYACAK ve açık oturumlarınız korunacaktır.\n\n"
            "Temizliği başlatmak istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_clean_cookies.setEnabled(False)
        self.btn_clean_cookies.setText("🧹 Temizleniyor...")
        self.cookie_clean_worker = CookieCleanWorker()
        self.cookie_clean_worker.finished.connect(self._on_cookies_cleaned)
        self.cookie_clean_worker.start()

    def _on_cookies_cleaned(self, deleted: int, preserved: int, locked: list):
        self.btn_clean_cookies.setEnabled(True)
        self.btn_clean_cookies.setText("🧹  Takip Çerezlerini Temizle (Oturumları Koru)")

        lock_msg = f"\n\n⚠️ Not: {', '.join(locked)} açık olduğu için bazı çerezler kilitli kaldı." if locked else ""
        QMessageBox.information(
            self,
            "Çerez Temizliği Tamamlandı",
            f"✅ {deleted:,} adet takip ve reklam çerezi başarıyla temizlendi!\n"
            f"🛡️ {preserved:,} adet oturum çerezi güvenle korundu.{lock_msg}"
        )
        self._scan_cookies()

    # -------------------------------------------------------------------------
    # BLOATWARE & TELEMETRY LOGIC
    # -------------------------------------------------------------------------
    def _scan_bloatware(self):
        self.btn_scan_bloatware.setEnabled(False)
        self.lbl_bloatware_status.setText("Yüklü bloatware paketleri taranıyor...")
        self.scan_worker = BloatwareScanWorker()
        self.scan_worker.finished.connect(self._on_bloatware_scanned)
        self.scan_worker.start()

    def _on_bloatware_scanned(self, items: list[BloatwareItem]):
        self.btn_scan_bloatware.setEnabled(True)
        self.bloatware_items = items
        self.selected_bloatware.clear()

        while self.bloatware_container.count():
            it = self.bloatware_container.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        installed_count = 0
        theme = get_active_theme_colors()
        for b_item in items:
            if not b_item.installed:
                continue
            installed_count += 1
            self.selected_bloatware.add(b_item.package_name)

            row = QFrame()
            row.setStyleSheet(f"background-color: transparent; border: none; border-bottom: 1px solid {theme['BORDER_COLOR']}; padding-bottom: 4px;")
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 2, 0, 2)

            chk = QCheckBox(f"<b>{b_item.display_name}</b>  <span style='color:{theme['TEXT_MUTED']};'>({b_item.category})</span>")
            chk.setStyleSheet("background-color: transparent;")
            chk.setChecked(True)
            chk.stateChanged.connect(lambda state, name=b_item.package_name: self._on_bloatware_chk(name, state))
            r_lay.addWidget(chk)

            lbl_d = QLabel(b_item.description)
            lbl_d.setStyleSheet(f"color:{theme['TEXT_SECONDARY']}; font-size: 11px;")
            lbl_d.setWordWrap(True)
            r_lay.addWidget(lbl_d)
            r_lay.addStretch()

            self.bloatware_container.addWidget(row)

        if installed_count > 0:
            self.lbl_bloatware_status.setText(f"Sistemde {installed_count} adet kaldırılabilir bloatware tespit edildi.")
            self.btn_remove_bloatware.setEnabled(True)
        else:
            self.lbl_bloatware_status.setText("Tebrikler! Sisteminizde bilinen herhangi bir bloatware paketi bulunamadı.")
            self.btn_remove_bloatware.setEnabled(False)

    def _on_bloatware_chk(self, pkg_name: str, state: int):
        if state == Qt.Checked:
            self.selected_bloatware.add(pkg_name)
        else:
            self.selected_bloatware.discard(pkg_name)
        self.btn_remove_bloatware.setEnabled(len(self.selected_bloatware) > 0)

    def _remove_selected_bloatware(self):
        if not self.selected_bloatware:
            return

        has_admin = is_admin()
        admin_note = (
            "\n\n🛡️ Yönetici Yetkisi: Paketler sistem düzeyinde (AllUsers) kökten ve kalıcı olarak temizlenecektir."
            if has_admin else
            "\n\n💡 İpucu: Sistem düzeyindeki paketleri tamamen kaldırabilmek için uygulamanın Yönetici olarak çalıştırılması önerilir."
        )

        reply = QMessageBox.question(
            self,
            "Bloatware Kaldırma Onayı",
            f"Seçilen {len(self.selected_bloatware)} adet uygulama sistemden kaldırılacak.{admin_note}\n\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_remove_bloatware.setEnabled(False)
        self.lbl_bloatware_status.setText("Seçilen uygulamalar kaldırılıyor, lütfen bekleyin...")
        self.remove_worker = BloatwareRemoveWorker(list(self.selected_bloatware))
        self.remove_worker.finished.connect(self._on_bloatware_removed)
        self.remove_worker.start()

    def _on_bloatware_removed(self, count: int, errors: list):
        QMessageBox.information(
            self,
            "İşlem Tamamlandı",
            f"{count} adet bloatware uygulaması başarıyla kaldırıldı!"
        )
        self._scan_bloatware()

    def _disable_deep_telemetry(self):
        has_admin = is_admin()
        admin_note = (
            "\n\n🛡️ Yönetici Yetkisi Aktif: Servisler ve kayıt defteri grup ilkeleri en derin seviyede kapatılacaktır."
            if has_admin else
            "\n\n⚠️ Dikkat: Telemetri servislerini tamamen durdurabilmek için Yönetici Yetkisi gereklidir."
        )

        reply = QMessageBox.question(
            self,
            "Derin Telemetri Kapatma",
            f"Bu işlem Windows arka plan telemetri servislerini (DiagTrack, dmwappushservice vb.) kalıcı olarak devre dışı bırakır ve Microsoft veri toplama politikalarını kısıtlar.{admin_note}\n\nUygulamak istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.telemetry_worker = DeepTelemetryWorker()
        self.telemetry_worker.finished.connect(self._on_telemetry_finished)
        self.telemetry_worker.start()

    def _on_telemetry_finished(self, res: dict):
        services = res.get("disabled_services", [])
        svc_str = "\n• " + "\n• ".join(services) if services else "\n(Servisler zaten devre dışı)"
        QMessageBox.information(
            self,
            "Telemetri Kapatıldı",
            f"Aşağıdaki telemetri servisleri durduruldu ve başlangıçları devre dışı bırakıldı:{svc_str}\n\nKayıt defteri telemetri ve tüketici promosyonu engelleri uygulandı!"
        )

    # -------------------------------------------------------------------------
    # TRACES & TWEAKS LOGIC
    # -------------------------------------------------------------------------
    def _refresh_traces(self):
        while self.traces_container.count():
            item = self.traces_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme = get_active_theme_colors()
        self.traces = self.tweaker.scan_privacy_traces()
        total_items = sum(t.count for t in self.traces)
        self.lbl_traces_count.setText(f"Toplam {total_items} adet gizlilik izi tespit edildi")

        for trace in self.traces:
            chk = QCheckBox(f"<b>{trace.name}</b>  <span style='color:{theme['TEXT_SECONDARY']};'>({trace.description})</span>")
            chk.setStyleSheet("background-color: transparent; background: transparent;")
            chk.setChecked(trace.selected)
            chk.stateChanged.connect(lambda state, t=trace: self._on_trace_toggle(t, state))
            self.traces_container.addWidget(chk)

    def _on_trace_toggle(self, trace: PrivacyTraceItem, state: int):
        trace.selected = (state == Qt.Checked)

    def _clean_traces(self):
        selected_ids = {t.id for t in self.traces if t.selected}
        if not selected_ids:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen temizlemek istediğiniz en az bir gizlilik izini seçin.")
            return

        cleaned_count = self.tweaker.clean_privacy_traces(selected_ids)
        QMessageBox.information(
            self,
            "Gizlilik Temizliği Tamamlandı",
            f"Seçilen gizlilik izleri başarıyla temizlendi!\nSilinen kayıt sayısı: {cleaned_count}"
        )
        self._refresh_traces()

    def _refresh_tweaks(self):
        while self.tweaks_container.count():
            item = self.tweaks_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme = get_active_theme_colors()
        self.tweaks = self.tweaker.check_tweak_statuses()

        for tweak in self.tweaks:
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background-color: transparent; background: transparent; border: none; border-bottom: 1px solid {theme['BORDER_COLOR']}; padding-bottom: 8px;")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(0, 4, 0, 4)

            v_info = QVBoxLayout()
            lbl_name = QLabel(f"<b>{tweak.name}</b>")
            lbl_name.setWordWrap(True)
            lbl_desc = QLabel(tweak.description)
            lbl_desc.setStyleSheet(f"color: {theme['TEXT_SECONDARY']}; font-size: 11px;")
            lbl_desc.setWordWrap(True)
            v_info.addWidget(lbl_name)
            v_info.addWidget(lbl_desc)

            chk_toggle = QCheckBox()
            chk_toggle.setStyleSheet("background-color: transparent; background: transparent;")
            chk_toggle.setText("Etkinleştirilmiş" if tweak.current_enabled else "Kapatılmış")
            chk_toggle.setChecked(tweak.current_enabled)
            chk_toggle.setCursor(Qt.PointingHandCursor)
            chk_toggle.stateChanged.connect(lambda state, tw=tweak, c=chk_toggle: self._on_tweak_toggle(tw, c, state))

            r_lay.addLayout(v_info)
            r_lay.addStretch()
            r_lay.addWidget(chk_toggle)

            self.tweaks_container.addWidget(row_frame)

    def _on_tweak_toggle(self, tweak: SystemTweak, checkbox: QCheckBox, state: int):
        enable = (state == Qt.Checked)
        success = self.tweaker.apply_tweak(tweak, enable)
        if success:
            checkbox.setText("Etkinleştirilmiş" if enable else "Kapatılmış")
        else:
            checkbox.blockSignals(True)
            checkbox.setChecked(not enable)
            checkbox.blockSignals(False)
            QMessageBox.critical(
                self,
                "Yetki Hatası",
                f"'{tweak.name}' ayarı uygulanamadı. Bu ayar için Yönetici (Administrator) izni gereklidir."
            )
