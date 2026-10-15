"""
NovaCare System Suite - App Uninstaller & Leftover Cleaner View
Lists installed programs, runs uninstallers, and scans/cleans residual leftovers.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFrame,
    QDialog, QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from core.uninstaller import AppUninstaller, InstalledApp, LeftoverItem
from core.utils import format_bytes
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class AppScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, uninstaller: AppUninstaller):
        super().__init__()
        self.uninstaller = uninstaller

    def run(self):
        try:
            apps = self.uninstaller.scan_installed_apps()
            self.finished.emit(apps)
        except Exception:
            self.finished.emit([])

class LeftoverDialog(QDialog):
    def __init__(self, app: InstalledApp, leftovers: list[LeftoverItem], uninstaller: AppUninstaller, parent=None):
        super().__init__(parent)
        self.app = app
        self.leftovers = leftovers
        self.uninstaller = uninstaller
        self.setWindowTitle(f"Artık Dosya ve Kalıntı Temizliği - {app.name}")
        self.resize(650, 450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl = QLabel(f"<b>{self.app.name}</b> uygulamasına ait sistemde kalan artıklar:")
        lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        for item in self.leftovers:
            icon_str = "📁" if item.item_type == "folder" else ("📄" if item.item_type == "file" else "🔑")
            list_item = QListWidgetItem(f"{icon_str}  [{item.details}]  {item.path}")
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Checked if item.selected else Qt.Unchecked)
            self.list_widget.addItem(list_item)
        layout.addWidget(self.list_widget)

        btn_box = QHBoxLayout()
        self.btn_clean = QPushButton("🧹  Seçilen Artıkları Kalıcı Olarak Sil")
        self.btn_clean.setProperty("class", "danger-btn")
        self.btn_clean.clicked.connect(self._clean)

        self.btn_cancel = QPushButton("Kapat")
        self.btn_cancel.setProperty("class", "secondary-btn")
        self.btn_cancel.clicked.connect(self.close)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_clean)
        layout.addLayout(btn_box)

    def _clean(self):
        for i in range(self.list_widget.count()):
            self.leftovers[i].selected = (self.list_widget.item(i).checkState() == Qt.Checked)

        cleaned, failed = self.uninstaller.clean_leftovers(self.leftovers)
        QMessageBox.information(
            self,
            "Temizlik Tamamlandı",
            f"Artık temizliği başarıyla tamamlandı!\n\n"
            f"• Temizlenen: {cleaned} öğe\n"
            f"• Kilitli/Atlanan: {failed} öğe"
        )
        self.accept()

class UninstallerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.uninstaller = AppUninstaller()
        self.all_apps: list[InstalledApp] = []
        self.filtered_apps: list[InstalledApp] = []
        self.scan_worker = None
        self._is_scanning = False

        # Search debouncer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self._filter_apps)

        self._init_ui()
        self.refresh_apps()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Uygulama ve Yazılım Kaldırıcı")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Yüklü programları kaldırın ve geride bıraktıkları tüm kayıt defteri ve dosya artıklarını temizleyin.")
        lbl_sub.setObjectName("ViewSubtitle")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Program ara...")
        self.search_box.setFixedWidth(240)
        self.search_box.textChanged.connect(lambda: self.search_timer.start())

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setProperty("class", "secondary-btn")
        self.btn_refresh.clicked.connect(self.refresh_apps)

        self.btn_uninstall = QPushButton("🗑️  Programı Kaldır")
        self.btn_uninstall.setProperty("class", "danger-btn")
        self.btn_uninstall.clicked.connect(self._uninstall_selected)

        self.btn_leftovers = QPushButton("✨  Artıkları / Kalıntıları Tara")
        self.btn_leftovers.setProperty("class", "primary-btn")
        self.btn_leftovers.clicked.connect(self._scan_leftovers_selected)

        self.lbl_stats = QLabel("Toplam: 0")
        self.lbl_stats.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700;")

        tb_layout.addWidget(self.search_box)
        tb_layout.addWidget(self.btn_refresh)
        tb_layout.addWidget(self.btn_uninstall)
        tb_layout.addWidget(self.btn_leftovers)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_stats)
        layout.addWidget(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Program Adı", "Yayıncı", "Sürüm", "Yükleme Tarihi", "Tahmini Boyut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 180)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)

    def refresh_apps(self):
        if self._is_scanning:
            return
        self._is_scanning = True
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Yükleniyor...")
        self.lbl_stats.setText("Programlar taranıyor...")

        self.scan_worker = AppScanWorker(self.uninstaller)
        self.scan_worker.finished.connect(self._on_apps_scanned)
        self.scan_worker.start()

    def _on_apps_scanned(self, apps: list):
        self._is_scanning = False
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄  Yenile")
        self.all_apps = apps
        self._filter_apps()

    def _filter_apps(self):
        query = self.search_box.text().strip().lower()
        if not query:
            self.filtered_apps = list(self.all_apps)
        else:
            self.filtered_apps = [a for a in self.all_apps if query in a.name.lower() or query in a.publisher.lower()]

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.filtered_apps))
            for row, app in enumerate(self.filtered_apps):
                # Column 0: Name
                name_item = QTableWidgetItem(f"📦  {app.name}")
                name_item.setToolTip(app.name)
                self.table.setItem(row, 0, name_item)

                # Column 1: Publisher
                pub_item = QTableWidgetItem(app.publisher)
                self.table.setItem(row, 1, pub_item)

                # Column 2: Version
                ver_item = QTableWidgetItem(app.version)
                ver_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, ver_item)

                # Column 3: Date
                date_item = QTableWidgetItem(app.install_date or "-")
                date_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, date_item)

                # Column 4: Size
                sz_str = format_bytes(app.size_bytes) if app.size_bytes > 0 else "-"
                sz_item = QTableWidgetItem(sz_str)
                sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 4, sz_item)
        finally:
            self.table.setUpdatesEnabled(True)

        self.lbl_stats.setText(f"Toplam Program: {len(self.filtered_apps)}")

    def _get_selected_app(self) -> InstalledApp | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.filtered_apps):
            return self.filtered_apps[row]
        return None

    def _uninstall_selected(self):
        app = self._get_selected_app()
        if not app:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen kaldırmak istediğiniz bir program seçin.")
            return

        confirm = QMessageBox.question(
            self,
            "Programı Kaldır",
            f"'{app.name}' programının resmi kaldırıcı aracı başlatılacak.\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            try:
                self.uninstaller.launch_uninstaller(app)
                QMessageBox.information(
                    self,
                    "Kaldırıcı Başlatıldı",
                    f"'{app.name}' kaldırıcı programı başlatıldı.\n\nKaldırma işlemi bittikten sonra 'Artıkları Tara' butonunu kullanarak geride kalan tüm kalıntıları silebilirsiniz."
                )
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kaldırma komutu başlatılamadı:\n{e}")

    def _scan_leftovers_selected(self):
        app = self._get_selected_app()
        if not app:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen artıklarını taramak istediğiniz bir program seçin.")
            return

        leftovers = self.uninstaller.scan_leftovers(app)
        if not leftovers:
            QMessageBox.information(self, "Artık Bulunamadı", f"'{app.name}' için sistemde herhangi bir artık dosya veya kayıt defteri kalıntısı bulunamadı. Sisteminiz temiz!")
            return

        dlg = LeftoverDialog(app, leftovers, self.uninstaller, self)
        dlg.exec_()
