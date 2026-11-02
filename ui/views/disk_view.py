"""
NovaCare System Suite - Disk Analyzer & Duplicate File Finder View
Visualizes partition space, finds large files, and discovers identical duplicate files
using multi-tier MD5 hashing with 1-click intelligent cleanup.
"""
import os
import subprocess
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox,
    QFrame, QAbstractItemView, QTabWidget, QFileDialog, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from core.disk_analyzer import DiskAnalyzer, LargeFileInfo
from core.duplicate_finder import DuplicateFinder, DuplicateGroup
from core.utils import log_debug, format_bytes
from ui.styles import BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, TEXT_SECONDARY

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

class DuplicateScanThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)

    def __init__(self, finder: DuplicateFinder, target_dirs: list[str], min_size_bytes: int):
        super().__init__()
        self.finder = finder
        self.target_dirs = target_dirs
        self.min_size_bytes = min_size_bytes

    def run(self):
        groups = []
        try:
            groups = self.finder.scan_duplicates(
                self.target_dirs,
                min_size_bytes=self.min_size_bytes,
                progress_callback=lambda p, s, d: self.progress.emit(p, s, d),
                cancel_check=self.isInterruptionRequested
            )
        except Exception as e:
            log_debug(f"DuplicateScanThread error: {e}")
        finally:
            self.finished.emit(groups)

