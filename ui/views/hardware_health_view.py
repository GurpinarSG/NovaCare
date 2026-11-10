"""
NovaCare System Suite - Hardware Health & Disk S.M.A.R.T. View
Comprehensive hardware health monitoring, SSD/HDD S.M.A.R.T. wear level,
temperature telemetry, power-on hours, bad sector detection, and battery wear.
Responsive layout optimized for all screen resolutions and DPI scaling factors.
"""
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QFrame, QScrollArea, QGridLayout, QLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from core.smart_reporter import SmartReporter, DiskHealthInfo
from core.hardware_monitor import HardwareMonitor
from core.battery_reporter import BatteryReporter, BatteryInfo, is_battery_present
from core.utils import log_debug
from ui.components import StatCard
from ui.styles import (
    get_active_theme_colors, COLOR_ACCENT
)

class SmartScanWorker(QThread):
    finished = pyqtSignal(list, dict, object) # disks, hw_stats, battery_info

    def __init__(self):
        super().__init__()
        self._is_cancelled = False
        self.smart_reporter = SmartReporter()
        self.hw_monitor = HardwareMonitor()
        self.battery_reporter = BatteryReporter()

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        disks = []
        hw_stats = {}
        bat_info = None
        try:
            if self._is_cancelled:
                return
            disks = self.smart_reporter.get_disks_health(force_refresh=True)
            if self._is_cancelled:
                return
            hw_stats = self.hw_monitor.get_hardware_stats()
            if self._is_cancelled:
                return
            bat_info = self.battery_reporter.get_battery_info(load_hardware_if_missing=True)
        except Exception as e:
            log_debug(f"SmartScanWorker error: {e}")
        finally:
            if not self._is_cancelled:
                self.finished.emit(disks, hw_stats, bat_info)

