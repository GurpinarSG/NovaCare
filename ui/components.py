"""
NovaCare System Suite - Custom High-Performance UI Components
Includes Circular Health Gauge, Stat Cards, and Styled Category Items.
Theme-aware dynamic rendering with seamless dark/light contrast support.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt, QRectF, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from ui.styles import get_active_theme_colors

class CircularHealthGauge(QWidget):
    """
    Circular Health Gauge widget indicating system health score (0 to 100).
    Smooth animated rendering with dynamic color grading and theme-aware contrast.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 100
        self._display_score = 100
        self.status_text = "Mükemmel"
        self.setFixedSize(220, 205)

    @pyqtProperty(int)
    def score(self):
        return self._score

    @score.setter
    def score(self, val: int):
        self._score = max(0, min(100, val))
        self._update_status_text()
        self.update()

    def _update_status_text(self):
        if self._score >= 85:
            self.status_text = "Mükemmel"
        elif self._score >= 65:
            self.status_text = "İyi"
        elif self._score >= 40:
            self.status_text = "Bakım Önerilir"
        else:
            self.status_text = "Kritik"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        p = get_active_theme_colors()

        width = self.width()
        height = self.height()
        size = min(width, height) - 24

        center_x = width / 2.0
        center_y = (height - 8) / 2.0
        rect = QRectF(center_x - size / 2.0, center_y - size / 2.0, size, size)

        # 1. Background Track Arc (270 degrees sweep starting from 135 deg)
        pen_bg = QPen(QColor(p["GAUGE_TRACK"]), 14, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, int(225 * 16), int(-270 * 16))

        # 2. Foreground Score Arc
        if self._score >= 85:
            arc_color = QColor(p["COLOR_SUCCESS"])
        elif self._score >= 60:
            arc_color = QColor(p["COLOR_WARNING"])
        else:
            arc_color = QColor(p["COLOR_DANGER"])

        pen_fg = QPen(arc_color, 14, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_fg)
        sweep_angle = int(-(self._score / 100.0) * 270.0 * 16)
        painter.drawArc(rect, int(225 * 16), sweep_angle)

        # 3. Text in Center
        painter.setPen(QColor(p["TEXT_PRIMARY"]))
        font_score = QFont("Segoe UI", 36, QFont.Bold)
        painter.setFont(font_score)
        painter.drawText(
            QRectF(0, center_y - 48, width, 50),
            Qt.AlignCenter,
            f"{self._score}"
        )

        font_unit = QFont("Segoe UI", 9, QFont.Bold)
        font_unit.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        painter.setFont(font_unit)
        painter.setPen(QColor(p["TEXT_MUTED"]))
        painter.drawText(
            QRectF(0, center_y + 4, width, 18),
            Qt.AlignCenter,
            "SAĞLIK SKORU"
        )

        # Normalize status text to prevent any overflow
        display_status = self.status_text
        for prefix in ("Sistem Durumu: ", "Sistem Durumu:", "İstek Durumu: ", "İstek Durumu:", "Durum: ", "Durum:"):
            if display_status.startswith(prefix):
                display_status = display_status[len(prefix):].strip()
                break

        # Dynamically scale font so text NEVER collides with or overflows the arc
        status_pt = 11
        font_status = QFont("Segoe UI", status_pt, QFont.Bold)
        fm = QFontMetrics(font_status)
        max_allowed_w = size - 64  # safe inner chord width
        while status_pt > 8 and fm.horizontalAdvance(display_status) > max_allowed_w:
            status_pt -= 1
            font_status.setPointSize(status_pt)
            fm = QFontMetrics(font_status)

        painter.setFont(font_status)
        painter.setPen(arc_color)
        painter.drawText(
            QRectF(0, center_y + 24, width, 22),
            Qt.AlignCenter,
            display_status
        )

