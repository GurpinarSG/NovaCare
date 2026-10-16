"""
NovaCare System Suite - Junk & Browser Cleaner View
Detailed category selection, scanning, and safe cleaning of temporary and cache files.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.junk_cleaner import JunkCleaner, CleanerCategory
from core.utils import format_bytes, is_admin
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class JunkScanThread(QThread):
    progress = pyqtSignal(str, int, int) # name, cur, total
    finished = pyqtSignal(list)

    def __init__(self, cleaner: JunkCleaner):
        super().__init__()
        self.cleaner = cleaner

    def run(self):
        cats = self.cleaner.scan_all(
            progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
        )
        self.finished.emit(cats)

class JunkCleanThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(int, int, int) # freed, cleaned_files, failed_files

    def __init__(self, cleaner: JunkCleaner, selected_ids: set[str]):
        super().__init__()
        self.cleaner = cleaner
        self.selected_ids = selected_ids

    def run(self):
        freed, cleaned, failed = self.cleaner.clean_categories(
            self.selected_ids,
            progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
        )
        self.finished.emit(freed, cleaned, failed)

class JunkView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaner = JunkCleaner()
        self.categories: list[CleanerCategory] = self.cleaner.categories
        self.scan_thread = None
        self.clean_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Gereksiz Dosya ve Tarayıcı Önbelleği Temizleyici")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Sisteminizde biriken geçici dosyaları, tarayıcı önbelleklerini ve sistem artıklarını temizleyin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Admin Depth Banner
        self.admin_banner = QFrame()
        has_admin = is_admin()
        bg_col = "rgba(16, 185, 129, 0.12)" if has_admin else "rgba(251, 191, 36, 0.12)"
        border_col = "rgba(16, 185, 129, 0.35)" if has_admin else "rgba(251, 191, 36, 0.35)"
        text_col = COLOR_SUCCESS if has_admin else COLOR_WARNING

        self.admin_banner.setStyleSheet(f"""
            background-color: {bg_col};
            border: 1px solid {border_col};
            border-radius: 8px;
            padding: 8px 12px;
        """)
        ab_lay = QHBoxLayout(self.admin_banner)
        ab_lay.setContentsMargins(8, 4, 8, 4)

        banner_msg = (
            "🛡️ <b>Yönetici Modu Aktif:</b> Windows Prefetch, Sistem Bellek Dökümleri ve sistem korumalı tüm önbelleklere tam erişimle %100 derinlikte temizlik sağlanır."
            if has_admin else
            "💡 <b>Daha İyi Temizlik İpucu:</b> Sistem korumalı bazı önbellekler standart modda atlanabilir. Maksimum derinlikte temizlik için NovaCare'i <b>Yönetici olarak</b> çalıştırın."
        )
        lbl_ab = QLabel(banner_msg)
        lbl_ab.setStyleSheet(f"color: {text_col}; font-size: 12px;")
        lbl_ab.setWordWrap(True)
        ab_lay.addWidget(lbl_ab)
        layout.addWidget(self.admin_banner)

        # Action Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        self.btn_scan = QPushButton("🔍  Taramayı Başlat")
        self.btn_scan.setProperty("class", "primary-btn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self._start_scan)

        self.btn_clean = QPushButton("🧹  Seçilenleri Temizle")
        self.btn_clean.setProperty("class", "success-btn")
        self.btn_clean.setCursor(Qt.PointingHandCursor)
        self.btn_clean.setEnabled(False)
        self.btn_clean.clicked.connect(self._start_clean)

        self.chk_all = QCheckBox("Tümünü Seç")
        self.chk_all.setChecked(True)
        self.chk_all.stateChanged.connect(self._toggle_select_all)

        self.lbl_summary = QLabel("Toplam Temizlenebilir: 0 B")
        self.lbl_summary.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700; font-size: 14px;")

        tb_layout.addWidget(self.btn_scan)
        tb_layout.addWidget(self.btn_clean)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self.chk_all)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_summary)
        layout.addWidget(toolbar)

        # Progress bar & status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_status)

        # Category Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Kategori", "Açıklama", "Dosya Sayısı", "Boyut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self._populate_table()

    def _populate_table(self):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(self.categories))
            for row, cat in enumerate(self.categories):
                # Column 0: Checkbox + Name
                chk = QCheckBox(f"{cat.icon}  {cat.name}")
                chk.setChecked(cat.selected)
                chk.stateChanged.connect(lambda state, c=cat: self._on_cat_checked(c, state))
                self.table.setCellWidget(row, 0, chk)

                # Column 1: Description
                desc_item = QTableWidgetItem(cat.description)
                desc_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 1, desc_item)

                # Column 2: File count
                count_str = f"{cat.file_count:,} dosya" if cat.file_count > 0 else "-"
                count_item = QTableWidgetItem(count_str)
                count_item.setTextAlignment(Qt.AlignCenter)
                count_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 2, count_item)

                # Column 3: Size
                sz_str = format_bytes(cat.size) if cat.size > 0 else "-"
                sz_item = QTableWidgetItem(sz_str)
                sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                sz_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 3, sz_item)
        finally:
            self.table.setUpdatesEnabled(True)

        self._update_summary()

    def _on_cat_checked(self, cat: CleanerCategory, state: int):
        cat.selected = (state == Qt.Checked)
        self._update_summary()

    def _toggle_select_all(self, state: int):
        checked = (state == Qt.Checked)
        for cat in self.categories:
            cat.selected = checked
        self._populate_table()

    def _update_summary(self):
        total_bytes = sum(c.size for c in self.categories if c.selected)
        total_files = sum(c.file_count for c in self.categories if c.selected)
        self.lbl_summary.setText(f"Toplam Temizlenebilir: {format_bytes(total_bytes)} ({total_files:,} Dosya)")
        self.btn_clean.setEnabled(total_bytes > 0)

    def _start_scan(self):
        self.btn_scan.setEnabled(False)
        self.btn_clean.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress_bar.setValue(0)

        self.scan_thread = JunkScanThread(self.cleaner)
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_progress(self, name: str, cur: int, total: int):
        pct = int((cur / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Taranıyor ({cur}/{total}): {name}...")

    def _on_scan_finished(self, categories: list[CleanerCategory]):
        self.categories = categories
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)
        self._populate_table()

    def _start_clean(self):
        selected_ids = {c.id for c in self.categories if c.selected}
        if not selected_ids:
            return

        has_admin = is_admin()
        admin_note = (
            "\n\n🛡️ Yönetici Yetkisi Aktif: Windows Prefetch, Sistem Hata Dökümleri ve korumalı önbellekler tam yetkiyle derinlemesine temizlenecektir."
            if has_admin else
            "\n\n💡 İpucu: NovaCare'i Yönetici olarak çalıştırdığınızda kilitli sistem dosyaları ve korumalı önbellekler çok daha derin ve kapsamlı temizlenir."
        )

        confirm = QMessageBox.question(
            self,
            "Temizliği Onayla",
            f"Seçili {len(selected_ids)} kategorideki gereksiz dosyalar kalıcı olarak temizlenecek.{admin_note}\n\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_scan.setEnabled(False)
        self.btn_clean.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress_bar.setValue(0)

        self.clean_thread = JunkCleanThread(self.cleaner, selected_ids)
        self.clean_thread.progress.connect(self._on_clean_progress)
        self.clean_thread.finished.connect(self._on_clean_finished)
        self.clean_thread.start()

    def _on_clean_progress(self, name: str, cur: int, total: int):
        pct = int((cur / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Temizleniyor ({cur}/{total}): {name}...")

    def _on_clean_finished(self, freed: int, cleaned_count: int, failed_count: int):
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)
        self._populate_table()

        has_admin = is_admin()
        admin_summary = (
            "\n\n🛡️ Yönetici ayrıcalıkları sayesinde sistem ve kullanıcı düzeyindeki tüm artıklar derinlemesine temizlendi."
            if has_admin else
            "\n\n💡 Daha fazla disk alanı kazanmak ve kilitli sistem artıklarını temizlemek için uygulamayı Yönetici olarak çalıştırmayı deneyin."
        )

        QMessageBox.information(
            self,
            "Temizlik Başarılı",
            f"İşlem tamamlandı!\n\n"
            f"• Boşaltılan Alan: {format_bytes(freed)}\n"
            f"• Silinen Dosya: {cleaned_count:,} adet\n"
            f"• Kilitli/Atlanan: {failed_count:,} adet"
            f"{admin_summary}"
        )
