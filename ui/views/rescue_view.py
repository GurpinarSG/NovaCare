"""
NovaCare System Suite - Backup & Rescue Center View
View and restore registry backups, create Windows restore points, and launch system restore.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt
from core.backup_manager import BackupManager, BackupEntry
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class RescueView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mgr = BackupManager()
        self.backups: list[BackupEntry] = []
        self._init_ui()
        self.refresh_backups()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # Header
        lbl_title = QLabel("Kurtarma ve Yedekleme Merkezi")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Temizlik öncesi alınan kayıt defteri yedeklerini geri yükleyin veya Windows Sistem Geri Yükleme noktası oluşturun.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Top System Restore Card
        top_card = QFrame()
        top_card.setObjectName("CardFrame")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(20, 16, 20, 16)

        v_desc = QVBoxLayout()
        lbl_r_title = QLabel("🛡️  Windows Sistem Geri Yükleme")
        lbl_r_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        lbl_r_sub = QLabel("Önemli sistem değişiklikleri öncesinde tam bir Windows kurtarma noktası oluşturabilirsiniz.")
        lbl_r_sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        lbl_r_sub.setWordWrap(True)
        v_desc.addWidget(lbl_r_title)
        v_desc.addWidget(lbl_r_sub)
        top_layout.addLayout(v_desc)

        top_layout.addStretch()

        self.btn_create_point = QPushButton("➕  Geri Yükleme Noktası")
        self.btn_create_point.setToolTip("Yeni bir Windows Sistem Geri Yükleme Noktası oluşturur")
        self.btn_create_point.setProperty("class", "primary-btn")
        self.btn_create_point.clicked.connect(self._create_restore_point)

        self.btn_open_rstrui = QPushButton("⚙️  Kurtarma Aracı")
        self.btn_open_rstrui.setToolTip("Windows Sistem Geri Yükleme Sihirbazını (rstrui.exe) açar")
        self.btn_open_rstrui.setProperty("class", "secondary-btn")
        self.btn_open_rstrui.clicked.connect(self.mgr.open_system_restore_ui)

        top_layout.addWidget(self.btn_create_point)
        top_layout.addWidget(self.btn_open_rstrui)
        layout.addWidget(top_card)

        # Backups Table Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        lbl_table_title = QLabel("💾  Kayıt Defteri Yedekleri Geçmişi")
        lbl_table_title.setStyleSheet("font-weight: 700;")

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setProperty("class", "secondary-btn")
        self.btn_refresh.clicked.connect(self.refresh_backups)

        self.btn_restore = QPushButton("↩️  Seçili Yedeği Geri Yükle")
        self.btn_restore.setProperty("class", "success-btn")
        self.btn_restore.clicked.connect(self._restore_selected)

        tb_layout.addWidget(lbl_table_title)
        tb_layout.addStretch()
        tb_layout.addWidget(self.btn_refresh)
        tb_layout.addWidget(self.btn_restore)
        layout.addWidget(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Yedek Dosyası", "Oluşturulma Tarihi", "Kayıt Sayısı", "Boyut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

    def refresh_backups(self):
        self.backups = self.mgr.list_backups()
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(self.backups))
            for row, bkp in enumerate(self.backups):
                f_item = QTableWidgetItem(f"📁  {bkp.filename}")
                f_item.setToolTip(bkp.filepath)
                self.table.setItem(row, 0, f_item)

                t_item = QTableWidgetItem(bkp.timestamp)
                t_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 1, t_item)

                c_item = QTableWidgetItem(f"{bkp.issue_count} kayıt")
                c_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, c_item)

                s_item = QTableWidgetItem(bkp.size_str)
                s_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 3, s_item)
        finally:
            self.table.setUpdatesEnabled(True)

    def _create_restore_point(self):
        self.btn_create_point.setEnabled(False)
        self.btn_create_point.setText("⏳  Oluşturuluyor...")
        success = self.mgr.create_system_restore_point("NovaCare Sistem Bakım Noktası")
        self.btn_create_point.setText("➕  Geri Yükleme Noktası Oluştur")
        self.btn_create_point.setEnabled(True)

        if success:
            QMessageBox.information(self, "Başarılı", "Windows Sistem Geri Yükleme Noktası başarıyla oluşturuldu!")
        else:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Geri yükleme noktası oluşturulamadı.\nWindows Sistem Koruması devre dışı bırakılmış olabilir veya yönetici izni gerekebilir."
            )

    def _restore_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.backups):
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen geri yüklemek istediğiniz bir yedek dosyası seçin.")
            return

        bkp = self.backups[row]
        confirm = QMessageBox.question(
            self,
            "Yedeği Geri Yükle",
            f"'{bkp.filename}' dosyasındaki kayıt defteri verileri geri yüklenecek.\nOnaylıyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            restored, failed = self.mgr.restore_backup(bkp.filepath)
            QMessageBox.information(
                self,
                "Geri Yükleme Sonucu",
                f"Kayıt defteri yedeği geri yüklendi!\n\n"
                f"• Başarıyla Geri Yüklenen: {restored} kayıt\n"
                f"• Atlanan / Başarısız: {failed}"
            )
