"""
NovaCare System Suite - Dashboard View (1-Click Care & Performance)
Signature 1-Click Scan & Repair, Game & Ultimate Performance Booster,
Real-Time CPU/GPU Hardware & Temperature Telemetry, and Desktop Overlay.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QGridLayout, QFrame, QScrollArea, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from ui.components import CircularHealthGauge, StatCard, HardwareOverlayWidget
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.utils import format_bytes, is_admin
from core.junk_cleaner import JunkCleaner
from core.registry_cleaner import RegistryCleaner
from core.privacy_tweaker import PrivacyTweaker
from core.startup_manager import StartupManager
from core.memory_booster import MemoryBooster
from core.game_booster import GameBooster
from core.hardware_monitor import HardwareMonitor

class DashboardScanWorker(QThread):
    progress = pyqtSignal(str, int)  # status_message, percent
    finished = pyqtSignal(dict)      # scan results

    def __init__(self):
        super().__init__()
        self.junk_cleaner = JunkCleaner()
        self.reg_cleaner = RegistryCleaner()
        self.privacy_tweaker = PrivacyTweaker()
        self.startup_mgr = StartupManager()

    def run(self):
        results = {
            "junk_size": 0,
            "junk_count": 0,
            "reg_issues": 0,
            "privacy_count": 0,
            "startup_count": 0,
            "score": 100
        }

        # 1. Junk files scan
        self.progress.emit("Gereksiz dosyalar ve önbellekler taranıyor...", 15)
        cats = self.junk_cleaner.scan_all()
        total_junk = sum(c.size for c in cats)
        total_junk_files = sum(c.file_count for c in cats)
        results["junk_size"] = total_junk
        results["junk_count"] = total_junk_files

        # 2. Registry scan
        self.progress.emit("Kayıt Defteri sorunları denetleniyor...", 45)
        reg_issues = self.reg_cleaner.scan_all()
        results["reg_issues"] = len(reg_issues)

        # 3. Privacy traces scan
        self.progress.emit("Gizlilik izleri ve geçmiş denetleniyor...", 75)
        traces = self.privacy_tweaker.scan_privacy_traces()
        results["privacy_count"] = sum(t.count for t in traces)

        # 4. Startup apps scan
        self.progress.emit("Başlangıç programları analiz ediliyor...", 90)
        startups = self.startup_mgr.scan_all()
        high_impact = len([s for s in startups if s.boot_impact == "Yüksek" and s.enabled])
        results["startup_count"] = high_impact

        # Calculate Health Score
        score = 100
        if total_junk > 1024 * 1024 * 1024:  # > 1GB
            score -= 25
        elif total_junk > 200 * 1024 * 1024: # > 200MB
            score -= 15
        elif total_junk > 50 * 1024 * 1024:
            score -= 8

        if len(reg_issues) > 50:
            score -= 25
        elif len(reg_issues) > 10:
            score -= 15
        elif len(reg_issues) > 0:
            score -= 5

        if results["privacy_count"] > 100:
            score -= 15
        elif results["privacy_count"] > 20:
            score -= 10

        if high_impact > 3:
            score -= 15

        results["score"] = max(15, score)
        self.progress.emit("Tarama tamamlandı!", 100)
        self.finished.emit(results)

class DashboardFixWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(int, int, int) # freed_bytes, reg_fixed, traces_cleaned

    def run(self):
        self.progress.emit("Gereksiz dosyalar temizleniyor...", 20)
        junk_cleaner = JunkCleaner()
        cats = junk_cleaner.scan_all()
        freed_bytes, _, _ = junk_cleaner.clean_categories({c.id for c in cats})

        self.progress.emit("Kayıt defteri sorunları güvenle onarılıyor...", 60)
        reg_cleaner = RegistryCleaner()
        issues = reg_cleaner.scan_all()
        reg_fixed, _, _ = reg_cleaner.fix_issues(issues)

        self.progress.emit("Gizlilik izleri temizleniyor...", 85)
        privacy = PrivacyTweaker()
        traces = privacy.scan_privacy_traces()
        traces_cleaned = privacy.clean_privacy_traces({t.id for t in traces})

        # Memory boost
        mem = MemoryBooster()
        mem.optimize_ram()

        self.progress.emit("Onarım başarıyla tamamlandı!", 100)
        self.finished.emit(freed_bytes, reg_fixed, traces_cleaned)

class DashboardView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mem_booster = MemoryBooster()
        self.game_booster = GameBooster()
        self.hw_monitor = HardwareMonitor()
        self.overlay_widget = HardwareOverlayWidget()
        
        self.scan_worker = None
        self.fix_worker = None
        self.last_results = None
        self._init_ui()
        self._start_live_timer()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Smooth, transparent scroll container for responsive adaptability
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background-color: transparent; background: transparent; border: none;")
        scroll.viewport().setStyleSheet("background-color: transparent; background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background-color: transparent; background: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 16, 24, 16)
        main_layout.setSpacing(14)

        # 1. Top Stat Cards Row (Live CPU, GPU, RAM, Junk)
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        self.card_cpu = StatCard("⚡", "İşlemci (CPU)", "0%", "0.0 GHz | - °C")
        self.card_gpu = StatCard("🎮", "Grafik (GPU)", "0%", "- °C | Yükleniyor...")
        self.card_ram = StatCard("🧠", "Bellek (RAM)", "0%", "0.0 / 0.0 GB")
        self.card_junk = StatCard("🗑️", "Gereksiz Dosya", "Taranmadı", "Temizlik Bekliyor")

        stats_layout.addWidget(self.card_cpu)
        stats_layout.addWidget(self.card_gpu)
        stats_layout.addWidget(self.card_ram)
        stats_layout.addWidget(self.card_junk)
        main_layout.addLayout(stats_layout)

        # 2. Game Mode & Ultimate Performance Banner Card
        game_card = QFrame()
        game_card.setObjectName("CardFrame")
        g_layout = QHBoxLayout(game_card)
        g_layout.setContentsMargins(18, 12, 18, 12)
        g_layout.setSpacing(14)

        g_icon = QLabel("🎮")
        g_icon.setStyleSheet("font-size: 26px;")
        g_layout.addWidget(g_icon)

        v_gtext = QVBoxLayout()
        v_gtext.setSpacing(2)
        lbl_g_title = QLabel("Oyun & Nihai Performans Modu")
        lbl_g_title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLOR_ACCENT};")
        self.lbl_g_sub = QLabel("Arka plan gereksiz servislerini durdurur ve güç planını 'Nihai Performans' moduna alır.")
        self.lbl_g_sub.setStyleSheet(f"font-size: 11px; color: {TEXT_SECONDARY};")
        self.lbl_g_sub.setWordWrap(True)
        v_gtext.addWidget(lbl_g_title)
        v_gtext.addWidget(self.lbl_g_sub)
        g_layout.addLayout(v_gtext)

        g_layout.addStretch()

        # Desktop Overlay Button
        self.btn_overlay = QPushButton("📌  Masaüstü Widget'ı")
        self.btn_overlay.setCursor(Qt.PointingHandCursor)
        self.btn_overlay.setProperty("class", "secondary-btn")
        self.btn_overlay.clicked.connect(self._toggle_overlay)
        g_layout.addWidget(self.btn_overlay)

        # Game Mode Toggle Button
        self.btn_game_mode = QPushButton("🎮  Oyun Modunu Başlat")
        self.btn_game_mode.setCursor(Qt.PointingHandCursor)
        self.btn_game_mode.setStyleSheet("padding: 8px 18px; font-size: 12px; font-weight: 700; background-color: #059669; color: #FFFFFF; border-radius: 6px;")
        self.btn_game_mode.clicked.connect(self._toggle_game_mode)
        g_layout.addWidget(self.btn_game_mode)

        main_layout.addWidget(game_card)
        self._sync_game_mode_ui()

        # 3. Central 1-Click Maintenance Area (Gauge + Action Button)
        center_card = QFrame()
        center_card.setObjectName("CenterCard")
        center_layout = QVBoxLayout(center_card)
        center_layout.setContentsMargins(20, 14, 20, 14)
        center_layout.setSpacing(10)
        center_layout.setAlignment(Qt.AlignCenter)

        self.gauge = CircularHealthGauge()
        center_layout.addWidget(self.gauge, alignment=Qt.AlignCenter)

        # Status text
        self.lbl_status = QLabel("Tek tıkla tam sistem taraması yaparak bilgisayarınızı hızlandırın.")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setWordWrap(True)
        center_layout.addWidget(self.lbl_status)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10)
        center_layout.addWidget(self.progress_bar)

        # Big Button (Scan / Fix)
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        self.btn_action = QPushButton("🚀  TEK TIKLA SİSTEMİ TARA")
        self.btn_action.setObjectName("BigScanBtn")
        self.btn_action.setCursor(Qt.PointingHandCursor)
        self.btn_action.clicked.connect(self._handle_action_click)
        btn_layout.addWidget(self.btn_action)
        center_layout.addLayout(btn_layout)

        main_layout.addWidget(center_card)

        # 4. Scan Items Breakdown Grid
        self.breakdown_frame = QFrame()
        self.breakdown_frame.setObjectName("CardFrame")
        grid = QGridLayout(self.breakdown_frame)
        grid.setContentsMargins(18, 12, 18, 12)
        grid.setSpacing(12)

        self.lbl_item_junk = QLabel("🗑️  Gereksiz Dosyalar & Önbellek: <b>Taranmadı</b>")
        self.lbl_item_reg = QLabel("🛠️  Kayıt Defteri Sorunları: <b>Taranmadı</b>")
        self.lbl_item_privacy = QLabel("🛡️  Gizlilik & İz Kayıtları: <b>Taranmadı</b>")
        self.lbl_item_startup = QLabel("🚀  Yüksek Başlangıç Yükü: <b>Taranmadı</b>")

        for lbl in (self.lbl_item_junk, self.lbl_item_reg, self.lbl_item_privacy, self.lbl_item_startup):
            lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            lbl.setWordWrap(True)

        grid.addWidget(self.lbl_item_junk, 0, 0)
        grid.addWidget(self.lbl_item_reg, 0, 1)
        grid.addWidget(self.lbl_item_privacy, 1, 0)
        grid.addWidget(self.lbl_item_startup, 1, 1)

        main_layout.addWidget(self.breakdown_frame)

        # Admin cleaning depth hint
        has_admin = is_admin()
        self.lbl_admin_depth_hint = QLabel(
            "🛡️ <b>Yönetici Modu Devrede:</b> Korumalı sistem önbellekleri, derin kayıt defteri anahtarları ve RAM çalışma kümeleri tam yetkiyle temizlenir."
            if has_admin else
            "💡 <b>Daha İyi Temizlik İpucu:</b> NovaCare'i Yönetici olarak çalıştırdığınızda Windows kilitli sistem dosyaları ve derin kayıt defteri kalıntıları çok daha iyi temizlenir."
        )
        self.lbl_admin_depth_hint.setAlignment(Qt.AlignCenter)
        self.lbl_admin_depth_hint.setStyleSheet(f"color: {COLOR_SUCCESS if has_admin else COLOR_ACCENT}; font-size: 12px; padding: 4px;")
        self.lbl_admin_depth_hint.setWordWrap(True)
        main_layout.addWidget(self.lbl_admin_depth_hint)

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _sync_game_mode_ui(self):
        if self.game_booster.is_active():
            self.btn_game_mode.setText("↩️  Normale Döndür")
            self.btn_game_mode.setStyleSheet("padding: 8px 18px; font-size: 12px; font-weight: 700; background-color: #D97706; color: #FFFFFF; border-radius: 6px;")
            self.lbl_g_sub.setText("Oyun Modu AKTİF: Nihai Performans Güç Planı etkin, arka plan servisleri durduruldu.")
        else:
            self.btn_game_mode.setText("🎮  Oyun Modunu Başlat")
            self.btn_game_mode.setStyleSheet("padding: 8px 18px; font-size: 12px; font-weight: 700; background-color: #059669; color: #FFFFFF; border-radius: 6px;")
            self.lbl_g_sub.setText("Arka plan gereksiz servislerini durdurur ve güç planını 'Nihai Performans' moduna alır.")

    def _toggle_game_mode(self):
        if not self.game_booster.is_active():
            state = self.game_booster.activate()
            freed_str = format_bytes(state.get("freed_ram_bytes", 0))
            stopped_cnt = len(state.get("stopped_services", []))
            QMessageBox.information(
                self,
                "Oyun Modu Etkinleştirildi",
                f"Nihai Performans Güç Planı başarıyla devreye alındı!\n\n"
                f"• {stopped_cnt} adet arka plan servisi geçici olarak durduruldu.\n"
                f"• {freed_str} RAM oyunlar için hazır hale getirildi.\n\n"
                "Oyununuz bittiğinde aynı butona basarak servisleri ve önceki güç planınızı tek tıkla geri yükleyebilirsiniz."
            )
        else:
            state = self.game_booster.deactivate()
            restarted_cnt = state.get("restored_services", 0)
            prev_name = state.get("previous_power_name", "Standart")
            QMessageBox.information(
                self,
                "Normal Moda Dönüldü",
                f"Sistem ayarları geri yüklendi!\n\n"
                f"• Güç Planı: {prev_name}\n"
                f"• {restarted_cnt} adet servis yeniden başlatıldı."
            )
        self._sync_game_mode_ui()

    def _toggle_overlay(self):
        if self.overlay_widget.isVisible():
            self.overlay_widget.hide()
            self.btn_overlay.setText("📌  Masaüstü Widget'ı")
        else:
            self.overlay_widget.show()
            self.overlay_widget.raise_()
            self.btn_overlay.setText("📌  Widget'ı Kapat")

    def _start_live_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_live_metrics)
        self.timer.start(2500)
        self._update_live_metrics()

    def _update_live_metrics(self):
        # Update metrics when Dashboard or Overlay is visible
        if not self.isVisible() and not self.overlay_widget.isVisible():
            return

        try:
            stats = self.hw_monitor.get_hardware_stats()

            # Update Overlay if open
            if self.overlay_widget.isVisible():
                self.overlay_widget.update_stats(stats)

            # Update StatCards
            if self.isVisible():
                c_temp = f" | {stats['cpu_temp']} °C" if stats.get("cpu_temp") else ""
                self.card_cpu.set_value(f"{stats['cpu_percent']:.0f}%", f"{stats['cpu_freq_ghz']} GHz{c_temp}")

                if stats.get("has_gpu", False):
                    g_temp = f"{stats['gpu_temp']} °C" if stats.get("gpu_temp") is not None else ""
                    self.card_gpu.set_value(f"{stats['gpu_load']}%", f"{g_temp} | VRAM: {stats['gpu_mem_used_mb']} MB")
                else:
                    self.card_gpu.set_value("Yok", "Harici GPU Yok")

                self.card_ram.set_value(f"{stats['ram_percent']:.0f}%", f"{stats['ram_used_gb']} / {stats['ram_total_gb']} GB")
        except Exception:
            pass

    def _handle_action_click(self):
        if self.btn_action.text().startswith("🚀"):
            self._start_scan()
        elif self.btn_action.text().startswith("✨"):
            self._start_fix()

    def _start_scan(self):
        self.btn_action.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Sistem derinlemesine taranıyor, lütfen bekleyin...")

        self.scan_worker = DashboardScanWorker()
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.start()

    def _on_scan_progress(self, msg: str, pct: int):
        self.lbl_status.setText(msg)
        self.progress_bar.setValue(pct)

    def _on_scan_finished(self, results: dict):
        self.last_results = results
        self.progress_bar.setVisible(False)
        self.btn_action.setEnabled(True)

        self.gauge.score = results["score"]
        junk_str = format_bytes(results["junk_size"])

        self.card_junk.set_value(junk_str, f"{results['junk_count']} dosya")

        self.lbl_item_junk.setText(f"🗑️  Gereksiz Dosyalar & Önbellek: <b style='color:{COLOR_WARNING};'>{junk_str} ({results['junk_count']} öğe)</b>")
        self.lbl_item_reg.setText(f"🛠️  Kayıt Defteri Sorunları: <b style='color:{COLOR_DANGER};'>{results['reg_issues']} sorun bulundu</b>")
        self.lbl_item_privacy.setText(f"🛡️  Gizlilik & İz Kayıtları: <b style='color:{COLOR_WARNING};'>{results['privacy_count']} iz bulundu</b>")
        self.lbl_item_startup.setText(f"🚀  Yüksek Başlangıç Yükü: <b style='color:{COLOR_ACCENT};'>{results['startup_count']} program</b>")

        self.lbl_status.setText(f"Tarama bitti! Toplam <b>{junk_str}</b> gereksiz dosya ve <b>{results['reg_issues']}</b> kayıt defteri sorunu tespit edildi.")

        self.btn_action.setText("✨  ŞİMDİ SİSTEMİ ONAR VE HIZLANDIR")
        self.btn_action.setObjectName("BigFixBtn")
        self.btn_action.setStyle(self.btn_action.style())

    def _start_fix(self):
        self.btn_action.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Sistem temizleniyor ve onarılıyor...")

        self.fix_worker = DashboardFixWorker()
        self.fix_worker.progress.connect(self._on_scan_progress)
        self.fix_worker.finished.connect(self._on_fix_finished)
        self.fix_worker.start()

    def _on_fix_finished(self, freed_bytes: int, reg_fixed: int, traces_cleaned: int):
        self.progress_bar.setVisible(False)
        self.btn_action.setEnabled(True)
        self.gauge.score = 100

        freed_str = format_bytes(freed_bytes)
        self.card_junk.set_value("0 B", "Temizlendi")

        self.lbl_item_junk.setText("🗑️  Gereksiz Dosyalar & Önbellek: <b style='color:#10B981;'>Temizlendi ✔</b>")
        self.lbl_item_reg.setText(f"🛠️  Kayıt Defteri Sorunları: <b style='color:#10B981;'>{reg_fixed} Sorun Onarıldı ✔</b>")
        self.lbl_item_privacy.setText(f"🛡️  Gizlilik & İz Kayıtları: <b style='color:#10B981;'>{traces_cleaned} İz Silindi ✔</b>")
        self.lbl_item_startup.setText("🚀  Sistem Belleği & Performans: <b style='color:#10B981;'>Optimize Edildi ✔</b>")

        has_admin = is_admin()
        admin_note = (
            " (🛡️ Yönetici Modu: Tam sistem derinliğinde onarıldı)"
            if has_admin else
            " (💡 Daha derin sistem temizliği için Yönetici Modu önerilir)"
        )
        self.lbl_status.setText(f"Tebrikler! <b>{freed_str}</b> disk alanı boşaltıldı ve sisteminiz optimize edildi.{admin_note}")

        self.btn_action.setText("🚀  TEK TIKLA SİSTEMİ TARA")
        self.btn_action.setObjectName("BigScanBtn")
        self.btn_action.setStyle(self.btn_action.style())
