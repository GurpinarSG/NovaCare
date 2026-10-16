"""
NovaCare System Suite - Battery Health & Power Diagnostics View
Live battery telemetry, wear level, design vs full capacity, charge cycles,
power plan switcher, and 1-click official Windows Battery Report generation.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QScrollArea, QMessageBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from core.battery_reporter import BatteryReporter, BatteryInfo
from ui.components import StatCard
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class BatteryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reporter = BatteryReporter()
        self.last_info: BatteryInfo | None = None
        self._init_ui()
        self.refresh_metrics()

        # Auto-refresh timer every 10 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(10000)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background-color: transparent; background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background-color: transparent; background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        # Header
        lbl_title = QLabel("Windows Pil Sağlığı & Güç Raporlayıcı")
        lbl_title.setObjectName("ViewTitle")
        lbl_sub = QLabel("Dizüstü bilgisayarınızın pil aşınma durumunu, fabrika kapasitesini, kalan ömrünü analiz edin ve detaylı Windows pil raporunu oluşturun.")
        lbl_sub.setObjectName("ViewSubtitle")
        lbl_sub.setWordWrap(True)
        main_layout.addWidget(lbl_title)
        main_layout.addWidget(lbl_sub)

        # 1. Top Stat Cards Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)

        self.card_charge = StatCard("🔋", "Şarj Seviyesi", "%0", "Durum Alınıyor...")
        self.card_health = StatCard("❤️", "Pil Sağlığı", "%100", "Aşınma: %0")
        self.card_capacity = StatCard("⚡", "Kapasite (mWh)", "0 / 0", "Fabrika / Tam Şarj")
        self.card_hardware = StatCard("💻", "Donanım & Model", "-", "-")

        stats_layout.addWidget(self.card_charge, 1)
        stats_layout.addWidget(self.card_health, 1)
        stats_layout.addWidget(self.card_capacity, 1)
        stats_layout.addWidget(self.card_hardware, 1)
        main_layout.addLayout(stats_layout)

        # 2. Main Central Card: Health & Telemetry Detail
        center_card = QFrame()
        center_card.setObjectName("CenterCard")
        c_layout = QVBoxLayout(center_card)
        c_layout.setContentsMargins(24, 20, 24, 20)
        c_layout.setSpacing(16)

        # Title & Subtitle inside CenterCard
        top_center = QHBoxLayout()
        v_title = QVBoxLayout()
        self.lbl_main_status = QLabel("Pil Sağlık Durumu: Mükemmel")
        self.lbl_main_status.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {COLOR_ACCENT};")
        self.lbl_runtime_desc = QLabel("Kalan Tahmini Süre: Hesaplanıyor...")
        self.lbl_runtime_desc.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")
        v_title.addWidget(self.lbl_main_status)
        v_title.addWidget(self.lbl_runtime_desc)
        top_center.addLayout(v_title)
        top_center.addStretch()

        # Official Report Button
        self.btn_gen_report = QPushButton("📊  Resmi Windows Pil Raporunu Aç (.HTML)")
        self.btn_gen_report.setCursor(Qt.PointingHandCursor)
        self.btn_gen_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #041326;
                font-size: 13px;
                font-weight: 800;
                border: none;
                border-radius: 8px;
                padding: 10px 22px;
            }}
            QPushButton:hover {{
                background-color: #0EA5E9;
            }}
        """)
        self.btn_gen_report.clicked.connect(self._generate_and_open_report)
        top_center.addWidget(self.btn_gen_report)
        c_layout.addLayout(top_center)

        # Two Progress Bars: Charge & Health
        bars_grid = QGridLayout()
        bars_grid.setSpacing(10)

        # Charge Bar
        lbl_c_tag = QLabel("Anlık Pil Şarjı:")
        lbl_c_tag.setStyleSheet(f"font-weight: 700; color: {TEXT_PRIMARY};")
        self.pbar_charge = QProgressBar()
        self.pbar_charge.setFixedHeight(18)
        self.pbar_charge.setRange(0, 100)
        self.pbar_charge.setValue(0)
        self.lbl_charge_val = QLabel("%0")
        self.lbl_charge_val.setStyleSheet(f"font-weight: 800; color: {COLOR_ACCENT}; min-width: 45px;")

        bars_grid.addWidget(lbl_c_tag, 0, 0)
        bars_grid.addWidget(self.pbar_charge, 0, 1)
        bars_grid.addWidget(self.lbl_charge_val, 0, 2)

        # Health Bar
        lbl_h_tag = QLabel("Fabrika Sağlığı (Kapasite Koruma):")
        lbl_h_tag.setStyleSheet(f"font-weight: 700; color: {TEXT_PRIMARY};")
        self.pbar_health = QProgressBar()
        self.pbar_health.setFixedHeight(18)
        self.pbar_health.setRange(0, 100)
        self.pbar_health.setValue(100)
        self.lbl_health_val = QLabel("%100")
        self.lbl_health_val.setStyleSheet(f"font-weight: 800; color: {COLOR_SUCCESS}; min-width: 45px;")

        bars_grid.addWidget(lbl_h_tag, 1, 0)
        bars_grid.addWidget(self.pbar_health, 1, 1)
        bars_grid.addWidget(self.lbl_health_val, 1, 2)

        bars_grid.setColumnStretch(1, 1)
        c_layout.addLayout(bars_grid)

        # Detailed parameters grid (2 columns)
        param_grid = QGridLayout()
        param_grid.setSpacing(10)
        param_grid.setContentsMargins(4, 8, 4, 4)

        self.lbl_info_plan = QLabel("⚡ Aktif Güç Planı: -")
        self.lbl_info_cycle = QLabel("🔄 Şarj Döngü Sayısı: -")
        self.lbl_info_mfg = QLabel("🏭 Üretici / Model: -")
        self.lbl_info_chem = QLabel("🧪 Kimya / Teknoloji: -")

        for lbl in (self.lbl_info_plan, self.lbl_info_cycle, self.lbl_info_mfg, self.lbl_info_chem):
            lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY};")

        param_grid.addWidget(self.lbl_info_plan, 0, 0)
        param_grid.addWidget(self.lbl_info_cycle, 0, 1)
        param_grid.addWidget(self.lbl_info_mfg, 1, 0)
        param_grid.addWidget(self.lbl_info_chem, 1, 1)
        c_layout.addLayout(param_grid)

        main_layout.addWidget(center_card)

        # 3. Battery Health & Lifespan Extension Tips Card
        card_tips = QFrame()
        card_tips.setObjectName("CardFrame")
        t_layout = QVBoxLayout(card_tips)
        t_layout.setContentsMargins(22, 18, 22, 18)
        t_layout.setSpacing(10)

        lbl_tips_head = QLabel("💡  Lityum-İyon Pil Sağlığını ve Ömrünü Uzatma Kılavuzu")
        lbl_tips_head.setStyleSheet("font-size: 15px; font-weight: 700; color: #38BDF8;")
        t_layout.addWidget(lbl_tips_head)

        tips_text = (
            "• <b>%20 - %80 Kuralı:</b> Lityum pillerin en sağlıklı kimyasal döngüsü %20 ile %80 arasındadır. Pilin %0'a kadar tamamen tükenmesi veya sürekli %100'de sıcak çalışması aşınmayı hızlandırır.<br>"
            "• <b>Sıcaklık Koruması:</b> Oyun oynarken veya ağır yük altındayken laptopun havalandırma deliklerinin kapanmamasına özen gösterin. Yüksek sıcaklık pillerin en büyük yıpranma nedenidir.<br>"
            "• <b>Pil Kalibrasyonu:</b> 2-3 ayda bir pili %10 seviyesine kadar deşarj edip ardından kesintisiz tam şarja bırakmak, Windows pil yüzdesi sensörünü kalibre eder.<br>"
            "• <b>Resmi Rapor:</b> 'Resmi Windows Pil Raporu' butonuyla pilinizin son 3 günlük detaylı saatlik şarj/deşarj tablosunu ve tarihsel kapasite geçmişini görebilirsiniz."
        )
        lbl_tips_body = QLabel(tips_text)
        lbl_tips_body.setStyleSheet(f"font-size: 12px; color: {TEXT_SECONDARY}; line-height: 1.5;")
        lbl_tips_body.setWordWrap(True)
        t_layout.addWidget(lbl_tips_body)

        main_layout.addWidget(card_tips)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def _on_timer(self):
        if self.isVisible():
            self.refresh_metrics()

    def refresh_metrics(self):
        try:
            info = self.reporter.get_battery_info()
            self.last_info = info

            if not info.has_battery:
                # Desktop PC view
                self.card_charge.set_value("AC Güç", "Masaüstü (Şebeke)")
                self.card_health.set_value("Harici Pil Yok", "Masaüstü Bilgisayar")
                self.card_capacity.set_value("Sürekli", "220V Şebeke Beslemesi")
                self.card_hardware.set_value(info.computer_model[:18], "Masaüstü Sistemi")

                self.lbl_main_status.setText("Sistem Durumu: Masaüstü Bilgisayar (Sürekli Şebeke Gücü)")
                self.lbl_main_status.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLOR_SUCCESS};")
                self.lbl_runtime_desc.setText(f"Aktif Güç Planı: {info.active_power_plan} | Kesintisiz AC Besleme")
                self.btn_gen_report.setEnabled(False)
                self.btn_gen_report.setText("Masaüstü Sisteminde Pil Raporu Oluşturulamaz")
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
            self.lbl_main_status.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {status_color};")
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
        try:
            self.btn_gen_report.setEnabled(False)
            self.btn_gen_report.setText("⏳ Rapor Hazırlanıyor...")
            report_path = self.reporter.open_html_report()
            QMessageBox.information(
                self,
                "Pil Raporu Hazırlandı",
                f"Resmi Windows Pil Tanılama Raporu başarıyla oluşturuldu ve varsayılan tarayıcınızda açıldı!\n\nDosya Konumu:\n{report_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Pil raporu oluşturulurken bir hata meydana geldi:\n{e}")
        finally:
            self.btn_gen_report.setEnabled(True)
            self.btn_gen_report.setText("📊  Resmi Windows Pil Raporunu Aç (.HTML)")
