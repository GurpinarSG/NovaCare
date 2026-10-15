"""
NovaCare System Suite - Custom High-Performance UI Components
Includes Circular Health Gauge, Stat Cards, and Styled Category Items.
Theme-aware dynamic rendering with seamless dark/light contrast support.
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QRectF, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
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
        self.status_text = "Sistem Durumu: Mükemmel"
        self.setMinimumSize(220, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
            self.status_text = "Sistem Durumu: Mükemmel"
        elif self._score >= 65:
            self.status_text = "Sistem Durumu: İyi"
        elif self._score >= 40:
            self.status_text = "Sistem Durumu: Orta (Bakım Önerilir)"
        else:
            self.status_text = "Sistem Durumu: Kritik (Temizlik Gerekli)"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        p = get_active_theme_colors()

        width = self.width()
        height = self.height()
        size = min(width, height) - 30

        center_x = width / 2.0
        center_y = height / 2.0
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
            QRectF(center_x - 70, center_y - 45, 140, 50),
            Qt.AlignCenter,
            f"{self._score}"
        )

        font_unit = QFont("Segoe UI", 11, QFont.DemiBold)
        painter.setFont(font_unit)
        painter.setPen(QColor(p["TEXT_SECONDARY"]))
        painter.drawText(
            QRectF(center_x - 70, center_y + 2, 140, 22),
            Qt.AlignCenter,
            "SAĞLIK SKORU"
        )

        font_status = QFont("Segoe UI", 10, QFont.Normal)
        painter.setFont(font_status)
        painter.setPen(arc_color)
        painter.drawText(
            QRectF(center_x - 120, center_y + 24, 240, 24),
            Qt.AlignCenter,
            self.status_text
        )

class StatCard(QFrame):
    """Modern rounded statistic card with icon, metric, and subtitle."""
    def __init__(self, icon: str, title: str, initial_value: str = "-", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.icon_lbl = QLabel(icon)
        self.icon_lbl.setStyleSheet("font-size: 20px;")
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        top_row.addWidget(self.icon_lbl)
        top_row.addWidget(self.title_lbl)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.value_lbl = QLabel(initial_value)
        self.value_lbl.setStyleSheet("font-size: 22px; font-weight: 800;")
        layout.addWidget(self.value_lbl)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.sub_lbl)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_lbl.setText(value)
        if subtitle:
            self.sub_lbl.setText(subtitle)
