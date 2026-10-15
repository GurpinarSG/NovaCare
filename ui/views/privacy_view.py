"""
NovaCare System Suite - Privacy Shield & System Tweaks View
Wipes user trace histories and configures Windows privacy/telemetry switches.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QMessageBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt
from core.privacy_tweaker import PrivacyTweaker, PrivacyTraceItem, SystemTweak
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class PrivacyView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tweaker = PrivacyTweaker()
        self.traces: list[PrivacyTraceItem] = []
        self.tweaks: list[SystemTweak] = []
        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # Header
        lbl_title = QLabel("Gizlilik Kalkanı ve Windows İyileştirme")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Kullanım geçmişinizi silerek gizliliğinizi koruyun ve arka plan telemetri servislerini kısıtlayın.")
        lbl_sub.setObjectName("ViewSubtitle")
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # Scroll Area for spacious layout
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setSpacing(20)

        # 1. Privacy Traces Card
        card_traces = QFrame()
        card_traces.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 18px 22px;
        """)
        traces_layout = QVBoxLayout(card_traces)
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

        # 2. Windows Privacy & Telemetry Tweaks Card
        card_tweaks = QFrame()
        card_tweaks.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 18px 22px;
        """)
        tweaks_layout = QVBoxLayout(card_tweaks)
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

    def _refresh_traces(self):
        # Clear container
        while self.traces_container.count():
            item = self.traces_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.traces = self.tweaker.scan_privacy_traces()
        total_items = sum(t.count for t in self.traces)
        self.lbl_traces_count.setText(f"Toplam {total_items} adet gizlilik izi tespit edildi")

        for trace in self.traces:
            chk = QCheckBox(f"<b>{trace.name}</b>  <span style='color:{TEXT_SECONDARY};'>({trace.description})</span>")
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
            row_frame.setStyleSheet(f"border-bottom: 1px solid {BORDER_COLOR}; padding-bottom: 8px;")
            r_lay = QHBoxLayout(row_frame)
            r_lay.setContentsMargins(0, 4, 0, 4)

            v_info = QVBoxLayout()
            lbl_name = QLabel(f"<b>{tweak.name}</b>")
            lbl_desc = QLabel(tweak.description)
            lbl_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            v_info.addWidget(lbl_name)
            v_info.addWidget(lbl_desc)

            chk_toggle = QCheckBox()
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
            # Revert checkbox without retriggering loop
            checkbox.blockSignals(True)
            checkbox.setChecked(not enable)
            checkbox.blockSignals(False)
            QMessageBox.critical(
                self,
                "Yetki Hatası",
                f"'{tweak.name}' ayarı uygulanamadı. Bu ayar için Yönetici (Administrator) izni gereklidir."
            )
