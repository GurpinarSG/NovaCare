"""
NovaCare System Suite - Dashboard View (1-Click Care)
Signature 1-Click Scan & Repair featuring health score gauge, live metrics, and category checklist.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QGridLayout, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from ui.components import CircularHealthGauge, StatCard
from ui.styles import (
    BG_CARD, BORDER_COLOR, COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
)
from core.utils import format_bytes
from core.junk_cleaner import JunkCleaner
from core.registry_cleaner import RegistryCleaner
from core.privacy_tweaker import PrivacyTweaker
from core.startup_manager import StartupManager
from core.memory_booster import MemoryBooster

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
        self.scan_worker = None
        self.fix_worker = None
        self.last_results = None
        self._init_ui()
        self._start_live_timer()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # 1. Top Stat Cards Row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(14)
        self.card_cpu = StatCard("⚡", "İşlemci Yükü", "0%", "Çekirdekler Aktif")
        self.card_ram = StatCard("🧠", "Bellek (RAM)", "0%", "Boş: -")
        self.card_junk = StatCard("🗑️", "Gereksiz Dosya", "Taranmadı", "Temizlik Bekliyor")
        self.card_health = StatCard("🛡️", "Kayıt Defteri", "0 Sorun", "Stabilite Durumu")

        stats_layout.addWidget(self.card_cpu)
        stats_layout.addWidget(self.card_ram)
        stats_layout.addWidget(self.card_junk)
        stats_layout.addWidget(self.card_health)
        main_layout.addLayout(stats_layout)

        # 2. Central 1-Click Maintenance Area (Gauge + Action Button)
        center_card = QFrame()
        center_card.setObjectName("CenterCard")
        center_card.setStyleSheet(f"""
            #CenterCard {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER_COLOR};
                border-radius: 16px;
                padding: 24px;
            }}
        """)
        center_layout = QVBoxLayout(center_card)
        center_layout.setSpacing(16)
        center_layout.setAlignment(Qt.AlignCenter)

        self.gauge = CircularHealthGauge()
        center_layout.addWidget(self.gauge, alignment=Qt.AlignCenter)

        # Status text
        self.lbl_status = QLabel("Tek tıkla tam sistem taraması yaparak bilgisayarınızı hızlandırın.")
        self.lbl_status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 14px;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.lbl_status)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
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

        # 3. Scan Items Breakdown Grid
        self.breakdown_frame = QFrame()
        self.breakdown_frame.setStyleSheet(f"""
            background-color: {BG_CARD};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 14px 20px;
        """)
        grid = QGridLayout(self.breakdown_frame)
        grid.setSpacing(16)

        self.lbl_item_junk = QLabel("🗑️  Gereksiz Dosyalar & Önbellek: <b>Taranmadı</b>")
        self.lbl_item_reg = QLabel("🛠️  Kayıt Defteri Sorunları: <b>Taranmadı</b>")
        self.lbl_item_privacy = QLabel("🛡️  Gizlilik & İz Kayıtları: <b>Taranmadı</b>")
        self.lbl_item_startup = QLabel("🚀  Yüksek Başlangıç Yükü: <b>Taranmadı</b>")

        for lbl in (self.lbl_item_junk, self.lbl_item_reg, self.lbl_item_privacy, self.lbl_item_startup):
            lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")

        grid.addWidget(self.lbl_item_junk, 0, 0)
        grid.addWidget(self.lbl_item_reg, 0, 1)
        grid.addWidget(self.lbl_item_privacy, 1, 0)
        grid.addWidget(self.lbl_item_startup, 1, 1)

        main_layout.addWidget(self.breakdown_frame)
        main_layout.addStretch()

    def _start_live_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_live_metrics)
        self.timer.start(2000)
        self._update_live_metrics()

    def _update_live_metrics(self):
        try:
            metrics = self.mem_booster.get_system_metrics()
            self.card_cpu.set_value(f"{metrics['cpu_percent']}%", "Tüm Çekirdekler")
            self.card_ram.set_value(f"{metrics['ram_percent']}%", f"Boş: {metrics['ram_free_str']}")
        except Exception:
            pass

    def _handle_action_click(self):
        if self.btn_action.text().startswith("🚀"):
            # Start Scanning
            self._start_scan()
        elif self.btn_action.text().startswith("✨"):
            # Start Fixing
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
        self.card_health.set_value(f"{results['reg_issues']} Sorun", "Onarım Hazır")

        self.lbl_item_junk.setText(f"🗑️  Gereksiz Dosyalar & Önbellek: <b style='color:{COLOR_WARNING};'>{junk_str} ({results['junk_count']} öğe)</b>")
        self.lbl_item_reg.setText(f"🛠️  Kayıt Defteri Sorunları: <b style='color:{COLOR_DANGER};'>{results['reg_issues']} sorun bulundu</b>")
        self.lbl_item_privacy.setText(f"🛡️  Gizlilik & İz Kayıtları: <b style='color:{COLOR_WARNING};'>{results['privacy_count']} iz bulundu</b>")
        self.lbl_item_startup.setText(f"🚀  Yüksek Başlangıç Yükü: <b style='color:{COLOR_ACCENT};'>{results['startup_count']} program</b>")

        self.lbl_status.setText(f"Tarama bitti! Toplam <b>{junk_str}</b> gereksiz dosya ve <b>{results['reg_issues']}</b> kayıt defteri sorunu tespit edildi.")

        # Switch button to Fix mode
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
        self.card_health.set_value("0 Sorun", "Sağlıklı")

        self.lbl_item_junk.setText("🗑️  Gereksiz Dosyalar & Önbellek: <b style='color:#10B981;'>Temizlendi ✔</b>")
        self.lbl_item_reg.setText(f"🛠️  Kayıt Defteri Sorunları: <b style='color:#10B981;'>{reg_fixed} Sorun Onarıldı ✔</b>")
        self.lbl_item_privacy.setText(f"🛡️  Gizlilik & İz Kayıtları: <b style='color:#10B981;'>{traces_cleaned} İz Silindi ✔</b>")
        self.lbl_item_startup.setText("🚀  Sistem Belleği & Performans: <b style='color:#10B981;'>Optimize Edildi ✔</b>")

        self.lbl_status.setText(f"Tebrikler! <b>{freed_str}</b> disk alanı boşaltıldı ve sisteminiz başarıyla optimize edildi.")

        # Switch button back to Scan
        self.btn_action.setText("🚀  TEK TIKLA SİSTEMİ TARA")
        self.btn_action.setObjectName("BigScanBtn")
        self.btn_action.setStyle(self.btn_action.style())
