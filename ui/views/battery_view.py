"""
NovaCare System Suite - Battery Health & Power Diagnostics View
Live battery telemetry, wear level, design vs full capacity, charge cycles,
power plan switcher, and 1-click official Windows Battery Report generation.
Responsive layout optimized for all screen resolutions and DPI scaling factors.
"""
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QScrollArea, QMessageBox, QGridLayout, QLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from core.battery_reporter import BatteryReporter, BatteryInfo, is_battery_present
from core.utils import log_debug
from ui.components import StatCard
from ui.styles import (
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER
)

class BatteryHardwareWorker(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, reporter: BatteryReporter):
        super().__init__()
        self.reporter = reporter
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        hw = {}
        try:
            if not self._is_cancelled:
                hw = self.reporter.fetch_hardware_details()
        except Exception as e:
            log_debug(f"BatteryHardwareWorker error: {e}")
        finally:
            if not self._is_cancelled:
                self.finished.emit(hw)

class BatteryReportWorker(QThread):
    finished = pyqtSignal(bool, str)  # ok, path_or_error

    def __init__(self, reporter: BatteryReporter):
        super().__init__()
        self.reporter = reporter
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not self._is_cancelled:
                path = self.reporter.generate_html_report()
                if not self._is_cancelled:
                    self.finished.emit(True, path)
        except Exception as e:
            if not self._is_cancelled:
                self.finished.emit(False, str(e))

class BatteryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reporter = BatteryReporter()
        self.has_battery = is_battery_present()
        self.last_info: BatteryInfo | None = None
        self.hw_worker = None
        self.report_worker = None
        self._init_ui()
        if self.has_battery:
            # Auto-refresh timer every 10 seconds (ultra-fast, non-blocking psutil query)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._on_timer)
            self.timer.start(10000)
        else:
            self.timer = QTimer(self)

    def on_activated(self):
        """Called when user opens battery view."""
        if self.has_battery:
            self.refresh_metrics(query_hardware=False)
            self._fetch_hardware_async()

    def _fetch_hardware_async(self):
        if BatteryReporter._cached_hardware is not None:
            return
        self.hw_worker = BatteryHardwareWorker(self.reporter)
        self.hw_worker.finished.connect(self._on_hardware_loaded)
        self.hw_worker.start()

    def _on_hardware_loaded(self, hw: dict):
        self.refresh_metrics(query_hardware=False)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background-color: transparent; background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background-color: transparent; background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(4, 8, 4, 12)
        main_layout.setSpacing(14)
        main_layout.setSizeConstraint(QLayout.SetMinimumSize)

        # 1. Compact Header Toolbar
        hdr = QHBoxLayout()
        hdr.setSpacing(12)
        lbl_sec_title = QLabel("🔋  Windows Pil Aşınma Durumu & Güç Telemetrisi")
        lbl_sec_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        lbl_sec_title.setWordWrap(True)
        hdr.addWidget(lbl_sec_title, 1)

        self.btn_refresh = QPushButton("🔄  Yenile")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "primary-btn")
        self.btn_refresh.clicked.connect(lambda: self.refresh_metrics(query_hardware=True))
        hdr.addWidget(self.btn_refresh, 0, Qt.AlignVCenter)
        main_layout.addLayout(hdr)

        # 2. Top Stat Cards Grid (Responsive 2x2 or 1x4)
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(10)

        self.card_charge = StatCard("🔋", "Şarj Seviyesi", "%0", "Durum Alınıyor...")
        self.card_health = StatCard("❤️", "Pil Sağlığı", "%100", "Aşınma: %0")
        self.card_capacity = StatCard("⚡", "Kapasite (mWh)", "0 / 0", "Fabrika / Tam Şarj")
        self.card_hardware = StatCard("💻", "Donanım & Model", "-", "-")

        self.layout_stats_row = self.stats_grid
        main_layout.addLayout(self.stats_grid)
        self._relayout_stats(self.width() or 800)

        # 3. Main Central Card: Health & Telemetry Detail
        center_card = QFrame()
        center_card.setObjectName("CenterCard")
        center_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        center_card.setMinimumHeight(220)
        c_layout = QVBoxLayout(center_card)
        c_layout.setContentsMargins(18, 14, 18, 14)
        c_layout.setSpacing(14)
        c_layout.setSizeConstraint(QLayout.SetMinimumSize)

        # Title & Subtitle inside CenterCard
        top_center = QHBoxLayout()
        top_center.setSpacing(12)
        v_title = QVBoxLayout()
        v_title.setSpacing(3)
        self.lbl_main_status = QLabel("Pil Sağlık Durumu: Mükemmel")
        self.lbl_main_status.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLOR_ACCENT};")
        self.lbl_main_status.setWordWrap(True)
        self.lbl_runtime_desc = QLabel("Kalan Tahmini Süre: Hesaplanıyor...")
        self.lbl_runtime_desc.setObjectName("TextSecondary")
        self.lbl_runtime_desc.setStyleSheet("font-size: 12px;")
        self.lbl_runtime_desc.setWordWrap(True)
        v_title.addWidget(self.lbl_main_status)
        v_title.addWidget(self.lbl_runtime_desc)
        top_center.addLayout(v_title, 1)

        # Official Report Button
        self.btn_gen_report = QPushButton("📊  Resmi Windows Pil Raporu (.HTML)")
        self.btn_gen_report.setCursor(Qt.PointingHandCursor)
        self.btn_gen_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #041326;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #0EA5E9;
            }}
        """)
        self.btn_gen_report.clicked.connect(self._generate_and_open_report)
        top_center.addWidget(self.btn_gen_report, 0, Qt.AlignVCenter)
        c_layout.addLayout(top_center)

        # Two Progress Bars: Charge & Health
        bars_grid = QGridLayout()
        bars_grid.setSpacing(10)

        # Charge Bar
        lbl_c_tag = QLabel("Anlık Pil Şarjı:")
        lbl_c_tag.setStyleSheet("font-weight: 700;")
        lbl_c_tag.setWordWrap(True)
        self.pbar_charge = QProgressBar()
        self.pbar_charge.setFixedHeight(14)
        self.pbar_charge.setRange(0, 100)
        self.pbar_charge.setValue(0)
        self.lbl_charge_val = QLabel("%0")
        self.lbl_charge_val.setStyleSheet(f"font-weight: 800; color: {COLOR_ACCENT}; min-width: 45px;")

        bars_grid.addWidget(lbl_c_tag, 0, 0)
        bars_grid.addWidget(self.pbar_charge, 0, 1)
        bars_grid.addWidget(self.lbl_charge_val, 0, 2)

        # Health Bar
        lbl_h_tag = QLabel("Fabrika Sağlığı (Kapasite Koruma):")
        lbl_h_tag.setStyleSheet("font-weight: 700;")
        lbl_h_tag.setWordWrap(True)
        self.pbar_health = QProgressBar()
        self.pbar_health.setFixedHeight(14)
        self.pbar_health.setRange(0, 100)
        self.pbar_health.setValue(100)
        self.lbl_health_val = QLabel("%100")
        self.lbl_health_val.setStyleSheet(f"font-weight: 800; color: {COLOR_SUCCESS}; min-width: 45px;")

        bars_grid.addWidget(lbl_h_tag, 1, 0)
        bars_grid.addWidget(self.pbar_health, 1, 1)
        bars_grid.addWidget(self.lbl_health_val, 1, 2)

        bars_grid.setColumnStretch(1, 1)
        c_layout.addLayout(bars_grid)

        # Detailed parameters grid (2 columns with clean tile styling)
        param_grid = QGridLayout()
        param_grid.setSpacing(10)
        param_grid.setContentsMargins(0, 6, 0, 0)
        param_grid.setColumnStretch(0, 1)
        param_grid.setColumnStretch(1, 1)

        self.lbl_info_plan = QLabel("⚡ Aktif Güç Planı: -")
        self.lbl_info_cycle = QLabel("🔄 Şarj Döngü Sayısı: -")
        self.lbl_info_mfg = QLabel("🏭 Üretici / Model: -")
        self.lbl_info_chem = QLabel("🧪 Kimya / Teknoloji: -")

        for lbl in (self.lbl_info_plan, self.lbl_info_cycle, self.lbl_info_mfg, self.lbl_info_chem):
            lbl.setProperty("class", "param-tile")
            lbl.setWordWrap(True)

        param_grid.addWidget(self.lbl_info_plan, 0, 0)
        param_grid.addWidget(self.lbl_info_cycle, 0, 1)
        param_grid.addWidget(self.lbl_info_mfg, 1, 0)
        param_grid.addWidget(self.lbl_info_chem, 1, 1)
        c_layout.addLayout(param_grid)

        main_layout.addWidget(center_card)

        # 4. Battery Health & Lifespan Extension Tips Card
        card_tips = QFrame()
        card_tips.setObjectName("CardFrame")
        card_tips.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        card_tips.setMinimumHeight(140)
        t_layout = QVBoxLayout(card_tips)
        t_layout.setContentsMargins(18, 14, 18, 14)
        t_layout.setSpacing(8)
        t_layout.setSizeConstraint(QLayout.SetMinimumSize)

        lbl_tips_head = QLabel("💡  Lityum-İyon Pil Sağlığını ve Ömrünü Uzatma Kılavuzu")
        lbl_tips_head.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_ACCENT};")
        lbl_tips_head.setWordWrap(True)
        t_layout.addWidget(lbl_tips_head)

        tips_text = (
            "• <b>%20 - %80 Kuralı:</b> Lityum pillerin en sağlıklı kimyasal döngüsü %20 ile %80 arasındadır. Pilin %0'a kadar tamamen tükenmesi veya sürekli %100'de sıcak çalışması aşınmayı hızlandırır.<br>"
            "• <b>Sıcaklık Koruması:</b> Ağır yük altındayken laptopun havalandırma deliklerinin kapanmamasına özen gösterin. Yüksek sıcaklık pillerin en büyük yıpranma nedenidir.<br>"
            "• <b>Pil Kalibrasyonu:</b> 2-3 ayda bir pili %10 seviyesine kadar deşarj edip ardından kesintisiz tam şarja bırakmak, Windows pil sensörünü kalibre eder.<br>"
            "• <b>Resmi Rapor:</b> 'Resmi Windows Pil Raporu' butonuyla pilinizin son 3 günlük detaylı saatlik şarj/deşarj tablosunu ve tarihsel kapasite geçmişini görebilirsiniz."
        )
        lbl_tips_body = QLabel(tips_text)
        lbl_tips_body.setObjectName("TextMuted")
        lbl_tips_body.setStyleSheet("font-size: 11.5px; line-height: 1.5;")
        lbl_tips_body.setWordWrap(True)
        t_layout.addWidget(lbl_tips_body)

        main_layout.addWidget(card_tips)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _relayout_stats(self, width: int):
        """Dynamically adapts battery cards: 2x2 grid on narrower views, 1x4 on wide views."""
        for card in (self.card_charge, self.card_health, self.card_capacity, self.card_hardware):
            self.stats_grid.removeWidget(card)

        if width < 820:
            self.stats_grid.addWidget(self.card_charge, 0, 0)
            self.stats_grid.addWidget(self.card_health, 0, 1)
            self.stats_grid.addWidget(self.card_capacity, 1, 0)
            self.stats_grid.addWidget(self.card_hardware, 1, 1)
            self.stats_grid.setColumnStretch(0, 1)
            self.stats_grid.setColumnStretch(1, 1)
            self.stats_grid.setColumnStretch(2, 0)
            self.stats_grid.setColumnStretch(3, 0)
        else:
            self.stats_grid.addWidget(self.card_charge, 0, 0)
            self.stats_grid.addWidget(self.card_health, 0, 1)
            self.stats_grid.addWidget(self.card_capacity, 0, 2)
            self.stats_grid.addWidget(self.card_hardware, 0, 3)
            self.stats_grid.setColumnStretch(0, 1)
            self.stats_grid.setColumnStretch(1, 1)
            self.stats_grid.setColumnStretch(2, 1)
            self.stats_grid.setColumnStretch(3, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_stats(event.size().width())

    def _on_timer(self):
        if self.isVisible():
            self.refresh_metrics(query_hardware=False)

    def refresh_metrics(self, query_hardware: bool = False):
        try:
            info = self.reporter.get_battery_info(load_hardware_if_missing=query_hardware)
            self.last_info = info

            if not info.has_battery:
                # Desktop PC view
                self.card_charge.set_value("AC Güç", "Masaüstü (Şebeke)")
                self.card_health.set_value("Harici Pil Yok", "Masaüstü Bilgisayar")
                self.card_capacity.set_value("Sürekli", "220V Şebeke Beslemesi")
                self.card_hardware.set_value(info.computer_model[:18] if info.computer_model else "Masaüstü", "Masaüstü Sistemi")

                self.lbl_main_status.setText("Sistem Durumu: Masaüstü Bilgisayar (Sürekli Şebeke Gücü)")
                self.lbl_main_status.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLOR_SUCCESS};")
                self.lbl_runtime_desc.setText(f"Aktif Güç Planı: {info.active_power_plan} | Kesintisiz AC Besleme")
                self.btn_gen_report.setEnabled(False)
                self.btn_gen_report.setText("Masaüstünde Pil Raporu Yok")
                self.pbar_charge.setValue(100)
                self.lbl_charge_val.setText("AC")
                self.pbar_health.setValue(100)
                self.lbl_health_val.setText("OK")
                return

            # Laptop with battery
            self.card_charge.set_value(f"%{info.percent}", info.status_text)
            self.card_health.set_value(f"%{info.health_percent:.1f}", f"Aşınma: %{info.wear_percent:.1f}")

            des_k = f"{info.design_capacity_mwh:,} mWh" if info.design_capacity_mwh else "-"
            ful_k = f"{info.full_charge_capacity_mwh:,} mWh" if info.full_charge_capacity_mwh else "-"
            self.card_capacity.set_value(ful_k, f"Tasarım: {des_k}")

            mfg_name = info.manufacturer or "Dahili Pil"
            self.card_hardware.set_value(mfg_name, info.model_name or info.chemistry)

            # Center Card details
            if info.health_percent >= 85:
                status_color = COLOR_SUCCESS
                status_str = f"Pil Sağlığı: Mükemmel (%{info.health_percent:.1f})"
            elif info.health_percent >= 70:
                status_color = COLOR_WARNING
                status_str = f"Pil Sağlığı: İyi (%{info.health_percent:.1f} - Hafif Aşınma)"
            elif info.health_percent >= 50:
                status_color = COLOR_WARNING
                status_str = f"Pil Sağlığı: Orta (%{info.health_percent:.1f} - Değişim Önerilebilir)"
            else:
                status_color = COLOR_DANGER
                status_str = f"Pil Sağlığı: Kritik (%{info.health_percent:.1f} - Yüksek Aşınma)"

            self.lbl_main_status.setText(status_str)
            self.lbl_main_status.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {status_color};")
            self.lbl_runtime_desc.setText(f"Kalan Tahmini Süre: {info.runtime_formatted}  |  Durum: {info.status_text}")

            self.pbar_charge.setValue(info.percent)
            self.lbl_charge_val.setText(f"%{info.percent}")

            self.pbar_health.setValue(int(info.health_percent))
            self.lbl_health_val.setText(f"%{info.health_percent:.1f}")

            # Parameters
            self.lbl_info_plan.setText(f"⚡ Aktif Güç Planı: <b>{info.active_power_plan}</b>")
            cycle_str = f"{info.cycle_count} döngü" if info.cycle_count > 0 else "Desteklenmiyor / 0"
            self.lbl_info_cycle.setText(f"🔄 Şarj Döngü Sayısı: <b>{cycle_str}</b>")
            self.lbl_info_mfg.setText(f"🏭 Üretici & Model: <b>{info.manufacturer} {info.model_name}</b>")
            self.lbl_info_chem.setText(f"🧪 Kimya / Cihaz: <b>{info.chemistry} ({info.computer_model})</b>")

        except Exception:
            pass

    def _generate_and_open_report(self):
        if self.report_worker and self.report_worker.isRunning():
            return
        self.btn_gen_report.setEnabled(False)
        self.btn_gen_report.setText("⏳ Rapor Hazırlanıyor...")

        self.report_worker = BatteryReportWorker(self.reporter)
        self.report_worker.finished.connect(self._on_report_finished)
        self.report_worker.start()

    def _on_report_finished(self, ok: bool, result: str):
        self.btn_gen_report.setEnabled(True)
        self.btn_gen_report.setText("📊  Resmi Windows Pil Raporu (.HTML)")

        if ok:
            if os.path.exists(result):
                try:
                    os.startfile(result)
                except Exception:
                    pass
            QMessageBox.information(
                self,
                "Pil Raporu Hazırlandı",
                f"Resmi Windows Pil Tanılama Raporu başarıyla oluşturuldu ve varsayılan tarayıcınızda açıldı!\n\nDosya Konumu:\n{result}"
            )
        else:
            QMessageBox.critical(self, "Hata", f"Pil raporu oluşturulurken bir hata meydana geldi:\n{result}")
