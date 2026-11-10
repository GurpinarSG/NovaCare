"""
NovaCare System Suite - Registry Cleaner & Compactor View
Scans, backs up, and safely fixes Windows Registry inconsistencies,
and analyzes hive fragmentation to execute deep registry compaction & defragmentation.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox, QFrame,
    QAbstractItemView, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor
from core.registry_cleaner import RegistryCleaner, RegistryIssue
from core.registry_compactor import RegistryCompactor, RegistryHiveInfo
from core.utils import is_admin, log_debug, format_bytes
from ui.styles import (
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING
)

class RegScanThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)

    def __init__(self, cleaner: RegistryCleaner):
        super().__init__()
        self.cleaner = cleaner
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        issues = []
        try:
            if not self._is_cancelled:
                issues = self.cleaner.scan_all(
                    progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
                )
        except Exception as e:
            log_debug(f"RegScanThread error: {e}")
        finally:
            if not self._is_cancelled:
                self.finished.emit(issues)

class RegFixThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(int, int, str) # fixed_count, failed_count, backup_path

    def __init__(self, cleaner: RegistryCleaner, issues: list[RegistryIssue]):
        super().__init__()
        self.cleaner = cleaner
        self.issues = issues
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        fixed, failed, bkp = 0, len(self.issues), ""
        try:
            if not self._is_cancelled:
                fixed, failed, bkp = self.cleaner.fix_issues(
                    self.issues,
                    progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
                )
        except Exception as e:
            log_debug(f"RegFixThread error: {e}")
        finally:
            if not self._is_cancelled:
                self.finished.emit(fixed, failed, bkp)

class RegistryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaner = RegistryCleaner()
        self.compactor = RegistryCompactor()
        self.issues: list[RegistryIssue] = []
        self.hives: list[RegistryHiveInfo] = []
        self.scan_thread = None
        self.fix_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # Header
        lbl_title = QLabel("Kayıt Defteri Onarımı ve Sıkıştırma")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Bozuk uygulama yollarını temizleyin, şişen kovanları analiz edip birleştirerek açılışı hızlandırın.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Tabs: 1. Temizleme ve Onarım, 2. Kovan Sıkıştırma (Compactor)
        self.tabs = QTabWidget()
        self.tab_cleaner = QWidget()
        self.tab_compactor = QWidget()

        self._build_cleaner_tab()
        self._build_compactor_tab()

        self.tabs.addTab(self.tab_cleaner, "🛠️  Kayıt Defteri Temizleyici ve Onarıcı")
        self.tabs.addTab(self.tab_compactor, "📦  Kovan Sıkıştırma & Birleştirme (Compactor)")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)
        self._analyze_hives()

    def _on_tab_changed(self, index: int):
        if index == 1 and not self.hives:
            self._analyze_hives()

    def _build_cleaner_tab(self):
        tab_lay = QVBoxLayout(self.tab_cleaner)
        tab_lay.setContentsMargins(10, 12, 10, 10)
        tab_lay.setSpacing(12)

        # Admin Depth Banner
        self.admin_banner = QFrame()
        has_admin = is_admin()
        self.admin_banner.setObjectName("AdminBannerSuccess" if has_admin else "AdminBannerWarning")
        ab_lay = QHBoxLayout(self.admin_banner)
        ab_lay.setContentsMargins(8, 4, 8, 4)

        banner_msg = (
            "🛡️ <b>Yönetici Modu Aktif:</b> HKEY_LOCAL_MACHINE dahil tüm sistem genelindeki kayıt defteri anahtarlarına tam erişimle en derin onarım yapılır."
            if has_admin else
            "💡 <b>Daha Derin Onarım İpucu:</b> Sistem genelindeki HKEY_LOCAL_MACHINE anahtarlarını onarmak için NovaCare'i <b>Yönetici olarak</b> çalıştırın."
        )
        lbl_ab = QLabel(banner_msg)
        lbl_ab.setObjectName("AdminBannerSuccessText" if has_admin else "AdminBannerWarningText")
        lbl_ab.setWordWrap(True)
        ab_lay.addWidget(lbl_ab)
        tab_lay.addWidget(self.admin_banner)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        self.btn_scan = QPushButton("🔍  Sorunları Tara")
        self.btn_scan.setProperty("class", "primary-btn")
        self.btn_scan.setCursor(Qt.PointingHandCursor)
        self.btn_scan.clicked.connect(self._start_scan)

        self.btn_fix = QPushButton("🛠️  Seçilenleri Onar")
        self.btn_fix.setProperty("class", "success-btn")
        self.btn_fix.setCursor(Qt.PointingHandCursor)
        self.btn_fix.setEnabled(False)
        self.btn_fix.clicked.connect(self._start_fix)

        self.chk_all = QCheckBox("Tümünü Seç")
        self.chk_all.setChecked(True)
        self.chk_all.stateChanged.connect(self._toggle_select_all)

        self.lbl_summary = QLabel("Tespit Edilen Sorun: 0")
        self.lbl_summary.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700; font-size: 14px;")

        tb_layout.addWidget(self.btn_scan)
        tb_layout.addWidget(self.btn_fix)
        tb_layout.addSpacing(16)
        tb_layout.addWidget(self.chk_all)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_summary)
        tab_lay.addWidget(toolbar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("TextSecondary")
        self.lbl_status.setVisible(False)
        tab_lay.addWidget(self.progress_bar)
        tab_lay.addWidget(self.lbl_status)

        # Issues Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Kategori", "Kayıt Konumu", "Giriş / Değer", "Sorun Sebebi"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 280)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 180)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tab_lay.addWidget(self.table)

    def _build_compactor_tab(self):
        tab_lay = QVBoxLayout(self.tab_compactor)
        tab_lay.setContentsMargins(10, 12, 10, 10)
        tab_lay.setSpacing(12)

        # Description Card
        desc_card = QFrame()
        desc_card.setObjectName("CardFrame")
        d_lay = QVBoxLayout(desc_card)
        d_lay.setContentsMargins(14, 10, 14, 10)
        d_lay.setSpacing(4)

        lbl_head = QLabel("📦  Kayıt Defteri Kovan Parçalanması ve Boşluk Analizi")
        lbl_head.setStyleSheet("font-size: 14px; font-weight: 700;")
        d_lay.addWidget(lbl_head)

        lbl_p = QLabel(
            "Programlar yüklenip kaldırıldıkça Windows kayıt defteri kovanlarında ölü hücreler (slack space) kalır. "
            "Kayıt defteri sıkıştırma işlemi bu boşlukları diske yazarak birleştirir, bellek kullanımını düşürür ve sistem açılışını hızlandırır."
        )
        lbl_p.setObjectName("TextSecondary")
        lbl_p.setStyleSheet("font-size: 12px;")
        lbl_p.setWordWrap(True)
        d_lay.addWidget(lbl_p)
        tab_lay.addWidget(desc_card)

        # Toolbar
        tb = QFrame()
        tb.setObjectName("ToolbarFrame")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(12, 8, 12, 8)
        tb_lay.setSpacing(10)

        self.btn_analyze_hives = QPushButton("🔍  Kovanları Analiz Et")
        self.btn_analyze_hives.setProperty("class", "primary-btn")
        self.btn_analyze_hives.setCursor(Qt.PointingHandCursor)
        self.btn_analyze_hives.clicked.connect(self._analyze_hives)
        tb_lay.addWidget(self.btn_analyze_hives)

        self.btn_compact_now = QPushButton("⚡  Kayıt Defterini Sıkıştır ve Birleştir")
        self.btn_compact_now.setProperty("class", "success-btn")
        self.btn_compact_now.setCursor(Qt.PointingHandCursor)
        self.btn_compact_now.clicked.connect(self._compact_registry)
        tb_lay.addWidget(self.btn_compact_now)

        tb_lay.addStretch()

        self.lbl_hive_summary = QLabel("Analiz bekleniyor...")
        self.lbl_hive_summary.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700; font-size: 13px;")
        tb_lay.addWidget(self.lbl_hive_summary)
        tab_lay.addWidget(tb)

        # Hives Table
        self.hive_table = QTableWidget()
        self.hive_table.setColumnCount(5)
        self.hive_table.setHorizontalHeaderLabels(["Kovan Açıklaması", "Mevcut Boyut", "Parçalanma", "Kazanılabilir Alan", "Fiziksel Dosya Yolu"])
        self.hive_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.hive_table.setColumnWidth(0, 240)
        self.hive_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hive_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.hive_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.hive_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.hive_table.verticalHeader().setVisible(False)
        self.hive_table.setAlternatingRowColors(True)
        self.hive_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tab_lay.addWidget(self.hive_table)

    def _analyze_hives(self):
        self.hives = self.compactor.analyze_hives()
        self.hive_table.setRowCount(len(self.hives))

        tot_sz = sum(h.current_size_bytes for h in self.hives)
        tot_reclaim = sum(h.reclaimable_bytes for h in self.hives)

        self.lbl_hive_summary.setText(f"Toplam Boyut: {format_bytes(tot_sz)} | Kazanılabilir: ~{format_bytes(tot_reclaim)}")

        for row, h in enumerate(self.hives):
            self.hive_table.setItem(row, 0, QTableWidgetItem(h.name))
            self.hive_table.setItem(row, 1, QTableWidgetItem(h.current_size_str))

            frag_it = QTableWidgetItem(f"%{h.fragmentation_pct}")
            if h.fragmentation_pct >= 20.0:
                frag_it.setForeground(QColor(COLOR_WARNING))
            self.hive_table.setItem(row, 2, frag_it)

            rec_it = QTableWidgetItem(h.reclaimable_str)
            rec_it.setForeground(QColor(COLOR_SUCCESS))
            self.hive_table.setItem(row, 3, rec_it)

            self.hive_table.setItem(row, 4, QTableWidgetItem(h.file_path))

    def _compact_registry(self):
        ans = QMessageBox.question(
            self,
            "Kayıt Defterini Sıkıştır",
            "Kayıt defteri kovanlarının in-memory tamponları diske yazılacak ve boş hücreler birleştirilecek.\n\nİşleme devam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return

        ok, reclaimed, msg = self.compactor.compact_and_optimize()
        if ok:
            QMessageBox.information(self, "Başarılı", f"Kayıt defteri başarıyla sıkıştırıldı ve optimize edildi!\n\n{msg}")
            self._analyze_hives()
        else:
            QMessageBox.warning(self, "Hata", msg)

    # Issue cleaner methods
    def _start_scan(self):
        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Kayıt defteri taranıyor...")
        self.table.setRowCount(0)

        self.scan_thread = RegScanThread(self.cleaner)
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_progress(self, category: str, current: int, total: int):
        pct = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Taranıyor: {category} ({current}/{total})")

    def _on_scan_finished(self, issues: list[RegistryIssue]):
        self.issues = issues
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.btn_fix.setEnabled(len(issues) > 0)

        self.lbl_summary.setText(f"Tespit Edilen Sorun: {len(issues)}")

        self.table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            self.table.setItem(row, 0, QTableWidgetItem(issue.category))
            self.table.setItem(row, 1, QTableWidgetItem(f"{issue.root_name}\\{issue.sub_key}"))
            val_txt = issue.value_name if issue.value_name else "(Varsayılan)"
            self.table.setItem(row, 2, QTableWidgetItem(val_txt))
            self.table.setItem(row, 3, QTableWidgetItem(issue.reason))

    def _toggle_select_all(self, state: int):
        checked = (state == Qt.Checked)
        for issue in self.issues:
            issue.selected = checked

    def _start_fix(self):
        selected_issues = [i for i in self.issues if i.selected]
        if not selected_issues:
            QMessageBox.information(self, "Bilgi", "Onarılacak herhangi bir sorun seçilmedi.")
            return

        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Yedek alınıyor ve sorunlar onarılıyor...")

        self.fix_thread = RegFixThread(self.cleaner, selected_issues)
        self.fix_thread.progress.connect(self._on_scan_progress)
        self.fix_thread.finished.connect(self._on_fix_finished)
        self.fix_thread.start()

    def _on_fix_finished(self, fixed: int, failed: int, backup_path: str):
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)

        msg = f"Onarım tamamlandı!\n\nBaşarıyla Onarılan: {fixed}\nBaşarısız: {failed}"
        if backup_path:
            msg += f"\n\nGeri alma yedeği oluşturuldu:\n{backup_path}"

        QMessageBox.information(self, "Sonuç", msg)

        # Refresh remaining issues
        self._on_scan_finished(self.cleaner.issues)