class StatCard(QFrame):
    """Modern rounded statistic card with icon, metric, and subtitle."""
    def __init__(self, icon: str, title: str, initial_value: str = "-", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setMinimumHeight(108)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        p = get_active_theme_colors()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 20px;")
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("StatTitle")
        top_row.addWidget(self.icon_lbl)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.value_lbl = QLabel(initial_value)
        self.value_lbl.setObjectName("StatValue")
        layout.addWidget(self.value_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setObjectName("StatSub")
        self.sub_lbl.setWordWrap(True)
        layout.addWidget(self.sub_lbl)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_lbl.setText(value)
        if subtitle:
            self.sub_lbl.setText(subtitle)

class HardwareOverlayWidget(QWidget):
    """
    Floating desktop mini hardware & temperature widget.
    Draggable, semi-transparent, stays on top, displays real-time CPU, GPU, and RAM stats.
    """
    def __init__(self, parent=None):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.drag_position = None
        self.setFixedSize(220, 160)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Card container
        self.card = QFrame(self)
        self.card.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.94);
                border: 1px solid #38BDF8;
                border-radius: 12px;
            }
            QLabel {
                color: #FFFFFF;
                background: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 8, 12, 10)
        card_layout.setSpacing(6)

        # Header with drag handle & close button
        hdr = QHBoxLayout()
        hdr.setSpacing(4)
        lbl_title = QLabel("⚡ NovaCare Monitör")
        lbl_title.setStyleSheet("font-weight: 700; font-size: 11px; color: #38BDF8;")
        hdr.addWidget(lbl_title)
        hdr.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94A3B8;
                border: none;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #EF4444;
            }
        """)
        btn_close.clicked.connect(self.hide)
        hdr.addWidget(btn_close)
        card_layout.addLayout(hdr)

        # Stats Rows
        self.lbl_cpu = QLabel("CPU: %0  (0.0 GHz)")
        self.lbl_cpu.setStyleSheet("font-size: 11px; font-weight: 600; color: #F8FAFC;")
        card_layout.addWidget(self.lbl_cpu)

        self.lbl_cpu_temp = QLabel("CPU Sıcaklık: - °C")
        self.lbl_cpu_temp.setStyleSheet("font-size: 10px; color: #CBD5E1;")
        card_layout.addWidget(self.lbl_cpu_temp)

        self.lbl_gpu = QLabel("GPU: %0  (- °C)")
        self.lbl_gpu.setStyleSheet("font-size: 11px; font-weight: 600; color: #34D399;")
        card_layout.addWidget(self.lbl_gpu)

        self.lbl_ram = QLabel("RAM: %0  (0.0 / 0.0 GB)")
        self.lbl_ram.setStyleSheet("font-size: 11px; font-weight: 600; color: #A78BFA;")
        card_layout.addWidget(self.lbl_ram)

        root.addWidget(self.card)

    def update_stats(self, stats: dict):
        cpu_pct = stats.get("cpu_percent", 0)
        cpu_freq = stats.get("cpu_freq_ghz", 0.0)
        cpu_temp = stats.get("cpu_temp")
        gpu_load = stats.get("gpu_load", 0)
        gpu_temp = stats.get("gpu_temp")
        ram_pct = stats.get("ram_percent", 0)
        ram_used = stats.get("ram_used_gb", 0)
        ram_total = stats.get("ram_total_gb", 0)

        self.lbl_cpu.setText(f"CPU: %{cpu_pct:.0f}  ({cpu_freq:.1f} GHz)")
        if cpu_temp is not None:
            c_color = "#EF4444" if cpu_temp > 75 else ("#FBBF24" if cpu_temp > 60 else "#34D399")
            self.lbl_cpu_temp.setText(f"CPU Sıcaklık: <b style='color:{c_color};'>{cpu_temp:.1f} °C</b>")
        else:
            self.lbl_cpu_temp.setText("CPU Sıcaklık: Ölçülüyor...")

        if stats.get("has_gpu", False):
            g_temp_str = f"{gpu_temp} °C" if gpu_temp is not None else "N/A"
            self.lbl_gpu.setText(f"GPU: %{gpu_load}  ({g_temp_str})")
        else:
            self.lbl_gpu.setText("GPU: Harici GPU Yok")

        self.lbl_ram.setText(f"RAM: %{ram_pct:.0f}  ({ram_used} / {ram_total} GB)")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

