"""
NovaCare System Suite - App Uninstaller & Leftover Cleaner View
Lists installed programs, supports multi-selection & batch sequential uninstallation,
and scans/cleans residual leftovers (registry & filesystem remnants).
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFrame,
    QDialog, QListWidget, QListWidgetItem, QCheckBox, QProgressBar,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
from core.uninstaller import AppUninstaller, InstalledApp, LeftoverItem
from core.utils import format_bytes, log_debug
from ui.styles import (
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY
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
    def __init__(self, app_or_apps, leftovers: list[LeftoverItem], uninstaller: AppUninstaller, parent=None):
        super().__init__(parent)
        self.app_or_apps = app_or_apps
        self.leftovers = leftovers
        self.uninstaller = uninstaller
        if isinstance(app_or_apps, list):
            self.app_title = f"{len(app_or_apps)} Program"
        else:
            self.app_title = app_or_apps.name
        self.setWindowTitle(f"Artık Dosya ve Kalıntı Temizliği - {self.app_title}")
        self.resize(680, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        lbl = QLabel(f"<b>{self.app_title}</b> uygulamasına ait sistemde tespit edilen artık ve kalıntılar:")
        lbl.setStyleSheet(f"font-size: 14px; color: {TEXT_PRIMARY};")
        lbl.setWordWrap(True)
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

class BatchUninstallWorker(QThread):
    app_started = pyqtSignal(int, object)             # index, app
    progress = pyqtSignal(int, int, str)              # current, total, status
    app_finished = pyqtSignal(int, object, bool, str) # index, app, success, msg
    batch_finished = pyqtSignal(list)                 # successfully processed apps

    def __init__(self, apps: list[InstalledApp], uninstaller: AppUninstaller):
        super().__init__()
        self.apps = list(apps)
        self.uninstaller = uninstaller
        self._is_canceled = False
        self._current_process = None

    def cancel(self):
        self._is_canceled = True

    def run(self):
        total = len(self.apps)
        uninstalled: list[InstalledApp] = []
        try:
            for idx, app in enumerate(self.apps):
                if self._is_canceled:
                    break

                self.app_started.emit(idx, app)
                self.progress.emit(idx + 1, total, f"'{app.name}' kaldırıcı aracı çalıştırılıyor...")

                success = False
                msg = ""
                try:
                    proc = self.uninstaller.launch_uninstaller(app)
                    self._current_process = proc
                    # Wait for uninstaller process to finish
                    while proc.poll() is None:
                        if self._is_canceled:
                            break
                        self.msleep(400)

                    if proc.returncode == 0 or proc.returncode is None:
                        success = True
                        msg = "Başarıyla tamamlandı"
                        uninstalled.append(app)
                    else:
                        success = True
                        msg = f"Tamamlandı (Kod: {proc.returncode})"
                        uninstalled.append(app)
                except Exception as e:
                    success = False
                    msg = str(e)

                self._current_process = None
                self.app_finished.emit(idx, app, success, msg)
                self.msleep(600)  # Brief pause between sequential uninstallers
        except Exception as e:
            log_debug(f"BatchUninstallWorker error: {e}")
        finally:
            self.batch_finished.emit(uninstalled)


class BatchUninstallDialog(QDialog):
    def __init__(self, apps: list[InstalledApp], uninstaller: AppUninstaller, parent=None):
        super().__init__(parent)
        self.apps = apps
        self.uninstaller = uninstaller
        self.worker = None
        self.uninstalled_apps: list[InstalledApp] = []

        self.setWindowTitle("NovaCare - Toplu Program Kaldırma")
        self.resize(620, 480)
        self._init_ui()
        self._start_batch()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QLabel(f"🚀  Toplu Program Kaldırma ({len(self.apps)} Program)")
        header.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLOR_ACCENT};")
        layout.addWidget(header)

        sub = QLabel("Programların resmi kaldırıcıları sırayla açılacaktır. Lütfen ekrana gelen pencerelerdeki kaldırma adımlarını onaylayın.")
        sub.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Progress bar
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(12)
        self.pbar.setRange(0, len(self.apps))
        self.pbar.setValue(0)
        layout.addWidget(self.pbar)

        self.lbl_status = QLabel("Hazırlanıyor...")
        self.lbl_status.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {TEXT_PRIMARY};")
        layout.addWidget(self.lbl_status)

        # App items list
        self.list_widget = QListWidget()
        for app in self.apps:
            item = QListWidgetItem(f"⏳  [Bekliyor] {app.name}")
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        # Auto leftover checkbox
        self.chk_auto_leftover = QCheckBox("Toplu kaldırma bitince geride kalan artık ve kalıntıları otomatik tara")
        self.chk_auto_leftover.setChecked(True)
        layout.addWidget(self.chk_auto_leftover)

        # Buttons
        b_box = QHBoxLayout()
        self.btn_cancel = QPushButton("İptal Et / Durdur")
        self.btn_cancel.setProperty("class", "danger-btn")
        self.btn_cancel.clicked.connect(self._cancel_batch)

        self.btn_close = QPushButton("Kapat")
        self.btn_close.setProperty("class", "secondary-btn")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)

        b_box.addStretch()
        b_box.addWidget(self.btn_cancel)
        b_box.addWidget(self.btn_close)
        layout.addLayout(b_box)

    def _start_batch(self):
        self.worker = BatchUninstallWorker(self.apps, self.uninstaller)
        self.worker.app_started.connect(self._on_app_started)
        self.worker.progress.connect(self._on_progress)
        self.worker.app_finished.connect(self._on_app_finished)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.start()

    def _on_app_started(self, idx: int, app: InstalledApp):
        item = self.list_widget.item(idx)
        if item:
            item.setText(f"⚙️  [Kaldırılıyor...] {app.name}")
            item.setForeground(QColor(COLOR_ACCENT))
            self.list_widget.setCurrentRow(idx)

    def _on_progress(self, current: int, total: int, msg: str):
        self.pbar.setValue(current)
        self.lbl_status.setText(f"({current} / {total}) - {msg}")

    def _on_app_finished(self, idx: int, app: InstalledApp, success: bool, msg: str):
        item = self.list_widget.item(idx)
        if item:
            if success:
                item.setText(f"✅  [Tamamlandı] {app.name}")
                item.setForeground(QColor(COLOR_SUCCESS))
            else:
                item.setText(f"⚠️  [Hata: {msg}] {app.name}")
                item.setForeground(QColor(COLOR_DANGER))

    def _on_batch_finished(self, uninstalled: list):
        self.uninstalled_apps = uninstalled
        self.lbl_status.setText(f"Toplu kaldırma tamamlandı! {len(uninstalled)} program başarıyla kaldırıldı.")
        self.lbl_status.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLOR_SUCCESS};")
        self.btn_cancel.setEnabled(False)
        self.btn_close.setEnabled(True)

        if self.chk_auto_leftover.isChecked() and uninstalled:
            leftovers = self.uninstaller.scan_multiple_leftovers(uninstalled)
            if leftovers:
                dlg = LeftoverDialog(uninstalled, leftovers, self.uninstaller, self)
                dlg.exec_()
            else:
                QMessageBox.information(
                    self,
                    "Kalıntı Bulunamadı",
                    "Kaldırılan programlara ait sistemde herhangi bir artık dosya veya kayıt defteri kalıntısı bulunamadı. Sisteminiz temiz!"
                )

    def _cancel_batch(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "İptal Onayı",
                "Toplu kaldırma işlemini durdurmak istiyor musunuz?\n(Şu an açık olan kaldırıcı tamamlandıktan sonra sıradakiler iptal edilir)",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.worker.cancel()
                self.lbl_status.setText("İşlem durduruldu.")
                self.btn_cancel.setEnabled(False)
                self.btn_close.setEnabled(True)

class CheckBoxCell(QWidget):
    def __init__(self, app_id: str, is_checked: bool, on_toggled, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        self.checkbox = QCheckBox()
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.checkbox.setChecked(is_checked)
        self.checkbox.stateChanged.connect(lambda state: on_toggled(self.app_id, state == Qt.Checked))
        layout.addWidget(self.checkbox)

    def setChecked(self, checked: bool):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked)
        self.checkbox.blockSignals(False)

    def isChecked(self) -> bool:
        return self.checkbox.isChecked()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.checkbox.toggle()
        super().mousePressEvent(event)

class UninstallerView(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.uninstaller = AppUninstaller()
        self.all_apps: list[InstalledApp] = []
        self.filtered_apps: list[InstalledApp] = []
        self.checked_app_ids: set[str] = set()
        self.scan_worker = None
        self._is_scanning = False
        self._updating_checks = False

        # Search debouncer
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self._filter_apps)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Uygulama ve Yazılım Kaldırıcı")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Yüklü programları tek tek veya toplu olarak kaldırın; geride bıraktıkları tüm kayıt defteri ve dosya kalıntılarını temizleyin.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Toolbar
        toolbar = QFrame()
        toolbar.setObjectName("ToolbarFrame")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        tb_layout.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍  Program ara...")
        self.search_box.setFixedWidth(220)
        self.search_box.textChanged.connect(lambda: self.search_timer.start())

        self.chk_all = QCheckBox("Tümünü Seç")
        self.chk_all.setCursor(Qt.PointingHandCursor)
        self.chk_all.stateChanged.connect(self._toggle_select_all)

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setProperty("class", "secondary-btn")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh_apps)

        self.btn_uninstall = QPushButton("🗑️  Programı Kaldır")
        self.btn_uninstall.setProperty("class", "danger-btn")
        self.btn_uninstall.setCursor(Qt.PointingHandCursor)
        self.btn_uninstall.clicked.connect(self._uninstall_selected)

        self.btn_leftovers = QPushButton("✨  Artıkları Tara")
        self.btn_leftovers.setProperty("class", "primary-btn")
        self.btn_leftovers.setCursor(Qt.PointingHandCursor)
        self.btn_leftovers.clicked.connect(self._scan_leftovers_selected)

        self.lbl_stats = QLabel("Toplam: 0")
        self.lbl_stats.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 700;")

        tb_layout.addWidget(self.search_box)
        tb_layout.addWidget(self.chk_all)
        tb_layout.addWidget(self.btn_refresh)
        tb_layout.addWidget(self.btn_uninstall)
        tb_layout.addWidget(self.btn_leftovers)
        tb_layout.addStretch()
        tb_layout.addWidget(self.lbl_stats)
        layout.addWidget(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Seç", "Program Adı", "Yayıncı", "Sürüm", "Yükleme Tarihi", "Tahmini Boyut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 52)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 180)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
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

        self._updating_checks = True
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(self.filtered_apps))
            for row, app in enumerate(self.filtered_apps):
                # Column 0: Centered CheckBox Widget
                is_chk = app.id in self.checked_app_ids
                cell = CheckBoxCell(app.id, is_chk, self._on_checkbox_toggled)
                self.table.setCellWidget(row, 0, cell)

                # Column 1: Name (Read-only)
                name_item = QTableWidgetItem(f"📦  {app.name}")
                name_item.setToolTip(app.name)
                name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 1, name_item)

                # Column 2: Publisher (Read-only)
                pub_item = QTableWidgetItem(app.publisher)
                pub_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 2, pub_item)

                # Column 3: Version (Read-only)
                ver_item = QTableWidgetItem(app.version)
                ver_item.setTextAlignment(Qt.AlignCenter)
                ver_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 3, ver_item)

                # Column 4: Date (Read-only)
                date_item = QTableWidgetItem(app.install_date or "-")
                date_item.setTextAlignment(Qt.AlignCenter)
                date_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 4, date_item)

                # Column 5: Size (Read-only)
                sz_str = format_bytes(app.size_bytes) if app.size_bytes > 0 else "-"
                sz_item = QTableWidgetItem(sz_str)
                sz_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                sz_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, 5, sz_item)
        finally:
            self._updating_checks = False
            self.table.setUpdatesEnabled(True)

        self._update_selection_ui()

    def _on_checkbox_toggled(self, app_id: str, is_checked: bool):
        if self._updating_checks:
            return
        if is_checked:
            self.checked_app_ids.add(app_id)
        else:
            self.checked_app_ids.discard(app_id)
        self._update_selection_ui()

    def _toggle_select_all(self, state: int):
        if self._updating_checks:
            return
        self._updating_checks = True
        is_chk = (state == Qt.Checked)
        for row, app in enumerate(self.filtered_apps):
            if is_chk:
                self.checked_app_ids.add(app.id)
            else:
                self.checked_app_ids.discard(app.id)
            cell = self.table.cellWidget(row, 0)
            if isinstance(cell, CheckBoxCell):
                cell.setChecked(is_chk)
        self._updating_checks = False
        self._update_selection_ui()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            row = self.table.currentRow()
            if 0 <= row < len(self.filtered_apps):
                cell = self.table.cellWidget(row, 0)
                if isinstance(cell, CheckBoxCell):
                    cell.checkbox.toggle()
                return
        super().keyPressEvent(event)

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self.filtered_apps):
            app = self.filtered_apps[row]
            confirm = QMessageBox.question(
                self,
                "Programı Kaldır",
                f"'{app.name}' programının resmi kaldırıcı aracı başlatılacak.\nDevam etmek istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    self.uninstaller.launch_uninstaller(app)
                    ans = QMessageBox.question(
                        self,
                        "Kaldırıcı Başlatıldı",
                        f"'{app.name}' kaldırıcı programı başlatıldı.\n\nKaldırma işlemi bittikten sonra kalan artık dosyaları şimdi taramak ister misiniz?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if ans == QMessageBox.Yes:
                        self._scan_leftovers_for_apps([app])
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Kaldırma komutu başlatılamadı:\n{e}")

    def _get_checked_apps(self) -> list[InstalledApp]:
        return [a for a in self.all_apps if a.id in self.checked_app_ids]

    def _get_selected_app(self) -> InstalledApp | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.filtered_apps):
            return self.filtered_apps[row]
        return None

    def _update_selection_ui(self):
        checked = self._get_checked_apps()
        cnt = len(checked)
        total = len(self.filtered_apps)

        # Synchronize chk_all state without triggering recursive toggles
        self.chk_all.blockSignals(True)
        if total > 0 and cnt == total:
            self.chk_all.setChecked(True)
        else:
            self.chk_all.setChecked(False)
        self.chk_all.blockSignals(False)

        if cnt > 1:
            total_size = sum(a.size_bytes for a in checked)
            size_str = f" ({format_bytes(total_size)})" if total_size > 0 else ""
            self.btn_uninstall.setText(f"🗑️  Toplu Kaldır ({cnt})")
            self.lbl_stats.setText(f"Toplam: {total} | Seçilen: {cnt}{size_str}")
        elif cnt == 1:
            self.btn_uninstall.setText("🗑️  Seçileni Kaldır (1)")
            self.lbl_stats.setText(f"Toplam: {total} | Seçilen: 1")
        else:
            self.btn_uninstall.setText("🗑️  Programı Kaldır")
            self.lbl_stats.setText(f"Toplam Program: {total}")


    def _uninstall_selected(self):
        checked_apps = self._get_checked_apps()

        # If user didn't check any checkboxes, fallback to currently highlighted row
        if not checked_apps:
            single = self._get_selected_app()
            if single:
                checked_apps = [single]

        if not checked_apps:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen kaldırmak istediğiniz en az bir programı tablodan seçin veya işaretleyin.")
            return

        if len(checked_apps) == 1:
            app = checked_apps[0]
            confirm = QMessageBox.question(
                self,
                "Programı Kaldır",
                f"'{app.name}' programının resmi kaldırıcı aracı başlatılacak.\nDevam etmek istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                try:
                    self.uninstaller.launch_uninstaller(app)
                    ans = QMessageBox.question(
                        self,
                        "Kaldırıcı Başlatıldı",
                        f"'{app.name}' kaldırıcı programı başlatıldı.\n\nKaldırma işlemi bittikten sonra kalan artık dosyaları şimdi taramak ister misiniz?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if ans == QMessageBox.Yes:
                        self._scan_leftovers_for_apps([app])
                except Exception as e:
                    QMessageBox.critical(self, "Hata", f"Kaldırma komutu başlatılamadı:\n{e}")
        else:
            # Batch Uninstall Flow
            app_list_preview = "\n".join(f"• {a.name}" for a in checked_apps[:8])
            if len(checked_apps) > 8:
                app_list_preview += f"\n... ve {len(checked_apps) - 8} program daha"

            confirm = QMessageBox.question(
                self,
                "Toplu Kaldırma Onayı",
                f"Seçilen {len(checked_apps)} adet program sırayla sistemden kaldırılacak:\n\n{app_list_preview}\n\nToplu kaldırma işlemini başlatmak istiyor musunuz?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                dlg = BatchUninstallDialog(checked_apps, self.uninstaller, self)
                dlg.exec_()
                self.checked_app_ids.clear()
                self.refresh_apps()

    def _scan_leftovers_selected(self):
        checked_apps = self._get_checked_apps()
        if not checked_apps:
            single = self._get_selected_app()
            if single:
                checked_apps = [single]

        if not checked_apps:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen artıklarını taramak istediğiniz programları seçin veya işaretleyin.")
            return

        self._scan_leftovers_for_apps(checked_apps)

    def _scan_leftovers_for_apps(self, apps: list[InstalledApp]):
        leftovers = self.uninstaller.scan_multiple_leftovers(apps)
        if not leftovers:
            target_name = f"{len(apps)} program" if len(apps) > 1 else f"'{apps[0].name}'"
            QMessageBox.information(
                self,
                "Artık Bulunamadı",
                f"{target_name} için sistemde herhangi bir artık dosya veya kayıt defteri kalıntısı bulunamadı. Sisteminiz temiz!"
            )
            return

        dlg = LeftoverDialog(apps if len(apps) > 1 else apps[0], leftovers, self.uninstaller, self)
        dlg.exec_()