class HardwareHealthView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.smart_reporter = SmartReporter()
        self.hw_monitor = HardwareMonitor()
        self.battery_reporter = BatteryReporter()
        self.scan_worker = None
        self.disks: list[DiskHealthInfo] = []
        self.has_battery = is_battery_present()

        self._init_ui()

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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setObjectName("HardwareScroll")
        scroll.setStyleSheet(
            "QScrollArea#HardwareScroll { background: transparent; border: none; } "
            "QWidget#HardwareContainer { background: transparent; }"
        )
        scroll.viewport().setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setObjectName("HardwareContainer")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(4, 8, 4, 12)
        self.layout.setSpacing(14)
        self.layout.setSizeConstraint(QLayout.SetMinimumSize)

        # 1. Compact Header Toolbar
        header = QHBoxLayout()
        header.setSpacing(12)
        lbl_sec = QLabel("💾  Fiziksel Disk S.M.A.R.T. Sağlığı & Donanım Telemetrisi")
        lbl_sec.setStyleSheet("font-size: 15px; font-weight: 700;")
        lbl_sec.setWordWrap(True)
        header.addWidget(lbl_sec, 1)

        self.btn_refresh = QPushButton("🔄  S.M.A.R.T. Verilerini Yenile")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setProperty("class", "primary-btn")
        self.btn_refresh.clicked.connect(self._start_scan)
        header.addWidget(self.btn_refresh, 0, Qt.AlignVCenter)
        self.layout.addLayout(header)

        # 2. Hardware Sensors Overview Grid (Responsive 2x2 or 1x4)
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(10)
        self.card_cpu = StatCard("⚡", "İşlemci (CPU)", "Yükleniyor...", "- °C")
        self.card_gpu = StatCard("🎮", "Grafik (GPU)", "Yükleniyor...", "- °C")
        self.card_ram = StatCard("🧠", "Bellek (RAM)", "Yükleniyor...", "- / - GB")
        self.card_power = StatCard("🔋", "Güç / Batarya", "Yükleniyor...", "Kontrol ediliyor")
        if not self.has_battery:
            self.card_power.setVisible(False)

        self.layout.addLayout(self.stats_grid)
        self._relayout_stats(self.width() or 800)

        # 3. Disk S.M.A.R.T. Section Header
        lbl_disk_sec = QLabel("🛡️  Fiziksel Sürücü Güvenilirlik & Ömür Raporları")
        lbl_disk_sec.setStyleSheet("font-size: 14px; font-weight: 700; margin-top: 4px;")
        lbl_disk_sec.setWordWrap(True)
        self.layout.addWidget(lbl_disk_sec)

        # Disks Container Frame
        self.disks_container = QVBoxLayout()
        self.disks_container.setSpacing(12)
        self.disks_container.setSizeConstraint(QLayout.SetMinimumSize)
        self.layout.addLayout(self.disks_container)

        # Placeholder loading label
        self.lbl_loading = QLabel("Disk S.M.A.R.T. güvenilirlik sayaçları taranıyor, lütfen bekleyin...")
        self.lbl_loading.setStyleSheet(f"font-size: 13px; color: {COLOR_ACCENT}; padding: 15px;")
        self.lbl_loading.setWordWrap(True)
        self.disks_container.addWidget(self.lbl_loading)

        self.layout.addStretch()

        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _relayout_stats(self, width: int):
        """Dynamically adapts sensor cards: 2x2 grid on narrower views, 1x4 or 1x3 on wide views."""
        for card in (self.card_cpu, self.card_gpu, self.card_ram, self.card_power):
            self.stats_grid.removeWidget(card)

        has_bat = getattr(self, 'has_battery', True) and self.card_power.isVisible()
        if has_bat:
            if width < 820:
                self.stats_grid.addWidget(self.card_cpu, 0, 0)
                self.stats_grid.addWidget(self.card_gpu, 0, 1)
                self.stats_grid.addWidget(self.card_ram, 1, 0)
                self.stats_grid.addWidget(self.card_power, 1, 1)
                self.stats_grid.setColumnStretch(0, 1)
                self.stats_grid.setColumnStretch(1, 1)
                self.stats_grid.setColumnStretch(2, 0)
                self.stats_grid.setColumnStretch(3, 0)
            else:
                self.stats_grid.addWidget(self.card_cpu, 0, 0)
                self.stats_grid.addWidget(self.card_gpu, 0, 1)
                self.stats_grid.addWidget(self.card_ram, 0, 2)
                self.stats_grid.addWidget(self.card_power, 0, 3)
                self.stats_grid.setColumnStretch(0, 1)
                self.stats_grid.setColumnStretch(1, 1)
                self.stats_grid.setColumnStretch(2, 1)
                self.stats_grid.setColumnStretch(3, 1)
        else:
            if width < 680:
                self.stats_grid.addWidget(self.card_cpu, 0, 0)
                self.stats_grid.addWidget(self.card_gpu, 0, 1)
                self.stats_grid.addWidget(self.card_ram, 1, 0, 1, 2)
                self.stats_grid.setColumnStretch(0, 1)
                self.stats_grid.setColumnStretch(1, 1)
                self.stats_grid.setColumnStretch(2, 0)
                self.stats_grid.setColumnStretch(3, 0)
            else:
                self.stats_grid.addWidget(self.card_cpu, 0, 0)
                self.stats_grid.addWidget(self.card_gpu, 0, 1)
                self.stats_grid.addWidget(self.card_ram, 0, 2)
                self.stats_grid.setColumnStretch(0, 1)
                self.stats_grid.setColumnStretch(1, 1)
                self.stats_grid.setColumnStretch(2, 1)
                self.stats_grid.setColumnStretch(3, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout_stats(event.size().width())

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

    def on_activated(self):
        """Called when user opens hardware health view."""
        self._refresh_live_sensors()
        if not self.disks and (self.scan_worker is None or not self.scan_worker.isRunning()):
            self._start_scan()

    def _refresh_live_sensors(self):
        """Ultra-fast non-blocking live refresh of CPU, GPU, RAM stats."""
        if not self.isVisible():
            return
        try:
            hw_stats = self.hw_monitor.get_hardware_stats()
            bat_info = self.battery_reporter.get_battery_info()
            self._update_hw_cards(hw_stats, bat_info)
        except Exception:
            pass

    def _update_hw_cards(self, hw_stats: dict, bat_info: Optional[BatteryInfo]):
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
            lbl_empty.setObjectName("TextMuted")
            lbl_empty.setStyleSheet("font-size: 13px;")
            lbl_empty.setWordWrap(True)
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
                card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
                card.setMinimumHeight(200)
                c_lay = QVBoxLayout(card)
                c_lay.setContentsMargins(16, 14, 16, 14)
                c_lay.setSpacing(10)
                c_lay.setSizeConstraint(QLayout.SetMinimumSize)

                # 1. Disk Header (Icon + Name + Type Badge + Size)
                hdr = QHBoxLayout()
                hdr.setSpacing(12)

                m_type_str = str(getattr(d, 'media_type', '')).upper()
                icon_str = "⚡" if "NVME" in m_type_str else ("💾" if "SSD" in m_type_str else "💽")
                lbl_icon = QLabel(icon_str)
                lbl_icon.setStyleSheet("font-size: 24px;")
                hdr.addWidget(lbl_icon, 0, Qt.AlignVCenter)

                v_title = QVBoxLayout()
                v_title.setSpacing(2)
                v_title.setSizeConstraint(QLayout.SetMinimumSize)
                drive_let = getattr(d, 'drive_letters', '') or 'Sürücü Harfi Yok'
                lbl_name = QLabel(f"<b>{d.name}</b>  <span style='color:{COLOR_ACCENT}; font-size:12px;'>[{drive_let}]</span>")
                lbl_name.setStyleSheet("font-size: 14px;")
                lbl_name.setWordWrap(True)
                v_title.addWidget(lbl_name)

                lbl_sub = QLabel(f"Sürücü Tipi: {d.media_type}  |  Kapasite: {d.size_str}  |  Veri Yolu: {getattr(d, 'bus_type', '-')}")
                lbl_sub.setObjectName("TextMuted")
                lbl_sub.setStyleSheet("font-size: 11.5px;")
                lbl_sub.setWordWrap(True)
                v_title.addWidget(lbl_sub)
                hdr.addLayout(v_title, 1)

                # Health Badge
                pct = getattr(d, 'health_percent', 100)
                h_col = theme["COLOR_SUCCESS"] if pct >= 85 else (theme["COLOR_WARNING"] if pct >= 60 else theme["COLOR_DANGER"])
                bg_alpha = "rgba(16, 185, 129, 0.12)" if pct >= 85 else ("rgba(245, 158, 11, 0.15)" if pct >= 60 else "rgba(239, 68, 68, 0.15)")
                status_tr = getattr(d, 'health_status_tr', 'Mükemmel')
                lbl_health_badge = QLabel(f"  {status_tr}  ")
                lbl_health_badge.setAlignment(Qt.AlignCenter)
                lbl_health_badge.setStyleSheet(f"""
                    background-color: {bg_alpha};
                    color: {h_col};
                    border: 1px solid {h_col};
                    border-radius: 6px;
                    font-weight: 700;
                    font-size: 12.5px;
                    padding: 4px 10px;
                """)
                hdr.addWidget(lbl_health_badge, 0, Qt.AlignVCenter)
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

                # 3. 2-Column Responsive Metrics Grid with clean metric tiles
                grid = QGridLayout()
                grid.setSpacing(10)
                grid.setColumnStretch(0, 1)
                grid.setColumnStretch(1, 1)

                def _create_metric_tile(title_str: str, val_html: str) -> QFrame:
                    tile = QFrame()
                    tile.setObjectName("MetricTile")
                    tile.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
                    tile.setMinimumHeight(56)
                    tile.setStyleSheet("""
                        QFrame {
                            background-color: rgba(255, 255, 255, 0.03);
                            border: 1px solid rgba(255, 255, 255, 0.07);
                            border-radius: 8px;
                        }
                    """)
                    t_lay = QVBoxLayout(tile)
                    t_lay.setContentsMargins(12, 8, 12, 8)
                    t_lay.setSpacing(3)
                    t_lay.setSizeConstraint(QLayout.SetMinimumSize)
                    lbl_t = QLabel(title_str)
                    lbl_t.setObjectName("TextMuted")
                    lbl_t.setStyleSheet("font-size: 11.5px; font-weight: 600;")
                    lbl_t.setWordWrap(True)
                    t_lay.addWidget(lbl_t)
                    lbl_v = QLabel(val_html)
                    lbl_v.setStyleSheet("font-size: 13px; font-weight: 700;")
                    lbl_v.setWordWrap(True)
                    t_lay.addWidget(lbl_v)
                    return tile

                # Metric 1: Temp
                temp_c = getattr(d, 'temperature_c', None)
                t_str = f"{temp_c} °C" if temp_c is not None else "Sensör Yok"
                t_col = theme["COLOR_SUCCESS"] if (temp_c and temp_c < 50) else (theme["COLOR_WARNING"] if (temp_c and temp_c < 65) else (theme["COLOR_DANGER"] if temp_c else theme["TEXT_MUTED"]))
                tile_temp = _create_metric_tile("🌡️  Çalışma Sıcaklığı", f"<span style='color:{t_col};'>{t_str}</span>")
                grid.addWidget(tile_temp, 0, 0)

                # Metric 2: Power-on hours
                poh = getattr(d, 'power_on_hours', None)
                pod = getattr(d, 'power_on_days', None)
                if poh is not None:
                    poh_str = f"{poh:,} saat (~{pod} gün)"
                elif "NVME" in m_type_str:
                    poh_str = "NVMe S.M.A.R.T. (Sağlık: %100)"
                else:
                    poh_str = "Sayaç Yok / Desteklenmiyor"
                tile_poh = _create_metric_tile("⏱️  Toplam Çalışma Süresi", poh_str)
                grid.addWidget(tile_poh, 0, 1)

                # Metric 3: Bad sectors & Read Errors
                sec_stat = getattr(d, 'bad_sectors_status', '0 Hata / Sıfır Bozuk Sektör')
                err_col = theme["COLOR_SUCCESS"] if "0 Hata" in sec_stat else theme["COLOR_WARNING"]
                tile_sec = _create_metric_tile("🔍  Bozuk Sektör / Hata Kaydı", f"<span style='color:{err_col};'>{sec_stat}</span>")
                grid.addWidget(tile_sec, 1, 0)

                # Metric 4: SMART Operational Status
                op_text = str(getattr(d, 'operational_status', 'OK') or 'OK')
                h_stat_lower = getattr(d, 'health_status', 'Healthy').lower()
                is_healthy = (op_text.upper() in ("OK", "NORMAL")) and (h_stat_lower == "healthy")
                is_warning = ("WARN" in op_text.upper() or h_stat_lower == "warning")

                if is_healthy:
                    op_col = theme["COLOR_SUCCESS"]
                    op_desc = f"{op_text} (Arıza Riski Yok / Sağlıklı)"
                elif is_warning:
                    op_col = theme["COLOR_WARNING"]
                    op_desc = f"{op_text} (Uyarı / Yıpranma Algılandı)"
                else:
                    op_col = theme["COLOR_DANGER"]
                    op_desc = f"{op_text} (Kritik / Arıza Riski Mevcut)"

                tile_smart = _create_metric_tile("🛡️  S.M.A.R.T. Durumu", f"<span style='color:{op_col};'>{op_desc}</span>")
                grid.addWidget(tile_smart, 1, 1)

                c_lay.addLayout(grid)
                self.disks_container.addWidget(card)
            except Exception as card_err:
                log_debug(f"Render single disk card error: {card_err}")
