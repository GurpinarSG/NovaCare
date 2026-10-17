"""
NovaCare System Suite - Network & DNS Optimizer View
Real-time DNS latency benchmark, 1-click DNS assignment, DHCP reset,
and complete network stack (Winsock, TCP/IP, flushdns) repair.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QScrollArea, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from core.network_optimizer import NetworkOptimizer, DNSServerInfo, DNS_CATALOG
from core.utils import log_debug
from ui.styles import (
    get_active_theme_colors, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER
)

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
        self.dns_results: list[DNSServerInfo] = []
        self._init_ui()
        self._load_network_info()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Scroll Area for clean overflow
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("NetworkScroll")
        scroll.setStyleSheet("QScrollArea#NetworkScroll { background: transparent; border: none; } QWidget#NetworkContainer { background: transparent; }")

        container = QWidget()
        container.setObjectName("NetworkContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # 1. Header
        header = QVBoxLayout()
        header.setSpacing(4)
        lbl_title = QLabel("🌐  Ağ ve DNS Optimize Edici")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 800;")
        header.addWidget(lbl_title)

        lbl_sub = QLabel("İnternet bağlantınızı onarın, DNS gecikmelerini (ping) test edin ve en hızlı DNS sunucusunu tek tıkla aktif edin.")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        lbl_sub.setWordWrap(True)
        header.addWidget(lbl_sub)
        layout.addLayout(header)

        # 2. Network Repair & Flush Card
        repair_card = QFrame()
        repair_card.setObjectName("CardFrame")
        r_layout = QVBoxLayout(repair_card)
        r_layout.setContentsMargins(18, 16, 18, 16)
        r_layout.setSpacing(12)

        lbl_r_title = QLabel("⚡  Hızlı Ağ Onarımı ve Çözümleyici")
        lbl_r_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        r_layout.addWidget(lbl_r_title)

        r_btns = QHBoxLayout()
        r_btns.setSpacing(12)

        self.btn_flush = QPushButton("🧹  DNS Önbelleğini Temizle")
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

        self.lbl_repair_status = QLabel("Ağ durumu normal. Bağlantı sorunlarında önbellek temizliğini kullanabilirsiniz.")
        self.lbl_repair_status.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS};")
        self.lbl_repair_status.setWordWrap(True)
        r_layout.addWidget(self.lbl_repair_status)

        layout.addWidget(repair_card)

        # 3. DNS Benchmark & Switcher Card
        dns_card = QFrame()
        dns_card.setObjectName("CardFrame")
        d_layout = QVBoxLayout(dns_card)
        d_layout.setContentsMargins(18, 16, 18, 16)
        d_layout.setSpacing(14)

        # Top Bar: Adapter Selector & Current DNS
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        lbl_adapter = QLabel("Bağdaştırıcı:")
        lbl_adapter.setStyleSheet("font-weight: 600; font-size: 12px;")
        top_row.addWidget(lbl_adapter)

        self.combo_adapters = QComboBox()
        self.combo_adapters.setMinimumWidth(180)
        self.combo_adapters.currentIndexChanged.connect(self._on_adapter_changed)
        top_row.addWidget(self.combo_adapters)

        self.lbl_current_dns = QLabel("Mevcut DNS: Yükleniyor...")
        self.lbl_current_dns.setStyleSheet(f"font-size: 12px; color: {COLOR_ACCENT}; font-weight: 600;")
        top_row.addWidget(self.lbl_current_dns)

        top_row.addStretch()

        self.btn_benchmark = QPushButton("📊  DNS Hızlarını Test Et")
        self.btn_benchmark.setCursor(Qt.PointingHandCursor)
        self.btn_benchmark.setProperty("class", "primary-btn")
        self.btn_benchmark.clicked.connect(self._start_dns_benchmark)
        top_row.addWidget(self.btn_benchmark)

        self.btn_apply_fastest = QPushButton("⚡  En Hızlı DNS'i Ata")
        self.btn_apply_fastest.setCursor(Qt.PointingHandCursor)
        self.btn_apply_fastest.setProperty("class", "success-btn")
        self.btn_apply_fastest.setEnabled(False)
        self.btn_apply_fastest.clicked.connect(self._apply_fastest_dns)
        top_row.addWidget(self.btn_apply_fastest)

        self.btn_reset_dhcp = QPushButton("↩️  DHCP'ye Sıfırla")
        self.btn_reset_dhcp.setCursor(Qt.PointingHandCursor)
        self.btn_reset_dhcp.setProperty("class", "secondary-btn")
        self.btn_reset_dhcp.clicked.connect(self._reset_adapter_to_dhcp)
        top_row.addWidget(self.btn_reset_dhcp)

        d_layout.addLayout(top_row)

        # Table of DNS providers
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "DNS Sağlayıcısı", "Sunucu Adresleri", "Özellik / Güvenlik", "Gecikme (Ping)", "İşlem"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setMinimumHeight(240)
        d_layout.addWidget(self.table)

        layout.addWidget(dns_card)
        layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Populate initial catalog rows
        self._populate_table(DNS_CATALOG)

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
        else:
            srvs = ", ".join(dns_info["servers"]) if dns_info["servers"] else "Statik"
            self.lbl_current_dns.setText(f"Mevcut DNS: Statik [{srvs}]")

    def _populate_table(self, servers: list[DNSServerInfo]):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(servers))
            for row, s in enumerate(servers):
                # Name
                name_item = QTableWidgetItem(f"  {s.name}")
                name_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 0, name_item)

                # IPs
                ip_item = QTableWidgetItem(f"{s.primary} / {s.secondary}")
                ip_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 1, ip_item)

                # Description
                desc_item = QTableWidgetItem(s.description)
                desc_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 2, desc_item)

                # Latency Badge
                theme = get_active_theme_colors()
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

                # Action button
                btn_use = QPushButton("Uygula")
                btn_use.setCursor(Qt.PointingHandCursor)
                btn_use.setProperty("class", "secondary-btn")
                btn_use.clicked.connect(lambda checked, srv=s: self._apply_dns(srv))
                self.table.setCellWidget(row, 4, btn_use)
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
