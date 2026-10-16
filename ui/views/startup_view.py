"""
NovaCare System Suite - Startup Manager View
Inspects, toggles, and manages Windows startup entries to optimize boot time.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from core.startup_manager import StartupManager, StartupItem
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class StartupScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, mgr: StartupManager):
        super().__init__()
        self.mgr = mgr

    def run(self):
        items = self.mgr.scan_all()
        self.finished.emit(items)

class StartupView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mgr = StartupManager()
        self.items: list[StartupItem] = []
        self.scan_worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Windows Başlangıç Yöneticisi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Bilgisayar açılışında arka planda başlayan uygulamaları yöneterek açılışı hızlandırın.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setProperty("class", "secondary-btn")
        self.btn_refresh.clicked.connect(self.refresh_items)

        self.btn_toggle = QPushButton("⚡  Durumu Değiştir (Aç / Kapat)")
        self.btn_toggle.setProperty("class", "primary-btn")
        self.btn_toggle.clicked.connect(self._toggle_selected)

        self.btn_delete = QPushButton("🗑️  Girişi Sil")
        self.btn_delete.setProperty("class", "danger-btn")
        self.btn_delete.clicked.connect(self._delete_selected)

        self.lbl_stats = QLabel("Toplam: 0")
        self.lbl_stats.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700;")

        tb_layout.addWidget(self.btn_refresh)
        tb_layout.addWidget(self.btn_toggle)
        tb_layout.addWidget(self.btn_delete)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_stats)
        layout.addWidget(toolbar)

        # Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Durum", "Program Adı", "Açılış Etkisi", "Konum", "Çalıştırma Komutu"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 200)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

    def refresh_items(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Yükleniyor...")
        self.lbl_stats.setText("Taranıyor...")
        self.scan_worker = StartupScanWorker(self.mgr)
        self.scan_worker.finished.connect(self._on_items_scanned)
        self.scan_worker.start()

    def _on_items_scanned(self, items: list[StartupItem]):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄  Yenile")
        self.items = items
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(self.items))
            enabled_count = 0
            for row, item in enumerate(self.items):
                if item.enabled:
                    enabled_count += 1

                # Column 0: Status Pill
                status_text = "🟢  Etkin" if item.enabled else "⚪  Devre Dışı"
                status_item = QTableWidgetItem(status_text)
                status_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, status_item)

                # Column 1: Name
                name_item = QTableWidgetItem(item.name)
                name_item.setToolTip(item.name)
                self.table.setItem(row, 1, name_item)

                # Column 2: Boot Impact
                impact_item = QTableWidgetItem(item.boot_impact)
                impact_item.setTextAlignment(Qt.AlignCenter)
                if item.boot_impact == "Yüksek":
                    impact_item.setForeground(QColor(COLOR_DANGER))
                elif item.boot_impact == "Orta":
                    impact_item.setForeground(QColor(COLOR_WARNING))
                else:
                    impact_item.setForeground(QColor(COLOR_SUCCESS))
                self.table.setItem(row, 2, impact_item)

                # Column 3: Location
                loc_item = QTableWidgetItem(item.location)
                self.table.setItem(row, 3, loc_item)

                # Column 4: Command
                cmd_item = QTableWidgetItem(item.command)
                cmd_item.setToolTip(item.command)
                self.table.setItem(row, 4, cmd_item)
        finally:
            self.table.setUpdatesEnabled(True)

        self.lbl_stats.setText(f"Toplam: {len(self.items)}  |  Etkin: {enabled_count}  |  Devre Dışı: {len(self.items) - enabled_count}")

    def _get_selected_item(self) -> StartupItem | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.items):
            return self.items[row]
        return None

    def _toggle_selected(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen durumunu değiştirmek istediğiniz bir başlangıç programı seçin.")
            return

        if self.mgr.toggle_item(item):
            self.refresh_items()
        else:
            QMessageBox.critical(self, "Hata", "Giriş durumu değiştirilemedi. Yetki veya erişim engeli olabilir.")

    def _delete_selected(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz bir başlangıç programı seçin.")
            return

        confirm = QMessageBox.question(
            self,
            "Girişi Sil",
            f"'{item.name}' başlangıç kaydı kalıcı olarak silinecek. Onaylıyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            if self.mgr.delete_item(item):
                self.refresh_items()
            else:
                QMessageBox.critical(self, "Hata", "Kayıt silinemedi.")
