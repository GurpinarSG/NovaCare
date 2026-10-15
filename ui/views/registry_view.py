"""
NovaCare System Suite - Registry Cleaner View
Scans, displays, backs up, and safely fixes Windows Registry inconsistencies.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.registry_cleaner import RegistryCleaner, RegistryIssue
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class RegScanThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(list)

    def __init__(self, cleaner: RegistryCleaner):
        super().__init__()
        self.cleaner = cleaner

    def run(self):
        issues = self.cleaner.scan_all(
            progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
        )
        self.finished.emit(issues)

class RegFixThread(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(int, int, str) # fixed_count, failed_count, backup_path

    def __init__(self, cleaner: RegistryCleaner, issues: list[RegistryIssue]):
        super().__init__()
        self.cleaner = cleaner
        self.issues = issues

    def run(self):
        fixed, failed, bkp = self.cleaner.fix_issues(
            self.issues,
            progress_callback=lambda name, cur, tot: self.progress.emit(name, cur, tot)
        )
        self.finished.emit(fixed, failed, bkp)

class RegistryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cleaner = RegistryCleaner()
        self.issues: list[RegistryIssue] = []
        self.scan_thread = None
        self.fix_thread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Kayıt Defteri Temizleyici ve Onarıcı")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Bozuk uygulama yollarını, silinmiş program kalıntılarını ve geçersiz anahtarları onarır.")
        lbl_sub.setObjectName("ViewSubtitle")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

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
        layout.addWidget(toolbar)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_status)

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
        layout.addWidget(self.table)

    def _populate_table(self):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(self.issues))
            for row, issue in enumerate(self.issues):
                chk = QCheckBox(issue.category)
                chk.setChecked(issue.selected)
                chk.stateChanged.connect(lambda state, iss=issue: self._on_issue_checked(iss, state))
                self.table.setCellWidget(row, 0, chk)

                loc_item = QTableWidgetItem(f"{issue.root_name}\\{issue.sub_key}")
                loc_item.setFlags(Qt.ItemIsEnabled)
                loc_item.setToolTip(f"{issue.root_name}\\{issue.sub_key}")
                self.table.setItem(row, 1, loc_item)

                val_item = QTableWidgetItem(issue.value_name or "(Varsayılan)")
                val_item.setFlags(Qt.ItemIsEnabled)
                val_item.setToolTip(issue.value_data)
                self.table.setItem(row, 2, val_item)

                reason_item = QTableWidgetItem(issue.reason)
                reason_item.setFlags(Qt.ItemIsEnabled)
                reason_item.setToolTip(issue.reason)
                self.table.setItem(row, 3, reason_item)
        finally:
            self.table.setUpdatesEnabled(True)

        self._update_summary()

    def _on_issue_checked(self, issue: RegistryIssue, state: int):
        issue.selected = (state == Qt.Checked)
        self._update_summary()

    def _toggle_select_all(self, state: int):
        checked = (state == Qt.Checked)
        for iss in self.issues:
            iss.selected = checked
        self._populate_table()

    def _update_summary(self):
        sel_count = len([i for i in self.issues if i.selected])
        self.lbl_summary.setText(f"Tespit Edilen Sorun: {len(self.issues)} (Seçili: {sel_count})")
        self.btn_fix.setEnabled(sel_count > 0)

    def _start_scan(self):
        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress_bar.setValue(0)

        self.scan_thread = RegScanThread(self.cleaner)
        self.scan_thread.progress.connect(self._on_scan_progress)
        self.scan_thread.finished.connect(self._on_scan_finished)
        self.scan_thread.start()

    def _on_scan_progress(self, name: str, cur: int, total: int):
        pct = int((cur / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Taranıyor ({cur}/{total}): {name}...")

    def _on_scan_finished(self, issues: list[RegistryIssue]):
        self.issues = issues
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)
        self._populate_table()

    def _start_fix(self):
        selected = [i for i in self.issues if i.selected]
        if not selected:
            return

        confirm = QMessageBox.question(
            self,
            "Kayıt Defteri Onarımı",
            f"Seçilen {len(selected)} kayıt defteri sorunu onarılacak.\n"
            "İşlem öncesinde otomatik olarak güvenli bir geri yükleme yedeği oluşturulacaktır. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        self.btn_scan.setEnabled(False)
        self.btn_fix.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress_bar.setValue(0)

        self.fix_thread = RegFixThread(self.cleaner, selected)
        self.fix_thread.progress.connect(self._on_fix_progress)
        self.fix_thread.finished.connect(self._on_fix_finished)
        self.fix_thread.start()

    def _on_fix_progress(self, name: str, cur: int, total: int):
        pct = int((cur / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Onarılıyor ({cur}/{total}): {name}...")

    def _on_fix_finished(self, fixed: int, failed: int, bkp: str):
        self.progress_bar.setVisible(False)
        self.lbl_status.setVisible(False)
        self.btn_scan.setEnabled(True)
        self._populate_table()

        QMessageBox.information(
            self,
            "Onarım Tamamlandı",
            f"Kayıt defteri onarımı tamamlandı!\n\n"
            f"• Başarıyla Onarılan: {fixed} sorun\n"
            f"• Başarısız/Atlanan: {failed}\n\n"
            f"Güvenlik Yedeği Kaydedildi:\n{bkp}"
        )
