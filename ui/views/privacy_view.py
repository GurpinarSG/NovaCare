"""
NovaCare System Suite - Privacy Shield, Bloatware & Telemetry Cleaner View
Wipes user trace histories, removes pre-installed Windows bloatware apps,
and terminates deep Windows telemetry tracking services.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QMessageBox, QFrame, QScrollArea, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from core.privacy_tweaker import PrivacyTweaker, PrivacyTraceItem, SystemTweak
from core.bloatware_cleaner import BloatwareCleaner, BloatwareItem
from core.utils import is_admin
from ui.styles import (
    BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class BloatwareScanWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.cleaner = BloatwareCleaner()

    def run(self):
        items = self.cleaner.scan_installed_bloatware()
        self.finished.emit(items)

class BloatwareRemoveWorker(QThread):
    finished = pyqtSignal(int, list) # count, errors

    def __init__(self, packages: list[str]):
        super().__init__()
        self.packages = packages
        self.cleaner = BloatwareCleaner()

    def run(self):
        removed = 0
        errs = []
        for pkg in self.packages:
            ok, msg = self.cleaner.remove_bloatware_package(pkg)
            if ok:
                removed += 1
            else:
                errs.append(f"{pkg}: {msg}")
        self.finished.emit(removed, errs)

class DeepTelemetryWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.cleaner = BloatwareCleaner()

    def run(self):
        res = self.cleaner.disable_deep_telemetry()
        self.finished.emit(res)

class PrivacyView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tweaker = PrivacyTweaker()
        self.bloatware_cleaner = BloatwareCleaner()
        self.traces: list[PrivacyTraceItem] = []
        self.tweaks: list[SystemTweak] = []
        self.bloatware_items: list[BloatwareItem] = []
        self.selected_bloatware: set[str] = set()
        
        self.scan_worker = None
        self.remove_worker = None
        self.telemetry_worker = None

        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header
        lbl_title = QLabel("Gizlilik Kalkanı, Bloatware & Telemetri Engelleyici")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Kullanım geçmişinizi silin, Windows 10/11 ile gelen gereksiz bloatware uygulamalarını kaldırın ve telemetriyi kapatın.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Scroll Area for spacious layout (fully transparent background)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent; background: transparent;")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)

        # 1. Bloatware & Telemetry Shield Card (FEATURE HIGHLIGHT)
        card_bloatware = QFrame()
        card_bloatware.setObjectName("CardFrame")
        b_layout = QVBoxLayout(card_bloatware)
        b_layout.setContentsMargins(22, 18, 22, 18)
        b_layout.setSpacing(12)

        lbl_b_title = QLabel("📦  Windows Bloatware & Telemetri Temizleyici")
        lbl_b_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #38BDF8;")
        b_layout.addWidget(lbl_b_title)

        lbl_b_desc = QLabel("Windows ile yüklü gelen Cortana, Bing Hava Durumu, Bing Haberler, Xbox Game Bar gibi arka planda veri ve bellek harcayan uygulamaları kaldırın.")
        lbl_b_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        lbl_b_desc.setWordWrap(True)
        b_layout.addWidget(lbl_b_desc)

        # Bloatware Controls Bar
        b_bar = QHBoxLayout()
        b_bar.setSpacing(10)

        self.btn_scan_bloatware = QPushButton("🔍  Bloatware Tara")
        self.btn_scan_bloatware.setCursor(Qt.PointingHandCursor)
        self.btn_scan_bloatware.setProperty("class", "secondary-btn")
        self.btn_scan_bloatware.clicked.connect(self._scan_bloatware)
        b_bar.addWidget(self.btn_scan_bloatware)

        self.btn_remove_bloatware = QPushButton("🗑️  Seçilenleri Kaldır")
        self.btn_remove_bloatware.setProperty("class", "danger-btn")
        self.btn_remove_bloatware.setCursor(Qt.PointingHandCursor)
        self.btn_remove_bloatware.setEnabled(False)
        self.btn_remove_bloatware.clicked.connect(self._remove_selected_bloatware)
        b_bar.addWidget(self.btn_remove_bloatware)

        self.btn_deep_telemetry = QPushButton("🛑  Derin Telemetriyi Kapat")
        self.btn_deep_telemetry.setToolTip("Windows arka plan telemetri servislerini ve veri toplama politikalarını kalıcı olarak kapatır")
        self.btn_deep_telemetry.setCursor(Qt.PointingHandCursor)
        self.btn_deep_telemetry.clicked.connect(self._disable_deep_telemetry)
        b_bar.addWidget(self.btn_deep_telemetry)

        b_bar.addStretch()
        b_layout.addLayout(b_bar)

        self.bloatware_container = QVBoxLayout()
        self.bloatware_container.setSpacing(6)
        b_layout.addLayout(self.bloatware_container)

        self.lbl_bloatware_status = QLabel("Bloatware taraması bekleniyor...")
        self.lbl_bloatware_status.setStyleSheet("font-size: 12px; color: #94A3B8;")
        b_layout.addWidget(self.lbl_bloatware_status)

        content_layout.addWidget(card_bloatware)

        # 2. Privacy Traces Card
        card_traces = QFrame()
        card_traces.setObjectName("CardFrame")
        traces_layout = QVBoxLayout(card_traces)
        traces_layout.setContentsMargins(22, 18, 22, 18)
        traces_layout.setSpacing(12)

        lbl_traces_title = QLabel("🛡️  Kullanıcı Etkinlik ve Gizlilik İzleri")
        lbl_traces_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        traces_layout.addWidget(lbl_traces_title)

        self.traces_container = QVBoxLayout()
        self.traces_container.setSpacing(8)
        traces_layout.addLayout(self.traces_container)

        # Traces Action Bar
        t_bar = QHBoxLayout()
        self.btn_clean_traces = QPushButton("🧹  Seçili İzleri Temizle")
        self.btn_clean_traces.setProperty("class", "success-btn")
        self.btn_clean_traces.setCursor(Qt.PointingHandCursor)
        self.btn_clean_traces.clicked.connect(self._clean_traces)

        self.lbl_traces_count = QLabel("0 iz bulundu")
        self.lbl_traces_count.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 600;")

        t_bar.addWidget(self.btn_clean_traces)
        t_bar.addSpacing(16)
        t_bar.addWidget(self.lbl_traces_count)
        t_bar.addStretch()
        traces_layout.addLayout(t_bar)

        content_layout.addWidget(card_traces)

        # 3. Windows Privacy & Telemetry Tweaks Card
        card_tweaks = QFrame()
        card_tweaks.setObjectName("CardFrame")
        tweaks_layout = QVBoxLayout(card_tweaks)
        tweaks_layout.setContentsMargins(22, 18, 22, 18)
        tweaks_layout.setSpacing(14)

        lbl_tweaks_title = QLabel("⚙️  Windows 10/11 Gizlilik ve Hızlandırma Ayarları")
        lbl_tweaks_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        tweaks_layout.addWidget(lbl_tweaks_title)

        self.tweaks_container = QVBoxLayout()
        self.tweaks_container.setSpacing(10)
        tweaks_layout.addLayout(self.tweaks_container)

        content_layout.addWidget(card_tweaks)
        content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def refresh_all(self):
        self._refresh_traces()
        self._refresh_tweaks()
        self._scan_bloatware()

    def _scan_bloatware(self):
        self.btn_scan_bloatware.setEnabled(False)
        self.lbl_bloatware_status.setText("Yüklü bloatware paketleri taranıyor...")
        self.scan_worker = BloatwareScanWorker()
        self.scan_worker.finished.connect(self._on_bloatware_scanned)
        self.scan_worker.start()

    def _on_bloatware_scanned(self, items: list[BloatwareItem]):
        self.btn_scan_bloatware.setEnabled(True)
        self.bloatware_items = items
        self.selected_bloatware.clear()

        while self.bloatware_container.count():
            it = self.bloatware_container.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        installed_count = 0
        for b_item in items:
            if not b_item.installed:
                continue
            installed_count += 1
            self.selected_bloatware.add(b_item.package_name)

            row = QFrame()
            row.setStyleSheet(f"background-color: transparent; border: none; border-bottom: 1px solid {BORDER_COLOR}; padding-bottom: 4px;")
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(0, 2, 0, 2)

            chk = QCheckBox(f"<b>{b_item.display_name}</b>  <span style='color:{TEXT_MUTED};'>({b_item.category})</span>")
            chk.setStyleSheet("background-color: transparent;")
            chk.setChecked(True)
            chk.stateChanged.connect(lambda state, name=b_item.package_name: self._on_bloatware_chk(name, state))
            r_lay.addWidget(chk)

            lbl_d = QLabel(b_item.description)
            lbl_d.setStyleSheet(f"color:{TEXT_SECONDARY}; font-size: 11px;")
            lbl_d.setWordWrap(True)
            r_lay.addWidget(lbl_d)
            r_lay.addStretch()

            self.bloatware_container.addWidget(row)

        if installed_count > 0:
            self.lbl_bloatware_status.setText(f"Sistemde {installed_count} adet kaldırılabilir bloatware tespit edildi.")
            self.btn_remove_bloatware.setEnabled(True)
        else:
            self.lbl_bloatware_status.setText("Tebrikler! Sisteminizde bilinen herhangi bir bloatware paketi bulunamadı.")
            self.btn_remove_bloatware.setEnabled(False)

    def _on_bloatware_chk(self, pkg_name: str, state: int):
        if state == Qt.Checked:
            self.selected_bloatware.add(pkg_name)
        else:
            self.selected_bloatware.discard(pkg_name)
        self.btn_remove_bloatware.setEnabled(len(self.selected_bloatware) > 0)

    def _remove_selected_bloatware(self):
        if not self.selected_bloatware:
            return

        has_admin = is_admin()
        admin_note = (
            "\n\n🛡️ Yönetici Yetkisi: Paketler sistem düzeyinde (AllUsers) kökten ve kalıcı olarak temizlenecektir."
            if has_admin else
            "\n\n💡 İpucu: Sistem düzeyindeki paketleri tamamen kaldırabilmek için uygulamanın Yönetici olarak çalıştırılması önerilir."
        )

        reply = QMessageBox.question(
            self,
            "Bloatware Kaldırma Onayı",
            f"Seçilen {len(self.selected_bloatware)} adet uygulama sistemden kaldırılacak.{admin_note}\n\nDevam etmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_remove_bloatware.setEnabled(False)
        self.lbl_bloatware_status.setText("Seçilen uygulamalar kaldırılıyor, lütfen bekleyin...")
        self.remove_worker = BloatwareRemoveWorker(list(self.selected_bloatware))
        self.remove_worker.finished.connect(self._on_bloatware_removed)
        self.remove_worker.start()

    def _on_bloatware_removed(self, count: int, errors: list):
        QMessageBox.information(
            self,
            "İşlem Tamamlandı",
            f"{count} adet bloatware uygulaması başarıyla kaldırıldı!"
        )
        self._scan_bloatware()

    def _disable_deep_telemetry(self):
        has_admin = is_admin()
        admin_note = (
            "\n\n🛡️ Yönetici Yetkisi Aktif: Servisler ve kayıt defteri grup ilkeleri en derin seviyede kapatılacaktır."
            if has_admin else
            "\n\n⚠️ Dikkat: Telemetri servislerini tamamen durdurabilmek için Yönetici Yetkisi gereklidir."
        )

        reply = QMessageBox.question(
            self,
            "Derin Telemetri Kapatma",
            f"Bu işlem Windows arka plan telemetri servislerini (DiagTrack, dmwappushservice vb.) kalıcı olarak devre dışı bırakır ve Microsoft veri toplama politikalarını kısıtlar.{admin_note}\n\nUygulamak istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.telemetry_worker = DeepTelemetryWorker()
        self.telemetry_worker.finished.connect(self._on_telemetry_finished)
        self.telemetry_worker.start()

    def _on_telemetry_finished(self, res: dict):
        services = res.get("disabled_services", [])
        svc_str = "\n• " + "\n• ".join(services) if services else "\n(Servisler zaten devre dışı)"
        QMessageBox.information(
            self,
            "Telemetri Kapatıldı",
            f"Aşağıdaki telemetri servisleri durduruldu ve başlangıçları devre dışı bırakıldı:{svc_str}\n\nKayıt defteri telemetri ve tüketici promosyonu engelleri uygulandı!"
        )

    def _refresh_traces(self):
        while self.traces_container.count():
            item = self.traces_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.traces = self.tweaker.scan_privacy_traces()
        total_items = sum(t.count for t in self.traces)
        self.lbl_traces_count.setText(f"Toplam {total_items} adet gizlilik izi tespit edildi")

        for trace in self.traces:
            chk = QCheckBox(f"<b>{trace.name}</b>  <span style='color:{TEXT_SECONDARY};'>({trace.description})</span>")
            chk.setStyleSheet("background-color: transparent; background: transparent;")
            chk.setChecked(trace.selected)
            chk.stateChanged.connect(lambda state, t=trace: self._on_trace_toggle(t, state))
            self.traces_container.addWidget(chk)

    def _on_trace_toggle(self, trace: PrivacyTraceItem, state: int):
        trace.selected = (state == Qt.Checked)

    def _clean_traces(self):
        selected_ids = {t.id for t in self.traces if t.selected}
        if not selected_ids:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen temizlemek istediğiniz en az bir gizlilik izini seçin.")
            return

        cleaned_count = self.tweaker.clean_privacy_traces(selected_ids)
        QMessageBox.information(
            self,
            "Gizlilik Temizliği Tamamlandı",
            f"Seçilen gizlilik izleri başarıyla temizlendi!\nSilinen kayıt sayısı: {cleaned_count}"
        )
        self._refresh_traces()

    def _refresh_tweaks(self):
        while self.tweaks_container.count():
            item = self.tweaks_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.tweaks = self.tweaker.check_tweak_statuses()

        for tweak in self.tweaks:
            row_frame = QFrame()
            row_frame.setStyleSheet(f"background-color: transparent; background: transparent; border: none; border-bottom: 1px solid {BORDER_COLOR}; padding-bottom: 8px;")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(0, 4, 0, 4)

            v_info = QVBoxLayout()
            lbl_name = QLabel(f"<b>{tweak.name}</b>")
            lbl_name.setWordWrap(True)
            lbl_desc = QLabel(tweak.description)
            lbl_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            lbl_desc.setWordWrap(True)
            v_info.addWidget(lbl_name)
            v_info.addWidget(lbl_desc)

            chk_toggle = QCheckBox()
            chk_toggle.setStyleSheet("background-color: transparent; background: transparent;")
            chk_toggle.setText("Etkinleştirilmiş" if tweak.current_enabled else "Kapatılmış")
            chk_toggle.setChecked(tweak.current_enabled)
            chk_toggle.setCursor(Qt.PointingHandCursor)
            chk_toggle.stateChanged.connect(lambda state, tw=tweak, c=chk_toggle: self._on_tweak_toggle(tw, c, state))

            r_lay.addLayout(v_info)
            r_lay.addStretch()
            r_lay.addWidget(chk_toggle)

            self.tweaks_container.addWidget(row_frame)

    def _on_tweak_toggle(self, tweak: SystemTweak, checkbox: QCheckBox, state: int):
        enable = (state == Qt.Checked)
        success = self.tweaker.apply_tweak(tweak, enable)
        if success:
            checkbox.setText("Etkinleştirilmiş" if enable else "Kapatılmış")
        else:
            checkbox.blockSignals(True)
            checkbox.setChecked(not enable)
            checkbox.blockSignals(False)
            QMessageBox.critical(
                self,
                "Yetki Hatası",
                f"'{tweak.name}' ayarı uygulanamadı. Bu ayar için Yönetici (Administrator) izni gereklidir."
            )
