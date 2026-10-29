"""
NovaCare System Suite - Memory Optimizer & Process Manager View
Real-time RAM/CPU meters, RAM working set trimmer, and threaded process manager.
Optimized for zero-lag background loading and smooth high-performance UI rendering.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QMessageBox, QFrame,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from core.memory_booster import MemoryBooster, ProcessInfo
from core.utils import format_bytes
from ui.styles import COLOR_ACCENT, TEXT_SECONDARY

class ProcessLoaderWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, booster: MemoryBooster):
        super().__init__()
        self.booster = booster

    def run(self):
        try:
            procs = self.booster.list_processes()
            self.finished.emit(procs)
        except Exception:
            self.finished.emit([])

class MemoryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.booster = MemoryBooster()
        self.all_processes: list[ProcessInfo] = []
        self.loader_worker = None
        self._is_loading = False

        # Debounce timer for search
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self._filter_processes)

        self._init_ui()
        self._start_timer()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Bellek (RAM) ve Süreç Yöneticisi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Arka planda çalışan uygulamaları denetleyin ve tek tıkla boşta duran RAM belleğini geri kazanın.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Performance Overview Card
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        card_layout = QHBoxLayout(top_card)
        card_layout.setContentsMargins(20, 16, 20, 16)

        # Left: RAM meter
        ram_box = QVBoxLayout()
        self.lbl_ram_title = QLabel("Bellek (RAM) Kullanımı: 0%")
        self.lbl_ram_title.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.bar_ram = QProgressBar()
        self.bar_ram.setFixedHeight(16)
        self.lbl_ram_detail = QLabel("Kullanılan: -  |  Toplam: -")
        self.lbl_ram_detail.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        ram_box.addWidget(self.lbl_ram_title)
        ram_box.addWidget(self.bar_ram)
        ram_box.addWidget(self.lbl_ram_detail)
        card_layout.addLayout(ram_box, stretch=2)

        card_layout.addSpacing(24)

        # Middle: CPU meter
        cpu_box = QVBoxLayout()
        self.lbl_cpu_title = QLabel("İşlemci (CPU) Yükü: 0%")
        self.lbl_cpu_title.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.bar_cpu = QProgressBar()
        self.bar_cpu.setFixedHeight(16)
        self.lbl_cpu_detail = QLabel("Tüm Çekirdekler Aktif")
        self.lbl_cpu_detail.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        cpu_box.addWidget(self.lbl_cpu_title)
        cpu_box.addWidget(self.bar_cpu)
        cpu_box.addWidget(self.lbl_cpu_detail)
        card_layout.addLayout(cpu_box, stretch=2)

        card_layout.addSpacing(24)

        # Right: Boost RAM Button
        self.btn_boost = QPushButton("⚡  RAM'İ HIZLANDIR\nVE BOŞALT")
        self.btn_boost.setProperty("class", "success-btn")
        self.btn_boost.setFixedHeight(56)
        self.btn_boost.setCursor(Qt.PointingHandCursor)
        self.btn_boost.clicked.connect(self._boost_ram)
        card_layout.addWidget(self.btn_boost, stretch=1)

        layout.addWidget(top_card)

        # Process Toolbar
        p_toolbar = QFrame()
        p_toolbar.setObjectName("ToolbarFrame")
        ptb_layout = QHBoxLayout(p_toolbar)
        ptb_layout.setContentsMargins(12, 8, 12, 8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Süreç veya PID ara...")
        self.search_box.setFixedWidth(240)
        self.search_box.textChanged.connect(self._on_search_changed)

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setProperty("class", "secondary-btn")
        self.btn_refresh.clicked.connect(self.refresh_processes)

        self.btn_kill = QPushButton("❌  Görevi Sonlandır")
        self.btn_kill.setProperty("class", "danger-btn")
        self.btn_kill.clicked.connect(self._kill_selected)

        self.lbl_proc_count = QLabel("Toplam Süreç: 0")
        self.lbl_proc_count.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700;")

        ptb_layout.addWidget(self.search_box)
        ptb_layout.addWidget(self.btn_refresh)
        ptb_layout.addWidget(self.btn_kill)
        ptb_layout.addStretch()
        ptb_layout.addWidget(self.lbl_proc_count)
        layout.addWidget(p_toolbar)

        # Process Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["PID", "İşlem Adı", "Bellek (MB)", "CPU (%)", "Kullanıcı"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

    def _start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(3500)
        self._on_timer_tick()

    def _on_timer_tick(self):
        # Only update live meters when this view is currently the active tab
        if not self.isVisible():
            return
        if self.parent() and hasattr(self.parent(), 'currentWidget') and self.parent().currentWidget() != self:
            return

        try:
            metrics = self.booster.get_system_metrics()
            ram_pct = int(metrics["ram_percent"])
            cpu_pct = int(metrics["cpu_percent"])

            self.bar_ram.setValue(ram_pct)
            self.lbl_ram_title.setText(f"Bellek (RAM) Kullanımı: {ram_pct}%")
            self.lbl_ram_detail.setText(f"Kullanılan: {metrics['ram_used_str']}  |  Toplam: {metrics['ram_total_str']}  |  Boş: {metrics['ram_free_str']}")

            self.bar_cpu.setValue(cpu_pct)
            self.lbl_cpu_title.setText(f"İşlemci (CPU) Yükü: {cpu_pct}%")
        except Exception:
            pass

    def _on_search_changed(self):
        self.search_timer.start()

    def refresh_processes(self):
        if self._is_loading:
            return
        self._is_loading = True
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Yükleniyor...")

        self.loader_worker = ProcessLoaderWorker(self.booster)
        self.loader_worker.finished.connect(self._on_processes_loaded)
        self.loader_worker.start()

    def _on_processes_loaded(self, procs: list):
        self._is_loading = False
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄  Yenile")
        self.all_processes = procs
        self._filter_processes()

    def _filter_processes(self):
        query = self.search_box.text().strip().lower()
        if not query:
            filtered = self.all_processes
        else:
            filtered = [p for p in self.all_processes if query in p.name.lower() or query == str(p.pid)]

        # Batch table update to eliminate redraw stutter
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(filtered))
            for row, p in enumerate(filtered):
                pid_item = QTableWidgetItem(str(p.pid))
                pid_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, pid_item)

                name_item = QTableWidgetItem(p.name)
                self.table.setItem(row, 1, name_item)

                mem_item = QTableWidgetItem(f"{p.memory_mb:,.1f} MB")
                mem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 2, mem_item)

                cpu_item = QTableWidgetItem(f"{p.cpu_percent}%")
                cpu_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, cpu_item)

                user_item = QTableWidgetItem(p.username)
                self.table.setItem(row, 4, user_item)
        finally:
            self.table.setUpdatesEnabled(True)

        self.lbl_proc_count.setText(f"Toplam Süreç: {len(filtered)}")

    def _boost_ram(self):
        self.btn_boost.setEnabled(False)
        self.btn_boost.setText("⏳  Bellek Boşaltılıyor...")

        freed_bytes, count = self.booster.optimize_ram()
        freed_str = format_bytes(freed_bytes)

        self.btn_boost.setText("⚡  RAM'İ HIZLANDIR\nVE BOŞALT")
        self.btn_boost.setEnabled(True)

        self._on_timer_tick()
        self.refresh_processes()

        QMessageBox.information(
            self,
            "RAM Hızlandırma Başarılı",
            f"Bellek optimizasyonu tamamlandı!\n\n"
            f"• Boşaltılan / Geri Kazanılan RAM: {freed_str}\n"
            f"• Optimize Edilen Süreç Sayısı: {count} adet"
        )

    def _kill_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen sonlandırmak istediğiniz bir işlem seçin.")
            return

        pid_item = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        if not pid_item or not name_item:
            return

        pid_text = pid_item.text()
        name_text = name_item.text()
        try:
            pid = int(pid_text)
        except ValueError:
            return

        confirm = QMessageBox.question(
            self,
            "Görevi Sonlandır",
            f"'{name_text}' (PID: {pid}) işlemini sonlandırmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            if self.booster.kill_process(pid):
                self.refresh_processes()
            else:
                QMessageBox.critical(self, "Hata", "İşlem sonlandırılamadı. Sistem korumalı bir işlem veya yetki kısıtlaması olabilir.")
