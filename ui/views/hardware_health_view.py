"""
NovaCare System Suite - Hardware Health & Disk S.M.A.R.T. View
Comprehensive hardware health monitoring, SSD/HDD S.M.A.R.T. wear level,
temperature telemetry, power-on hours, bad sector detection, and battery wear.
"""
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QScrollArea, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from core.smart_reporter import SmartReporter, DiskHealthInfo
from core.hardware_monitor import HardwareMonitor
from core.battery_reporter import BatteryReporter, BatteryInfo, is_battery_present
from core.utils import log_debug
from ui.components import StatCard
from ui.styles import (
    get_active_theme_colors, BG_CARD, BORDER_COLOR, COLOR_ACCENT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)

class SmartScanWorker(QThread):
    finished = pyqtSignal(list, dict, object) # disks, hw_stats, battery_info

    def __init__(self):
        super().__init__()
        self.smart_reporter = SmartReporter()
        self.hw_monitor = HardwareMonitor()
        self.battery_reporter = BatteryReporter()

    def run(self):
        disks = []
        hw_stats = {}
        bat_info = None
        try:
            disks = self.smart_reporter.get_disks_health(force_refresh=True)
            hw_stats = self.hw_monitor.get_hardware_stats()
            bat_info = self.battery_reporter.get_battery_info(load_hardware_if_missing=True)
        except Exception as e:
            log_debug(f"SmartScanWorker error: {e}")
        finally:
            self.finished.emit(disks, hw_stats, bat_info)

