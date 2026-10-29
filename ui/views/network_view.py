"""
NovaCare System Suite - Network & DNS Optimizer View
Real-time Internet Speed Test (Download, Upload, Ping, Jitter),
DNS latency benchmark, 1-click DNS assignment, DHCP reset,
and complete network stack (Winsock, TCP/IP, flushdns) repair.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QScrollArea, QComboBox, QMessageBox,
    QAbstractItemView, QSizePolicy, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from core.network_optimizer import NetworkOptimizer, DNSServerInfo, DNS_CATALOG
from core.speed_tester import SpeedTester, SpeedTestResult
from core.utils import log_debug
from ui.components import StatCard
from ui.styles import (
    get_active_theme_colors, TEXT_PRIMARY, TEXT_SECONDARY,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER
)

class SpeedTestWorker(QThread):
    phase_changed = pyqtSignal(str, str) # phase, msg
    speed_progress = pyqtSignal(float, int) # mbps, percent
    finished = pyqtSignal(object) # SpeedTestResult

    def __init__(self):
        super().__init__()
        self.tester = SpeedTester()

    def run(self):
        try:
            res = self.tester.run_full_test(
                phase_callback=lambda p, m: self.phase_changed.emit(p, m),
                progress_callback=lambda s, pct: self.speed_progress.emit(s, pct)
            )
            self.finished.emit(res)
        except Exception as e:
            log_debug(f"SpeedTestWorker error: {e}")
            self.finished.emit(None)
        finally:
            self.tester.close()

    def cancel(self):
        self.tester.cancel()

class MetaFetchWorker(QThread):
    finished = pyqtSignal(str, str)

    def run(self):
        tester = SpeedTester()
        try:
            ip, loc = tester.get_network_meta()
            self.finished.emit(ip, loc)
        except Exception:
            self.finished.emit("Otomatik", "Türkiye / Avrupa Edge Sunucusu")
        finally:
            tester.close()

class DNSBenchmarkWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.optimizer = NetworkOptimizer()

    def run(self):
        results = []
        try:
            results = self.optimizer.benchmark_all_dns()
        except Exception as e:
            log_debug(f"DNSBenchmarkWorker error: {e}")
        finally:
            self.finished.emit(results)

class NetworkRepairWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, action_type: str):
        super().__init__()
        self.action_type = action_type
        self.optimizer = NetworkOptimizer()

    def run(self):
        ok = False
        msg = "İşlem başlatılamadı"
        try:
            if self.action_type == "flush":
                ok, msg = self.optimizer.flush_dns()
            elif self.action_type == "reset_stack":
                ok, msg = self.optimizer.reset_network_stack()
            else:
                ok, msg = False, "Bilinmeyen işlem"
        except Exception as e:
            log_debug(f"NetworkRepairWorker error: {e}")
            ok, msg = False, f"Hata: {e}"
        finally:
            self.finished.emit(ok, msg)

class NetworkView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.optimizer = NetworkOptimizer()
        self.benchmark_worker = None
        self.repair_worker = None
        self.speed_worker = None
        self.meta_worker = None
        self.dns_results: list[DNSServerInfo] = []
        self._init_ui()
        self._load_network_info()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll Area for clean overflow
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("NetworkScroll")
        scroll.setStyleSheet("QScrollArea#NetworkScroll { background: transparent; border: none; } QWidget#NetworkContainer { background: transparent; }")

        container = QWidget()
        container.setObjectName("NetworkContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # 1. Header
        header = QVBoxLayout()
        header.setSpacing(4)
        lbl_title = QLabel("🌐  Ağ ve DNS Optimize Edici")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 800;")
        header.addWidget(lbl_title)

        lbl_sub = QLabel("Gerçek zamanlı internet hızınızı test edin, ağ bağlantınızı onarın ve en hızlı DNS sunucusunu tek tıkla aktif edin.")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        lbl_sub.setWordWrap(True)
        header.addWidget(lbl_sub)
        layout.addLayout(header)

        # 2. Internet Speed Test Card
        speed_card = QFrame()
        speed_card.setObjectName("CardFrame")
        sp_layout = QVBoxLayout(speed_card)
        sp_layout.setContentsMargins(18, 16, 18, 16)
        sp_layout.setSpacing(14)

        # Top row: Title + Server Location Info
        sp_top = QHBoxLayout()
        sp_top.setSpacing(10)
        lbl_sp_title = QLabel("🚀  İnternet Hız Testi (Bant Genişliği & Gecikme)")
        lbl_sp_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        sp_top.addWidget(lbl_sp_title)
        sp_top.addStretch()

        self.lbl_server_info = QLabel("📍 Sunucu: Bağlanıyor...")
        self.lbl_server_info.setStyleSheet(f"""
            background: rgba(14, 165, 233, 0.12);
            color: {COLOR_ACCENT};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid rgba(14, 165, 233, 0.25);
        """)
        sp_top.addWidget(self.lbl_server_info)
        sp_layout.addLayout(sp_top)

        # 4 Stat Cards Row: Download, Upload, Ping, Jitter
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        self.card_dl = StatCard("⬇️", "İndirme (Download)", "-- Mbps", "Alınan veri bant genişliği")
        self.card_ul = StatCard("⬆️", "Yükleme (Upload)", "-- Mbps", "Gönderilen veri bant genişliği")
        self.card_ping = StatCard("⚡", "Gecikme (Ping)", "-- ms", "Sunucu tepki süresi")
        self.card_jitter = StatCard("〰️", "Dalgalanma (Jitter)", "-- ms", "Gecikme kararlılığı")

        stats_layout.addWidget(self.card_dl, 1)
        stats_layout.addWidget(self.card_ul, 1)
        stats_layout.addWidget(self.card_ping, 1)
        stats_layout.addWidget(self.card_jitter, 1)
        sp_layout.addLayout(stats_layout)

        # Live speed & status indicator row
        live_row = QHBoxLayout()
        live_row.setSpacing(12)

        self.lbl_live_speed = QLabel("⚡ Anlık Hız: -- Mbps")
        self.lbl_live_speed.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLOR_ACCENT};")
        live_row.addWidget(self.lbl_live_speed)

        self.lbl_speed_status = QLabel("Hız testine başlamak için butona tıklayın.")
        self.lbl_speed_status.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; font-weight: 500;")
        live_row.addWidget(self.lbl_speed_status, 1)

        sp_layout.addLayout(live_row)

        # Progress bar
        self.speed_pbar = QProgressBar()
        self.speed_pbar.setFixedHeight(10)
        self.speed_pbar.setRange(0, 100)
        self.speed_pbar.setValue(0)
        self.speed_pbar.setTextVisible(False)
        self.speed_pbar.setStyleSheet("""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #38BDF8);
                border-radius: 5px;
            }}
        """)
        sp_layout.addWidget(self.speed_pbar)

        # Action Buttons Row + Grade Banner
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_start_speed = QPushButton("🚀  Hız Testini Başlat")
        self.btn_start_speed.setCursor(Qt.PointingHandCursor)
        self.btn_start_speed.setProperty("class", "primary-btn")
        self.btn_start_speed.clicked.connect(self._start_speed_test)
        action_row.addWidget(self.btn_start_speed)

        self.btn_cancel_speed = QPushButton("⏹️  Durdur")
        self.btn_cancel_speed.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_speed.setProperty("class", "danger-btn")
        self.btn_cancel_speed.setEnabled(False)
        self.btn_cancel_speed.clicked.connect(self._cancel_speed_test)
        action_row.addWidget(self.btn_cancel_speed)

        action_row.addStretch()
        sp_layout.addLayout(action_row)

        # Connection Quality Grade Banner (hidden initially)
        self.frame_grade = QFrame()
        self.frame_grade.setVisible(False)
        self.frame_grade.setStyleSheet("""
            QFrame {
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 8px;
                padding: 10px;
            }
        """)
        g_layout = QVBoxLayout(self.frame_grade)
        g_layout.setContentsMargins(12, 8, 12, 8)
        g_layout.setSpacing(3)

        self.lbl_grade_title = QLabel("🌟 Bağlantı Değerlendirmesi: Mükemmel")
        self.lbl_grade_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLOR_SUCCESS};")
        g_layout.addWidget(self.lbl_grade_title)

        self.lbl_grade_desc = QLabel("Bağlantınız yüksek hızlı 4K yayın ve rekabetçi çevrimiçi oyunlar için ideal.")
        self.lbl_grade_desc.setStyleSheet(f"font-size: 12px; color: {TEXT_PRIMARY};")
        self.lbl_grade_desc.setWordWrap(True)
        g_layout.addWidget(self.lbl_grade_desc)

        sp_layout.addWidget(self.frame_grade)

        layout.addWidget(speed_card)

        # 3. Network Repair & Flush Card
        repair_card = QFrame()
        repair_card.setObjectName("CardFrame")
        r_layout = QVBoxLayout(repair_card)
        r_layout.setContentsMargins(18, 14, 18, 14)
        r_layout.setSpacing(10)

        r_top = QHBoxLayout()
        r_top.setSpacing(12)
        lbl_r_title = QLabel("⚡  Hızlı Ağ Onarımı ve Çözümleyici")
        lbl_r_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        r_top.addWidget(lbl_r_title)

        r_top.addStretch()

        self.lbl_repair_status = QLabel("Ağ durumu normal. Bağlantı sorunlarında önbellek temizliğini kullanabilirsiniz.")
        self.lbl_repair_status.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS}; font-weight: 500;")
        self.lbl_repair_status.setWordWrap(True)
        r_top.addWidget(self.lbl_repair_status)
        r_layout.addLayout(r_top)

        r_btns = QHBoxLayout()
        r_btns.setSpacing(10)

        self.btn_flush = QPushButton("🧹  DNS Önbelleğini Temizle (Flush DNS)")
        self.btn_flush.setToolTip("Windows DNS çözümleyici önbelleğini (ipconfig /flushdns) anında temizler")
        self.btn_flush.setCursor(Qt.PointingHandCursor)
        self.btn_flush.setProperty("class", "secondary-btn")
        self.btn_flush.clicked.connect(self._handle_flush_dns)
        r_btns.addWidget(self.btn_flush)

        self.btn_reset_stack = QPushButton("🔄  Winsock & Ağ Yığınını Sıfırla")
        self.btn_reset_stack.setToolTip("Winsock ve TCP/IP ağ protokollerini fabrika ayarlarına döndürür")
        self.btn_reset_stack.setCursor(Qt.PointingHandCursor)
        self.btn_reset_stack.setProperty("class", "secondary-btn")
        self.btn_reset_stack.clicked.connect(self._handle_reset_stack)
        r_btns.addWidget(self.btn_reset_stack)

        r_btns.addStretch()
        r_layout.addLayout(r_btns)

        layout.addWidget(repair_card)

        # 4. DNS Benchmark & Switcher Card
        dns_card = QFrame()
        dns_card.setObjectName("CardFrame")
        d_layout = QVBoxLayout(dns_card)
        d_layout.setContentsMargins(18, 14, 18, 14)
        d_layout.setSpacing(12)

        # Card Title
        lbl_dns_title = QLabel("🌐  DNS Sunucuları ve Hız Kıyaslama Kataloğu")
        lbl_dns_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        d_layout.addWidget(lbl_dns_title)

        # Row 1: Adapter Selector & Current DNS Badge
        row_adapter = QHBoxLayout()
        row_adapter.setSpacing(10)

        lbl_adapter = QLabel("Ağ Bağdaştırıcısı:")
        lbl_adapter.setStyleSheet("font-weight: 600; font-size: 12px;")
        row_adapter.addWidget(lbl_adapter)

        self.combo_adapters = QComboBox()
        self.combo_adapters.setMinimumWidth(180)
        self.combo_adapters.setStyleSheet("padding: 5px 10px; font-weight: 600; font-size: 12px;")
        self.combo_adapters.currentIndexChanged.connect(self._on_adapter_changed)
        row_adapter.addWidget(self.combo_adapters)

        self.lbl_current_dns = QLabel("Mevcut DNS: Yükleniyor...")
        self.lbl_current_dns.setStyleSheet(f"""
            background: rgba(2, 132, 199, 0.12);
            color: {COLOR_ACCENT};
            font-size: 12px;
            font-weight: 600;
            padding: 5px 12px;
            border-radius: 6px;
            border: 1px solid rgba(2, 132, 199, 0.25);
        """)
        row_adapter.addWidget(self.lbl_current_dns)

        row_adapter.addStretch()
        d_layout.addLayout(row_adapter)

        # Row 2: Actions Toolbar (Benchmark, Apply Fastest, Reset DHCP)
        row_toolbar = QHBoxLayout()
        row_toolbar.setSpacing(10)

        self.btn_benchmark = QPushButton("📊  DNS Hızlarını Test Et")
        self.btn_benchmark.setCursor(Qt.PointingHandCursor)
        self.btn_benchmark.setProperty("class", "primary-btn")
        self.btn_benchmark.clicked.connect(self._start_dns_benchmark)
        row_toolbar.addWidget(self.btn_benchmark)

        self.btn_apply_fastest = QPushButton("⚡  En Hızlı DNS'i Ata")
        self.btn_apply_fastest.setCursor(Qt.PointingHandCursor)
        self.btn_apply_fastest.setProperty("class", "success-btn")
        self.btn_apply_fastest.setEnabled(False)
        self.btn_apply_fastest.clicked.connect(self._apply_fastest_dns)
        row_toolbar.addWidget(self.btn_apply_fastest)

        self.btn_reset_dhcp = QPushButton("↩️  DHCP'ye Sıfırla")
        self.btn_reset_dhcp.setCursor(Qt.PointingHandCursor)
        self.btn_reset_dhcp.setProperty("class", "secondary-btn")
        self.btn_reset_dhcp.clicked.connect(self._reset_adapter_to_dhcp)
        row_toolbar.addWidget(self.btn_reset_dhcp)

        row_toolbar.addStretch()
        d_layout.addLayout(row_toolbar)

        # Table of DNS providers
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "DNS Sağlayıcısı", "Sunucu Adresleri", "Özellik / Güvenlik Koruması", "Gecikme (Ping)", "İşlem"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 150)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 110)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 95)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(320)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        d_layout.addWidget(self.table)

        layout.addWidget(dns_card)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Populate initial catalog rows
        self._populate_table(DNS_CATALOG)

        # Asynchronously fetch meta (client IP & Edge server)
        self._fetch_meta_async()

    def _fetch_meta_async(self):
        self.meta_worker = MetaFetchWorker()
        self.meta_worker.finished.connect(self._on_meta_loaded)
        self.meta_worker.start()

    def _on_meta_loaded(self, ip: str, loc: str):
        self.lbl_server_info.setText(f"📍 Sunucu: {loc}  |  IP: {ip}")

    # =========================================================================
    # Speed Test Controls & Slots
    # =========================================================================
    def _start_speed_test(self):
        if self.speed_worker and self.speed_worker.isRunning():
            return

        self.btn_start_speed.setEnabled(False)
        self.btn_cancel_speed.setEnabled(True)
        self.speed_pbar.setValue(5)
        self.lbl_speed_status.setText("Hız testi motoru başlatılıyor...")
        self.lbl_live_speed.setText("⚡ Test Başlatılıyor...")
        self.frame_grade.setVisible(False)

        # Reset stat cards
        self.card_dl.set_value("-- Mbps", "Ölçülüyor...")
        self.card_ul.set_value("-- Mbps", "Bekleniyor...")
        self.card_ping.set_value("-- ms", "Bekleniyor...")
        self.card_jitter.set_value("-- ms", "Bekleniyor...")

        self.speed_worker = SpeedTestWorker()
        self.speed_worker.phase_changed.connect(self._on_speed_phase_changed)
        self.speed_worker.speed_progress.connect(self._on_speed_progress)
        self.speed_worker.finished.connect(self._on_speed_finished)
        self.speed_worker.start()

    def _cancel_speed_test(self):
        if self.speed_worker and self.speed_worker.isRunning():
            self.lbl_speed_status.setText("Test iptal ediliyor...")
            self.speed_worker.cancel()
            self.btn_cancel_speed.setEnabled(False)

    def _on_speed_phase_changed(self, phase: str, msg: str):
        self.lbl_speed_status.setText(msg)
        if phase == "meta":
            self.speed_pbar.setValue(10)
        elif phase == "ping":
            self.speed_pbar.setValue(20)
            self.lbl_live_speed.setText("⚡ Gecikme Ölçülüyor...")
        elif phase == "download":
            self.speed_pbar.setValue(35)
            self.card_dl.set_value("Ölçülüyor...", "Veri çekiliyor")
        elif phase == "upload":
            self.speed_pbar.setValue(65)
            self.card_ul.set_value("Ölçülüyor...", "Veri gönderiliyor")

    def _on_speed_progress(self, mbps: float, pct: int):
        self.speed_pbar.setValue(pct)
        if self.speed_worker and getattr(self.speed_worker.tester, '_cancelled', False):
            return
        if pct < 60:
            self.lbl_live_speed.setText(f"⬇️ İndirme: {mbps:.1f} Mbps")
            self.card_dl.set_value(f"{mbps:.1f} Mbps", "Canlı İndirme Hızı")
        else:
            self.lbl_live_speed.setText(f"⬆️ Yükleme: {mbps:.1f} Mbps")
            self.card_ul.set_value(f"{mbps:.1f} Mbps", "Canlı Yükleme Hızı")

    def _on_speed_finished(self, res: SpeedTestResult | None):
        self.btn_start_speed.setEnabled(True)
        self.btn_cancel_speed.setEnabled(False)

        if not res or res.grade == "İptal Edildi":
            self.lbl_speed_status.setText("Hız testi kullanıcı tarafından durduruldu.")
            self.lbl_live_speed.setText("⏹️ Test Durduruldu")
            self.speed_pbar.setValue(0)
            return

        self.speed_pbar.setValue(100)
        self.lbl_speed_status.setText(f"Test tamamlandı! ({res.timestamp})")
        self.lbl_live_speed.setText(f"✅ İndirme: {res.download_mbps:.1f} Mbps  |  Yükleme: {res.upload_mbps:.1f} Mbps")

        # Update Stat Cards
        self.card_dl.set_value(f"{res.download_mbps:.1f} Mbps", "İndirme Hızı")
        self.card_ul.set_value(f"{res.upload_mbps:.1f} Mbps", "Yükleme Hızı")
        self.card_ping.set_value(f"{res.ping_ms:.1f} ms", "Gecikme (Ping)")
        self.card_jitter.set_value(f"{res.jitter_ms:.1f} ms", "Dalgalanma (Jitter)")

        # Update Server info badge if valid
        if res.client_ip and res.server_location:
            self.lbl_server_info.setText(f"📍 Sunucu: {res.server_location}  |  IP: {res.client_ip}")

        # Update Quality Assessment
        self.lbl_grade_title.setText(f"🌟 Bağlantı Değerlendirmesi: {res.grade}")
        self.lbl_grade_desc.setText(res.grade_description)
        self.frame_grade.setVisible(True)

    # =========================================================================
    # DNS Optimizer Controls & Slots
    # =========================================================================
    def _load_network_info(self):
        """Loads network adapters and sets the active one."""
        self.combo_adapters.clear()
        ifaces = self.optimizer.get_network_interfaces()
        active_idx = 0
        for i, iface in enumerate(ifaces):
            status_text = "Bağlı" if iface["connected"] else "Bağlı Değil"
            self.combo_adapters.addItem(f"{iface['name']} ({status_text})", iface["name"])
            if iface["connected"]:
                active_idx = i

        if ifaces:
            self.combo_adapters.setCurrentIndex(active_idx)
            self._update_current_dns_label(ifaces[active_idx]["name"])
        else:
            self.combo_adapters.addItem("Ağ Bağdaştırıcısı Bulunamadı", "")
            self.lbl_current_dns.setText("Mevcut DNS: Ağ Bağdaştırıcısı Yok")

    def _on_adapter_changed(self):
        adapter = self.combo_adapters.currentData()
        if adapter:
            self._update_current_dns_label(adapter)

    def _update_current_dns_label(self, adapter_name: str):
        dns_info = self.optimizer.get_current_dns(adapter_name)
        if dns_info["is_dhcp"]:
            srvs = ", ".join(dns_info["servers"]) if dns_info["servers"] else "Otomatik Ağ Ataması"
            self.lbl_current_dns.setText(f"Mevcut DNS: Otomatik (DHCP) [{srvs}]")
            self.lbl_current_dns.setToolTip(f"Ağ bağdaştırıcısı DNS adreslerini DHCP üzerinden otomatik alıyor.\nAdresler: {srvs}")
        else:
            srvs = ", ".join(dns_info["servers"]) if dns_info["servers"] else "Statik"
            self.lbl_current_dns.setText(f"Mevcut DNS: Statik [{srvs}]")
            self.lbl_current_dns.setToolTip(f"Ağ bağdaştırıcısına atanmış statik DNS adresleri: {srvs}")

    def _populate_table(self, servers: list[DNSServerInfo]):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(servers))
            theme = get_active_theme_colors()
            for row, s in enumerate(servers):
                # 1. Name with bold font
                name_item = QTableWidgetItem(f"  {s.name}")
                f_name = name_item.font()
                f_name.setBold(True)
                name_item.setFont(f_name)
                name_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 0, name_item)

                # 2. IP Addresses
                ip_item = QTableWidgetItem(f"{s.primary}   /   {s.secondary}")
                ip_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                ip_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 1, ip_item)

                # 3. Description with tooltip
                desc_item = QTableWidgetItem(s.description)
                desc_item.setToolTip(s.description)
                desc_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 2, desc_item)

                # 4. Latency Badge
                if s.latency_ms is not None:
                    lat_str = f"{s.latency_ms} ms"
                    color = theme["COLOR_SUCCESS"] if s.latency_ms < 60 else (theme["COLOR_WARNING"] if s.latency_ms < 100 else theme["COLOR_DANGER"])
                else:
                    lat_str = "Test Edilmedi"
                    color = theme["TEXT_MUTED"]

                lat_item = QTableWidgetItem(lat_str)
                lat_item.setTextAlignment(Qt.AlignCenter)
                lat_item.setForeground(QColor(color))
                f = lat_item.font()
                f.setBold(True)
                lat_item.setFont(f)
                lat_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 3, lat_item)

                # 5. Centered Action button
                btn_use = QPushButton("Uygula")
                btn_use.setCursor(Qt.PointingHandCursor)
                btn_use.setProperty("class", "secondary-btn")
                btn_use.setFixedHeight(28)
                btn_use.setFixedWidth(75)
                btn_use.clicked.connect(lambda checked, srv=s: self._apply_dns(srv))

                cell_w = QWidget()
                cell_l = QHBoxLayout(cell_w)
                cell_l.setContentsMargins(4, 2, 4, 2)
                cell_l.setAlignment(Qt.AlignCenter)
                cell_l.addWidget(btn_use)
                self.table.setCellWidget(row, 4, cell_w)
        finally:
            self.table.setUpdatesEnabled(True)

    def _start_dns_benchmark(self):
        self.btn_benchmark.setEnabled(False)
        self.btn_benchmark.setText("⏳  Test Ediliyor...")
        self.benchmark_worker = DNSBenchmarkWorker()
        self.benchmark_worker.finished.connect(self._on_benchmark_finished)
        self.benchmark_worker.start()

    def _on_benchmark_finished(self, results: list[DNSServerInfo]):
        self.dns_results = results
        self.btn_benchmark.setEnabled(True)
        self.btn_benchmark.setText("📊  DNS Hızlarını Test Et")
        self.btn_apply_fastest.setEnabled(True)
        self._populate_table(results)

    def _apply_dns(self, srv: DNSServerInfo):
        adapter = self.combo_adapters.currentData()
        if not adapter:
            QMessageBox.warning(self, "Hata", "Geçerli bir ağ bağdaştırıcısı seçilmedi.")
            return

        ok, msg = self.optimizer.set_dns(adapter, srv.primary, srv.secondary)
        if ok:
            QMessageBox.information(self, "Başarılı", f"{srv.name} bağdaştırıcıya uygulandı!\n\nBirincil: {srv.primary}\nİkincil: {srv.secondary}")
            self._update_current_dns_label(adapter)
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _apply_fastest_dns(self):
        if not self.dns_results:
            return
        fastest = self.dns_results[0]
        if fastest.latency_ms is None:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir ping sonucu alınamadı.")
            return
        self._apply_dns(fastest)

    def _reset_adapter_to_dhcp(self):
        adapter = self.combo_adapters.currentData()
        if not adapter:
            return
        ok, msg = self.optimizer.reset_dns_to_dhcp(adapter)
        if ok:
            QMessageBox.information(self, "Başarılı", f"{adapter} bağdaştırıcısı otomatik (DHCP) DNS moduna geçirildi.")
            self._update_current_dns_label(adapter)
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _handle_flush_dns(self):
        self.btn_flush.setEnabled(False)
        self.repair_worker = NetworkRepairWorker("flush")
        self.repair_worker.finished.connect(self._on_flush_finished)
        self.repair_worker.start()

    def _on_flush_finished(self, ok: bool, msg: str):
        self.btn_flush.setEnabled(True)
        self.lbl_repair_status.setText(msg)
        self.lbl_repair_status.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS};" if ok else f"font-size: 12px; color: {COLOR_DANGER};")

    def _handle_reset_stack(self):
        reply = QMessageBox.question(
            self,
            "Winsock ve Ağ Yığınını Sıfırla",
            "Bu işlem Windows Winsock ve TCP/IP ağ protokollerini varsayılan fabrika ayarlarına döndürür.\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.btn_reset_stack.setEnabled(False)
            self.repair_worker = NetworkRepairWorker("reset_stack")
            self.repair_worker.finished.connect(self._on_reset_stack_finished)
            self.repair_worker.start()

    def _on_reset_stack_finished(self, ok: bool, msg: str):
        self.btn_reset_stack.setEnabled(True)
        self.lbl_repair_status.setText(msg)
        self.lbl_repair_status.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS};" if ok else f"font-size: 12px; color: {COLOR_DANGER};")
        adapter = self.combo_adapters.currentData()
        if adapter:
            self._update_current_dns_label(adapter)
