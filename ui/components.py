"""
NovaCare System Suite - Custom High-Performance UI Components
Includes Circular Health Gauge, Stat Cards, and Styled Category Items.
Theme-aware dynamic rendering with seamless dark/light contrast support.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt, QRectF, pyqtProperty, pyqtSignal
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

from ui.desktop_widget import DesktopPerformanceWidget

# Backward compatibility alias
HardwareOverlayWidget = DesktopPerformanceWidget


