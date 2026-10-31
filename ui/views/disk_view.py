"""
NovaCare System Suite - Disk Analyzer & Large Files View
Visualizes partition space and finds the largest files consuming disk storage.
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox,
    QFrame, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.disk_analyzer import DiskAnalyzer, LargeFileInfo
from core.utils import log_debug
from ui.styles import BG_CARD, BORDER_COLOR, COLOR_ACCENT, TEXT_SECONDARY

class LargeFileScanThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(list)

    def __init__(self, analyzer: DiskAnalyzer, target_dir: str, min_size_mb: int, limit: int):
        super().__init__()
        self.analyzer = analyzer
        self.target_dir = target_dir
        self.min_size_mb = min_size_mb
        self.limit = limit

    def run(self):
        files = []
        try:
            files = self.analyzer.scan_largest_files(
                self.target_dir,
                limit=self.limit,
                min_size_mb=self.min_size_mb,
                progress_callback=lambda path, count: self.progress.emit(path, count),
                cancel_check=self.isInterruptionRequested
            )
        except Exception as e:
            log_debug(f"LargeFileScanThread error: {e}")
        finally:
            self.finished.emit(files)

class DiskView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = DiskAnalyzer()
        self.large_files: list[LargeFileInfo] = []
        self.scan_thread = None
        self._init_ui()
        self.refresh_drives()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Disk Alanı ve Büyük Dosya Analizörü")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Sürücü doluluk oranlarını inceleyin ve diskinizi dolduran devasa dosyaları kolayca tespit edin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Drive overview container
        self.drives_container = QFrame()
        self.drives_container.setObjectName("CardFrame")
        self.drives_layout = QHBoxLayout(self.drives_container)
        self.drives_layout.setContentsMargins(16, 14, 16, 14)
        self.drives_layout.setSpacing(16)
        layout.addWidget(self.drives_container)

        # Large File Scanner Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        lbl_target = QLabel("Hedef Sürücü / Klasör:")
        self.combo_target = QComboBox()
        self.combo_target.setStyleSheet("padding: 6px 12px; font-weight: 600;")
        self.combo_target.setFixedWidth(160)

        lbl_size = QLabel("Min Boyut:")
        self.combo_min_size = QComboBox()
        self.combo_min_size.addItems(["50 MB", "100 MB", "250 MB", "500 MB", "1 GB"])
        self.combo_min_size.setCurrentIndex(1) # 100 MB
        self.combo_min_size.setFixedWidth(100)

        self.btn_scan = QPushButton("🔍  Büyük Dosyaları Tara")
        self.btn_scan.setProperty("class", "primary-btn")
        self.btn_scan.clicked.connect(self._start_scan)

        self.btn_open = QPushButton("📂  Konumu Aç")
        self.btn_open.setProperty("class", "secondary-btn")
        self.btn_open.clicked.connect(self._open_file_location)

        self.btn_delete = QPushButton("🗑️  Dosyayı Sil")
        self.btn_delete.setProperty("class", "danger-btn")
        self.btn_delete.clicked.connect(self._delete_file)

        tb_layout.addWidget(lbl_target)
        tb_layout.addWidget(self.combo_target)
        tb_layout.addSpacing(10)
        tb_layout.addWidget(lbl_size)
        tb_layout.addWidget(self.combo_min_size)
        tb_layout.addSpacing(10)
        tb_layout.addWidget(self.btn_scan)
        tb_layout.addWidget(self.btn_open)
        tb_layout.addWidget(self.btn_delete)
        tb_layout.addStretch()
        layout.addWidget(toolbar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_status)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Dosya Adı", "Kategori", "Boyut", "Tam Dosya Yolu"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 240)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh_drives(self):
        # Clear drive cards
        while self.drives_layout.count():
            item = self.drives_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        partitions = self.analyzer.get_partitions()
        self.combo_target.clear()

        # Add user profile folder as option
        user_home = os.path.expanduser('~')
        self.combo_target.addItem(f"👤 Kullanıcı Klasörü ({user_home})", user_home)

        for part in partitions:
            self.combo_target.addItem(f"💾 Sürücü {part.mountpoint}", part.mountpoint)

            # Create Drive Card
            card = QFrame()
            card.setStyleSheet(f"""
                background-color: {BG_CARD};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 10px 14px;
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(8, 6, 8, 6)
            c_lay.setSpacing(4)

            top_row = QHBoxLayout()
            lbl_name = QLabel(f"<b>Sürücü ({part.mountpoint})</b> - {part.fstype}")
            lbl_pct = QLabel(f"<b>{part.percent}%</b>")
            lbl_pct.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px;")
            top_row.addWidget(lbl_name)
            top_row.addStretch()
            top_row.addWidget(lbl_pct)
            c_lay.addLayout(top_row)

            bar = QProgressBar()
            bar.setFixedHeight(12)
            bar.setValue(int(part.percent))
            c_lay.addWidget(bar)

            lbl_detail = QLabel(f"Boş: {part.free_str} / Toplam: {part.total_str}")
            lbl_detail.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            c_lay.addWidget(lbl_detail)

            self.drives_layout.addWidget(card)

    def stop_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.requestInterruption()
            self.scan_thread.wait(500)
            self.btn_scan.setText("🔍  Büyük Dosyaları Tara")
            self.progress_bar.setVisible(False)
            self.lbl_status.setText("Tarama durduruldu.")

    def hideEvent(self, event):
        self.stop_scan()
        super().hideEvent(event)

    def _start_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.stop_scan()
            return

        target_dir = self.combo_target.currentData()
        if not target_dir or not os.path.exists(target_dir):
            target_dir = os.path.expanduser('~')

        size_text = self.combo_min_size.currentText()
        size_map = {"50 MB": 50, "100 MB": 100, "250 MB": 250, "500 MB": 500, "1 GB": 1024}
        min_mb = size_map.get(size_text, 100)

        self.btn_scan.setText("⏹️  Taramayı Durdur")
        self.btn_scan.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate pulse

        self.scan_thread = LargeFileScanThread(self.analyzer, target_dir, min_mb, 100)
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_progress(self, path: str, count: int):
        self.lbl_status.setText(f"Taranan dosya: {count:,}  |  Dizin: {path[:60]}...")

    def _on_scan_finished(self, files: list[LargeFileInfo]):
        self.large_files = files
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setText("🔍  Büyük Dosyaları Tara")
        self.btn_scan.setEnabled(True)

        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(files))
            for row, f in enumerate(files):
                name_item = QTableWidgetItem(f.name)
                self.table.setItem(row, 0, name_item)

                cat_item = QTableWidgetItem(f.category)
                cat_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 1, cat_item)

                sz_item = QTableWidgetItem(f.size_str)
                sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 2, sz_item)

                path_item = QTableWidgetItem(f.path)
                path_item.setToolTip(f.path)
                self.table.setItem(row, 3, path_item)
        finally:
            self.table.setUpdatesEnabled(True)

    def _open_file_location(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.large_files):
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen konumunu açmak istediğiniz bir dosya seçin.")
            return

        fpath = self.large_files[row].path
        if os.path.exists(fpath):
            norm = os.path.normpath(fpath)
            subprocess.Popen(f'explorer.exe /select,"{norm}"')
        else:
            QMessageBox.warning(self, "Bulunamadı", "Dosya diskte mevcut değil.")

    def _delete_file(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.large_files):
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz bir dosya seçin.")
            return

        target = self.large_files[row]
        confirm = QMessageBox.question(
            self,
            "Dosyayı Sil",
            f"'{target.name}' ({target.size_str}) kalıcı olarak silinecek.\nEmin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            if self.analyzer.delete_file(target.path):
                self.table.removeRow(row)
                self.large_files.pop(row)
                QMessageBox.information(self, "Silindi", "Dosya başarıyla silindi.")
            else:
                QMessageBox.critical(self, "Hata", "Dosya silinemedi. Başka bir program tarafından kullanılıyor olabilir.")