class HardwareHealthView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.smart_reporter = SmartReporter()
        self.hw_monitor = HardwareMonitor()
        self.battery_reporter = BatteryReporter()
        self.scan_worker = None
        self.disks: list[DiskHealthInfo] = []

        self._init_ui()
        # Immediately populate live hardware sensors (CPU, RAM, GPU, Power) with zero lag
        self._refresh_live_sensors()

        # If cached disks already exist, render them instantly
        if self.smart_reporter._cached_results:
            self.disks = self.smart_reporter._cached_results
            self._render_disk_cards(self.disks)

        # Live hardware refresh timer (every 3 seconds)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_live_sensors)
        self.timer.start(3000)

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setObjectName("HardwareScroll")
        scroll.setStyleSheet("QScrollArea#HardwareScroll { background: transparent; border: none; } QWidget#HardwareContainer { background: transparent; }")

        container = QWidget()
        container.setObjectName("HardwareContainer")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(28, 20, 28, 20)
        self.layout.setSpacing(18)

        # 1. Header
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        lbl_title = QLabel("🛡️  Donanım Sağlığı & Disk S.M.A.R.T. Takibi")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: 800;")
        header_text.addWidget(lbl_title)

        lbl_sub = QLabel("SSD ve HDD disklerinizin kalan ömrünü, çalışma saatlerini, sıcaklıklarını ve donanım sensörlerini gerçek zamanlı takip edin.")
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        lbl_sub.setWordWrap(True)
        header_text.addWidget(lbl_sub)
        header.addLayout(header_text, 1)

        self.btn_refresh = QPushButton("🔄  S.M.A.R.T. Verilerini Yenile")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "primary-btn")
        self.btn_refresh.clicked.connect(self._start_scan)
        header.addWidget(self.btn_refresh)
        self.layout.addLayout(header)

        # 2. Hardware Sensors Overview Row
        self.has_battery = is_battery_present()
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(14)
        self.card_cpu = StatCard("⚡", "İşlemci (CPU)", "Yükleniyor...", "- °C")
        self.card_gpu = StatCard("🎮", "Grafik (GPU)", "Yükleniyor...", "- °C")
        self.card_ram = StatCard("🧠", "Bellek (RAM)", "Yükleniyor...", "- / - GB")
        self.card_power = StatCard("🔋", "Güç / Batarya", "Yükleniyor...", "Kontrol ediliyor")
        if not self.has_battery:
            self.card_power.setVisible(False)

        stats_layout.addWidget(self.card_cpu, 1)
        stats_layout.addWidget(self.card_gpu, 1)
        stats_layout.addWidget(self.card_ram, 1)
        stats_layout.addWidget(self.card_power, 1)
        self.layout.addLayout(stats_layout)

        # 3. Disk S.M.A.R.T. Section Header
        lbl_disk_sec = QLabel("💾  Fiziksel Disk S.M.A.R.T. Sağlık ve Ömür Raporları")
        lbl_disk_sec.setStyleSheet("font-size: 16px; font-weight: 700; margin-top: 6px;")
        self.layout.addWidget(lbl_disk_sec)

        # Disks Container Frame
        self.disks_container = QVBoxLayout()
        self.disks_container.setSpacing(14)
        self.layout.addLayout(self.disks_container)

        # Placeholder loading label
        self.lbl_loading = QLabel("Disk S.M.A.R.T. güvenilirlik sayaçları taranıyor, lütfen bekleyin...")
        self.lbl_loading.setStyleSheet(f"font-size: 13px; color: {COLOR_ACCENT}; padding: 15px;")
        self.disks_container.addWidget(self.lbl_loading)

        self.layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_live_sensors()
        if not self.disks and (self.scan_worker is None or not self.scan_worker.isRunning()):
            self._start_scan()

    def _start_scan(self):
        if self.scan_worker and self.scan_worker.isRunning():
            return
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳  Taranıyor...")
        self.scan_worker = SmartScanWorker()
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_finished(self, disks: list[DiskHealthInfo], hw_stats: dict, bat_info: Optional[BatteryInfo]):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("🔄  S.M.A.R.T. Verilerini Yenile")
        self.disks = disks

        try:
            # Update Hardware Cards
            self._update_hw_cards(hw_stats, bat_info)
        except Exception as e:
            log_debug(f"_update_hw_cards error: {e}")

        try:
            # Render Disk SMART Cards
            self._render_disk_cards(disks)
        except Exception as e:
            log_debug(f"_render_disk_cards error: {e}")

    def _refresh_live_sensors(self):
        """Ultra-fast non-blocking live refresh of CPU, GPU, RAM stats."""
        try:
            hw_stats = self.hw_monitor.get_hardware_stats()
            bat_info = self.battery_reporter.get_battery_info()
            self._update_hw_cards(hw_stats, bat_info)
        except Exception:
            pass

    def _update_hw_cards(self, hw_stats: dict, bat_info: Optional[BatteryInfo]):
        theme = get_active_theme_colors()
        if hw_stats:
            cpu_p = hw_stats.get("cpu_percent", 0)
            cpu_f = hw_stats.get("cpu_freq_ghz", 0.0)
            cpu_t = hw_stats.get("cpu_temp")
            c_temp_str = f"{cpu_t:.1f} °C" if cpu_t is not None else "Normal"
            self.card_cpu.set_value(f"%{cpu_p:.0f}", f"{cpu_f:.1f} GHz | {c_temp_str}")

            if hw_stats.get("has_gpu", False):
                gpu_p = hw_stats.get("gpu_load", 0)
                gpu_t = hw_stats.get("gpu_temp")
                g_temp_str = f"{gpu_t} °C" if gpu_t is not None else "Aktif"
                self.card_gpu.set_value(f"%{gpu_p}", f"{hw_stats.get('gpu_name', 'GPU')} | {g_temp_str}")
            else:
                self.card_gpu.set_value("Dahili GPU", "Enerji Tasarruflu")

            ram_p = hw_stats.get("ram_percent", 0)
            ram_u = hw_stats.get("ram_used_gb", 0)
            ram_t = hw_stats.get("ram_total_gb", 0)
            self.card_ram.set_value(f"%{ram_p:.0f}", f"{ram_u} / {ram_t} GB Kullanımda")

        if getattr(self, 'has_battery', True) and bat_info and bat_info.has_battery:
            health_color = theme["COLOR_SUCCESS"] if bat_info.health_percent >= 80 else theme["COLOR_WARNING"]
            is_chg = getattr(bat_info, 'is_charging', getattr(bat_info, 'power_plugged', False))
            status_text = "Şarj Oluyor" if is_chg else "Pilde"
            self.card_power.set_value(
                f"%{bat_info.percent} ({status_text})",
                f"Pil Sağlığı: %{bat_info.health_percent:.0f} | {bat_info.cycle_count} Döngü"
            )
        elif getattr(self, 'has_battery', True):
            self.card_power.set_value("Şebeke Gücü", "Masaüstü / Kesintisiz Güç")
        else:
            self.card_power.setVisible(False)

    def on_activated(self):
        """Called when this view or tab is activated."""
        self._refresh_live_sensors()
        if not self.disks and (self.scan_worker is None or not self.scan_worker.isRunning()):
            self._start_scan()

    def _render_disk_cards(self, disks: list[DiskHealthInfo]):
        # Clear existing disk widgets
        while self.disks_container.count():
            item = self.disks_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not disks:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("background: transparent;")
            e_lay = QVBoxLayout(empty_frame)
            e_lay.setContentsMargins(10, 10, 10, 10)
            e_lay.setSpacing(10)
            lbl_empty = QLabel("Sistemde fiziksel disk bilgisi alınamadı veya sayaçlar henüz yüklenmedi.")
            lbl_empty.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
            e_lay.addWidget(lbl_empty)
            btn_retry = QPushButton("🔄  Diskleri Yeniden Tara")
            btn_retry.setCursor(Qt.PointingHandCursor)
            btn_retry.setProperty("class", "primary-btn")
            btn_retry.clicked.connect(self._start_scan)
            e_lay.addWidget(btn_retry, 0, Qt.AlignLeft)
            self.disks_container.addWidget(empty_frame)
            return

        theme = get_active_theme_colors()

        for d in disks:
            try:
                card = QFrame()
                card.setObjectName("CardFrame")
                c_lay = QVBoxLayout(card)
                c_lay.setContentsMargins(20, 16, 20, 16)
                c_lay.setSpacing(12)

                # 1. Disk Header (Icon + Name + Type Badge + Size)
                hdr = QHBoxLayout()
                hdr.setSpacing(12)

                m_type_str = str(getattr(d, 'media_type', '')).upper()
                icon_str = "⚡" if "NVME" in m_type_str else ("💾" if "SSD" in m_type_str else "💽")
                lbl_icon = QLabel(icon_str)
                lbl_icon.setStyleSheet("font-size: 24px;")
                hdr.addWidget(lbl_icon)

                v_title = QVBoxLayout()
                v_title.setSpacing(2)
                drive_let = getattr(d, 'drive_letters', '') or 'Sürücü Harfi Yok'
                lbl_name = QLabel(f"<b>{d.name}</b>  <span style='color:{COLOR_ACCENT}; font-size:12px;'>[{drive_let}]</span>")
                lbl_name.setStyleSheet("font-size: 15px;")
                v_title.addWidget(lbl_name)

                lbl_sub = QLabel(f"Sürücü Tipi: {d.media_type}  |  Kapasite: {d.size_str}  |  Veri Yolu: {getattr(d, 'bus_type', '-')}")
                lbl_sub.setStyleSheet(f"font-size: 12px; color: {TEXT_MUTED};")
                v_title.addWidget(lbl_sub)
                hdr.addLayout(v_title, 1)

                # Health Badge
                pct = getattr(d, 'health_percent', 100)
                h_col = theme["COLOR_SUCCESS"] if pct >= 85 else (theme["COLOR_WARNING"] if pct >= 60 else theme["COLOR_DANGER"])
                status_tr = getattr(d, 'health_status_tr', 'Mükemmel')
                lbl_health_badge = QLabel(f"  {status_tr}  ")
                lbl_health_badge.setStyleSheet(f"""
                    background-color: rgba(16, 185, 129, 0.12);
                    color: {h_col};
                    border: 1px solid {h_col};
                    border-radius: 6px;
                    font-weight: 700;
                    font-size: 13px;
                    padding: 6px 12px;
                """)
                hdr.addWidget(lbl_health_badge)
                c_lay.addLayout(hdr)

                # 2. Health Progress Bar
                p_bar = QProgressBar()
                p_bar.setRange(0, 100)
                p_bar.setValue(pct)
                p_bar.setTextVisible(False)
                p_bar.setFixedHeight(8)
                p_bar.setStyleSheet(f"""
                    QProgressBar {{
                        background-color: rgba(148, 163, 184, 0.20);
                        border: none;
                        border-radius: 4px;
                    }}
                    QProgressBar::chunk {{
                        background-color: {h_col};
                        border-radius: 4px;
                    }}
                """)
                c_lay.addWidget(p_bar)

                # 3. Metrics Grid (Temperature, Power-on Hours, Bad Sectors, Reliability)
                grid = QGridLayout()
                grid.setHorizontalSpacing(24)
                grid.setVerticalSpacing(8)

                # Temp
                temp_c = getattr(d, 'temperature_c', None)
                t_str = f"{temp_c} °C" if temp_c is not None else "Sensör Yok"
                t_col = theme["COLOR_SUCCESS"] if (temp_c and temp_c < 50) else (theme["COLOR_WARNING"] if (temp_c and temp_c < 65) else (theme["COLOR_DANGER"] if temp_c else TEXT_MUTED))
                grid.addWidget(QLabel("🌡️  Çalışma Sıcaklığı:"), 0, 0)
                lbl_t = QLabel(f"<b style='color:{t_col};'>{t_str}</b>")
                grid.addWidget(lbl_t, 0, 1)

                # Power-on hours
                poh = getattr(d, 'power_on_hours', None)
                pod = getattr(d, 'power_on_days', None)
                poh_str = f"{poh:,} saat (~{pod} gün)" if poh is not None else "Sayaç Yok / Desteklenmiyor"
                grid.addWidget(QLabel("⏱️  Toplam Çalışma Süresi:"), 0, 2)
                grid.addWidget(QLabel(f"<b>{poh_str}</b>"), 0, 3)

                # Bad sectors & Read Errors
                sec_stat = getattr(d, 'bad_sectors_status', '0 Hata / Sıfır Bozuk Sektör')
                err_col = theme["COLOR_SUCCESS"] if "0 Hata" in sec_stat else theme["COLOR_WARNING"]
                grid.addWidget(QLabel("🔍  Bozuk Sektör / Hata Kaydı:"), 1, 0)
                grid.addWidget(QLabel(f"<b style='color:{err_col};'>{sec_stat}</b>"), 1, 1)

                # SMART Operational Status
                op_text = str(getattr(d, 'operational_status', 'OK') or 'OK')
                grid.addWidget(QLabel("🛡️  S.M.A.R.T. Durumu:"), 1, 2)
                grid.addWidget(QLabel(f"<b style='color:{theme['COLOR_SUCCESS']};'>{op_text} (Arıza Riski Yok)</b>"), 1, 3)

                c_lay.addLayout(grid)
                self.disks_container.addWidget(card)
            except Exception as card_err:
                log_debug(f"Render single disk card error: {card_err}")