class DiskView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = DiskAnalyzer()
        self.duplicate_finder = DuplicateFinder()
        self.large_files: list[LargeFileInfo] = []
        self.duplicate_groups: list[DuplicateGroup] = []
        self.scan_thread = None
        self.dup_thread = None

        self._init_ui()
        self.refresh_drives()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # Header
        lbl_title = QLabel("Disk Alanı ve Depolama Yönetimi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Sürücü doluluk oranlarını inceleyin, devasa dosyaları bulun ve yinelenen kopyaları temizleyin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tab_large_files = QWidget()
        self.tab_duplicates = QWidget()

        self._build_large_files_tab()
        self._build_duplicates_tab()

        self.tabs.addTab(self.tab_large_files, "📊  Sürücü Alanı & Büyük Dosya Analizörü")
        self.tabs.addTab(self.tab_duplicates, "🔍  Yinelenen Dosya Bulucu (Duplicate Finder)")
        layout.addWidget(self.tabs)

    def _build_large_files_tab(self):
        tab_lay = QVBoxLayout(self.tab_large_files)
        tab_lay.setContentsMargins(10, 12, 10, 10)
        tab_lay.setSpacing(12)

        # Drive overview container
        self.drives_container = QFrame()
        self.drives_container.setObjectName("CardFrame")
        self.drives_layout = QHBoxLayout(self.drives_container)
        self.drives_layout.setContentsMargins(14, 10, 14, 10)
        self.drives_layout.setSpacing(14)
        tab_lay.addWidget(self.drives_container)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 8, 10, 8)

        lbl_target = QLabel("Hedef:")
        self.combo_target = QComboBox()
        self.combo_target.setMinimumWidth(220)

        lbl_size = QLabel("Min Boyut:")
        self.combo_min_size = QComboBox()
        self.combo_min_size.addItems(["50 MB", "100 MB", "250 MB", "500 MB", "1 GB"])
        self.combo_min_size.setCurrentIndex(1) # 100 MB
        self.combo_min_size.setFixedWidth(90)

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
        tb_layout.addSpacing(8)
        tb_layout.addWidget(lbl_size)
        tb_layout.addWidget(self.combo_min_size)
        tb_layout.addSpacing(8)
        tb_layout.addWidget(self.btn_scan)
        tb_layout.addWidget(self.btn_open)
        tb_layout.addWidget(self.btn_delete)
        tb_layout.addStretch()
        tab_lay.addWidget(toolbar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_status.setVisible(False)
        tab_lay.addWidget(self.progress_bar)
        tab_lay.addWidget(self.lbl_status)

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
        tab_lay.addWidget(self.table)

    def _build_duplicates_tab(self):
        tab_lay = QVBoxLayout(self.tab_duplicates)
        tab_lay.setContentsMargins(10, 12, 10, 10)
        tab_lay.setSpacing(12)

        # Duplicate Toolbar
        tb = QFrame()
        tb.setObjectName("ToolbarFrame")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(10, 8, 10, 8)
        tb_lay.setSpacing(8)

        lbl_loc = QLabel("Hedef Konum:")
        self.combo_dup_target = QComboBox()
        self.combo_dup_target.setMinimumWidth(220)

        btn_browse = QPushButton("📁 Gözat...")
        btn_browse.setProperty("class", "secondary-btn")
        btn_browse.clicked.connect(self._browse_dup_target)

        lbl_min = QLabel("Min Boyut:")
        self.combo_dup_min = QComboBox()
        self.combo_dup_min.addItems(["1 KB", "100 KB", "1 MB", "10 MB", "50 MB"])
        self.combo_dup_min.setCurrentIndex(1) # 100 KB
        self.combo_dup_min.setFixedWidth(85)

        self.btn_dup_scan = QPushButton("🔍  Yinelenenleri Tara")
        self.btn_dup_scan.setProperty("class", "primary-btn")
        self.btn_dup_scan.clicked.connect(self._toggle_duplicate_scan)

        tb_lay.addWidget(lbl_loc)
        tb_lay.addWidget(self.combo_dup_target)
        tb_lay.addWidget(btn_browse)
        tb_lay.addSpacing(6)
        tb_lay.addWidget(lbl_min)
        tb_lay.addWidget(self.combo_dup_min)
        tb_lay.addSpacing(6)
        tb_lay.addWidget(self.btn_dup_scan)
        tb_lay.addStretch()
        tab_lay.addWidget(tb)

        # Actions Toolbar (Select helpers & Delete)
        act_bar = QHBoxLayout()
        act_bar.setSpacing(8)

        self.btn_auto_old = QPushButton("🎯  En Eskileri Koru (Yenileri Seç)")
        self.btn_auto_old.setProperty("class", "secondary-btn")
        self.btn_auto_old.clicked.connect(lambda: self._apply_auto_selection("oldest"))

        self.btn_auto_new = QPushButton("🎯  En Yenileri Koru (Eskileri Seç)")
        self.btn_auto_new.setProperty("class", "secondary-btn")
        self.btn_auto_new.clicked.connect(lambda: self._apply_auto_selection("newest"))

        self.btn_dup_delete = QPushButton("🗑️  Seçilen Yinelenenleri Sil")
        self.btn_dup_delete.setProperty("class", "danger-btn")
        self.btn_dup_delete.clicked.connect(self._delete_selected_duplicates)

        act_bar.addWidget(self.btn_auto_old)
        act_bar.addWidget(self.btn_auto_new)
        act_bar.addStretch()
        act_bar.addWidget(self.btn_dup_delete)
        tab_lay.addLayout(act_bar)

        # Duplicate Progress & Status
        self.dup_progress = QProgressBar()
        self.dup_progress.setVisible(False)
        self.lbl_dup_status = QLabel("MD5 tabanlı derin analiz ile aynı içeriğe sahip dosyaları bulun.")
        self.lbl_dup_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        tab_lay.addWidget(self.dup_progress)
        tab_lay.addWidget(self.lbl_dup_status)

        # Duplicate Table
        self.dup_table = QTableWidget()
        self.dup_table.setColumnCount(5)
        self.dup_table.setHorizontalHeaderLabels(["Seçim", "Dosya Adı", "Durum", "Boyut", "Tam Dosya Yolu"])
        self.dup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.dup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.dup_table.setColumnWidth(1, 220)
        self.dup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.dup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.dup_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.dup_table.verticalHeader().setVisible(False)
        self.dup_table.setAlternatingRowColors(True)
        self.dup_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dup_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dup_table.itemDoubleClicked.connect(self._on_dup_row_double_click)
        tab_lay.addWidget(self.dup_table)

    def refresh_drives(self):
        while self.drives_layout.count():
            item = self.drives_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        partitions = self.analyzer.get_partitions()
        self.combo_target.clear()
        self.combo_dup_target.clear()

        user_home = os.path.expanduser('~')
        self.combo_target.addItem(f"👤 Kullanıcı Klasörü ({user_home})", user_home)
        self.combo_dup_target.addItem(f"👤 Kullanıcı Klasörü ({user_home})", user_home)

        # Common user subfolders for duplicates
        for sub in ("Downloads", "Documents", "Pictures", "Videos", "Desktop"):
            sub_p = os.path.join(user_home, sub)
            if os.path.exists(sub_p):
                self.combo_dup_target.addItem(f"📁 {sub} ({sub_p})", sub_p)

        for part in partitions:
            self.combo_target.addItem(f"💾 Sürücü {part.mountpoint}", part.mountpoint)
            self.combo_dup_target.addItem(f"💾 Sürücü {part.mountpoint}", part.mountpoint)

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

    def _browse_dup_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Taranacak Klasörü Seçin")
        if folder:
            self.combo_dup_target.insertItem(0, f"📂 {folder}", folder)
            self.combo_dup_target.setCurrentIndex(0)

    # Large file methods
    def _start_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.stop_scan()
            return

        target_dir = self.combo_target.currentData() or os.path.expanduser('~')
        size_str = self.combo_min_size.currentText()
        size_map = {"50 MB": 50, "100 MB": 100, "250 MB": 250, "500 MB": 500, "1 GB": 1024}
        min_size = size_map.get(size_str, 100)

        self.btn_scan.setText("⏹️  Taramayı Durdur")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText(f"{target_dir} taranıyor...")
        self.table.setRowCount(0)

        self.scan_thread = LargeFileScanThread(self.analyzer, target_dir, min_size, limit=50)
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_progress(self, path: str, count: int):
        self.lbl_status.setText(f"Taranan: {count:,} dosya | {path[:65]}...")

    def _on_scan_finished(self, files: list[LargeFileInfo]):
        self.btn_scan.setText("🔍  Büyük Dosyaları Tara")
        self.progress_bar.setVisible(False)
        self.large_files = files

        if not files:
            self.lbl_status.setText("Belirtilen boyuttan büyük dosya bulunamadı.")
            return

        total_sz = sum(f.size_bytes for f in files)
        self.lbl_status.setText(f"Tarama tamamlandı! En büyük {len(files)} dosya listelendi (Toplam: {format_bytes(total_sz)}).")

        self.table.setRowCount(len(files))
        for row, f in enumerate(files):
            self.table.setItem(row, 0, QTableWidgetItem(f.name))
            self.table.setItem(row, 1, QTableWidgetItem(f.category))
            sz_item = QTableWidgetItem(f.size_str)
            sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, sz_item)
            self.table.setItem(row, 3, QTableWidgetItem(f.path))

    def _open_file_location(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.large_files):
            QMessageBox.information(self, "Bilgi", "Lütfen konumunu açmak istediğiniz dosyayı seçin.")
            return

        path = self.large_files[row].path
        if os.path.exists(path):
            norm = os.path.normpath(path)
            subprocess.Popen(f'explorer.exe /select,"{norm}"')
        else:
            QMessageBox.warning(self, "Uyarı", "Dosya bulunamadı veya taşınmış.")

    def _delete_file(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.large_files):
            QMessageBox.information(self, "Bilgi", "Lütfen silmek istediğiniz dosyayı seçin.")
            return

        target = self.large_files[row]
        ans = QMessageBox.question(
            self,
            "Dosyayı Sil",
            f"<b>{target.name}</b> ({target.size_str}) dosyasını kalıcı olarak silmek istediğinizden emin misiniz?\n\nKonum: {target.path}",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans == QMessageBox.Yes:
            ok, msg = self.analyzer.delete_file_safely(target.path)
            if ok:
                QMessageBox.information(self, "Başarılı", "Dosya başarıyla silindi.")
                self.table.removeRow(row)
                self.large_files.pop(row)
            else:
                QMessageBox.warning(self, "Hata", f"Dosya silinemedi: {msg}")

    # Duplicate finder methods
    def _toggle_duplicate_scan(self):
        if self.dup_thread and self.dup_thread.isRunning():
            self.dup_thread.requestInterruption()
            self.dup_thread.wait(500)
            self.btn_dup_scan.setText("🔍  Yinelenenleri Tara")
            self.dup_progress.setVisible(False)
            self.lbl_dup_status.setText("Tarama durduruldu.")
            return

        target_dir = self.combo_dup_target.currentData() or os.path.expanduser('~')
        min_map = {"1 KB": 1024, "100 KB": 102400, "1 MB": 1048576, "10 MB": 10485760, "50 MB": 52428800}
        min_bytes = min_map.get(self.combo_dup_min.currentText(), 102400)

        self.btn_dup_scan.setText("⏹️  Durdur")
        self.dup_progress.setVisible(True)
        self.dup_progress.setRange(0, 0)
        self.lbl_dup_status.setText(f"MD5 hash hesaplanıyor: {target_dir}...")
        self.dup_table.setRowCount(0)
        self.duplicate_groups.clear()

        self.dup_thread = DuplicateScanThread(self.duplicate_finder, [target_dir], min_bytes)
        self.dup_thread.progress.connect(self._on_dup_progress)
        self.dup_thread.finished.connect(self._on_dup_finished)
        self.dup_thread.start()

    def _on_dup_progress(self, path: str, scanned: int, found_dups: int):
        self.lbl_dup_status.setText(f"Taranan: {scanned:,} dosya | Tespit Edilen Kopya: {found_dups} | {os.path.basename(path)[:40]}")

    def _on_dup_finished(self, groups: list[DuplicateGroup]):
        self.btn_dup_scan.setText("🔍  Yinelenenleri Tara")
        self.dup_progress.setVisible(False)
        self.duplicate_groups = groups

        if not groups:
            self.lbl_dup_status.setText("Tebrikler! Belirtilen konumda yinelenen dosya bulunamadı.")
            return

        total_wasted = sum(g.wasted_size for g in groups)
        dup_file_count = sum(len(g.files) - 1 for g in groups)
        self.lbl_dup_status.setText(
            f"Tarama tamamlandı! <b>{len(groups)}</b> kopya kümesinde toplam <b>{dup_file_count}</b> yinelenen dosya tespit edildi. "
            f"Kazanılabilir alan: <b>{format_bytes(total_wasted)}</b>."
        )

        self._render_duplicate_table()

    def _render_duplicate_table(self):
        total_rows = sum(len(g.files) for g in self.duplicate_groups)
        self.dup_table.setRowCount(total_rows)

        cur_row = 0
        for grp in self.duplicate_groups:
            for item in grp.files:
                # Checkbox
                chk = QCheckBox()
                chk.setChecked(item.selected and not item.is_original)
                chk.setEnabled(not item.is_original) # Prevent checking original by accident
                chk.stateChanged.connect(lambda state, it=item: self._on_item_check_changed(it, state))

                cell_widget = QWidget()
                cell_lay = QHBoxLayout(cell_widget)
                cell_lay.setContentsMargins(10, 0, 0, 0)
                cell_lay.setAlignment(Qt.AlignCenter)
                cell_lay.addWidget(chk)
                self.dup_table.setCellWidget(cur_row, 0, cell_widget)

                # Name
                item_name = QTableWidgetItem(os.path.basename(item.path))
                self.dup_table.setItem(cur_row, 1, item_name)

                # Status
                if item.is_original:
                    status_lbl = "⭐ Orijinal Dosya (Korunuyor)"
                    status_col = COLOR_SUCCESS
                else:
                    status_lbl = "⚠️ Yinelenen Kopya"
                    status_col = COLOR_WARNING

                it_status = QTableWidgetItem(status_lbl)
                it_status.setForeground(QColor(status_col))
                self.dup_table.setItem(cur_row, 2, it_status)

                # Size
                sz_item = QTableWidgetItem(format_bytes(item.size))
                sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.dup_table.setItem(cur_row, 3, sz_item)

                # Path
                self.dup_table.setItem(cur_row, 4, QTableWidgetItem(item.path))
                cur_row += 1

    def _on_item_check_changed(self, item, state: int):
        item.selected = (state == Qt.Checked)

    def _apply_auto_selection(self, mode: str):
        if not self.duplicate_groups:
            return
        self.duplicate_finder.auto_mark_selection(self.duplicate_groups, keep_mode=mode)
        self._render_duplicate_table()

    def _delete_selected_duplicates(self):
        if not self.duplicate_groups:
            QMessageBox.information(self, "Bilgi", "Silinecek yinelenen dosya listesi boş.")
            return

        to_delete = [
            f for g in self.duplicate_groups for f in g.files
            if f.selected and not f.is_original
        ]
        if not to_delete:
            QMessageBox.information(self, "Bilgi", "Lütfen silinmesini istediğiniz yinelenen dosyaları işaretleyin.")
            return

        total_bytes = sum(f.size for f in to_delete)
        ans = QMessageBox.question(
            self,
            "Yinelenen Dosyaları Sil",
            f"Seçilen <b>{len(to_delete)}</b> adet kopya dosyayı kalıcı olarak silmek ve "
            f"<b>{format_bytes(total_bytes)}</b> disk alanı boşaltmak istediğinizden emin misiniz?\n\n"
            f"(Her dosyanın en az 1 orijinal kopyası kesinlikle korunacaktır.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return

        deleted, freed, errs = self.duplicate_finder.delete_selected(self.duplicate_groups)
        freed_str = format_bytes(freed)

        if errs:
            err_msg = "\n".join(errs[:5])
            QMessageBox.warning(
                self,
                "İşlem Tamamlandı (Bazı Hatalarla)",
                f"{deleted} adet kopya dosya silindi (+{freed_str} boşaltıldı).\n\nBazı dosyalar kilitli olduğundan silinemedi:\n{err_msg}"
            )
        else:
            QMessageBox.information(
                self,
                "Başarılı",
                f"Tebrikler! {deleted} adet yinelenen dosya temizlendi ve {freed_str} alan geri kazanıldı."
            )

        # Refresh scan
        self._toggle_duplicate_scan()

    def _on_dup_row_double_click(self, item: QTableWidgetItem):
        row = item.row()
        path_item = self.dup_table.item(row, 4)
        if path_item and os.path.exists(path_item.text()):
            norm_p = os.path.normpath(path_item.text())
            subprocess.Popen(f'explorer.exe /select,"{norm_p}"')

    def stop_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.requestInterruption()
            self.scan_thread.wait(500)
            self.btn_scan.setText("🔍  Büyük Dosyaları Tara")
            self.progress_bar.setVisible(False)
            self.lbl_status.setText("Tarama durduruldu.")
        if self.dup_thread and self.dup_thread.isRunning():
            self.dup_thread.requestInterruption()
            self.dup_thread.wait(500)
            self.btn_dup_scan.setText("🔍  Yinelenenleri Tara")
            self.dup_progress.setVisible(False)

    def hideEvent(self, event):
        self.stop_scan()
        super().hideEvent(event)
