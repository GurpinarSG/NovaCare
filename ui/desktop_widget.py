"""
NovaCare System Suite - Modular Desktop Performance Monitor
Glassmorphic, customizable desktop performance dock featuring:
- Opacity slider (20% - 100%) and sizing modes (Detailed Card, Horizontal Bar, Vertical Strip)
- Theme presets (Cyberpunk Purple, Neon Cyan, OLED Black, Minimal White, Custom RGB)
- Windows Click-Through mode (WS_EX_TRANSPARENT)
- Multi-monitor coordinate retention and magnetic snap-to-edge
- Telemetries: Discrete GPU (Temp, Load, VRAM), Disk I/O MB/s, Top Consumer Process, Uptime, CPU Temp
- 1-Click Mini Quick Actions: RAM Boost, Game Mode switch, Silent Mode toggle
- Modular display toggles for each telemetry item.
"""
import sys
import ctypes
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QAction, QApplication, QColorDialog, QLayout
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor, QColor
from core.hardware_monitor import HardwareMonitor
from core.memory_booster import MemoryBooster
from core.game_booster import GameBooster
from core.config import ConfigManager
from core.utils import format_bytes, log_debug

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

if sys.platform == 'win32':
    from ctypes import wintypes
    LONG_PTR = ctypes.c_ssize_t
    u32 = ctypes.windll.user32
    if hasattr(u32, "GetWindowLongPtrW"):
        _get_window_long = u32.GetWindowLongPtrW
        _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        _get_window_long.restype = LONG_PTR
    else:
        _get_window_long = u32.GetWindowLongW
        _get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        _get_window_long.restype = wintypes.LONG

    if hasattr(u32, "SetWindowLongPtrW"):
        _set_window_long = u32.SetWindowLongPtrW
        _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
        _set_window_long.restype = LONG_PTR
    else:
        _set_window_long = u32.SetWindowLongW
        _set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        _set_window_long.restype = wintypes.LONG
else:
    _get_window_long = None
    _set_window_long = None

THEME_PRESETS = {
    "neon_cyan": {
        "name": "Neon Camgöbeği",
        "bg": "rgba(8, 22, 36, {alpha})",
        "border": "#38BDF8",
        "title": "#38BDF8",
        "accent": "#38BDF8",
        "secondary": "#34D399",
        "text": "#F8FAFC",
        "btn_bg": "#0284C7",
        "btn_border": "#38BDF8",
        "btn_text": "#FFFFFF"
    },
    "cyberpunk_purple": {
        "name": "Cyberpunk Moru",
        "bg": "rgba(24, 8, 42, {alpha})",
        "border": "#A855F7",
        "title": "#C084FC",
        "accent": "#F472B6",
        "secondary": "#E879F9",
        "text": "#FDF4FF",
        "btn_bg": "#7E22CE",
        "btn_border": "#C084FC",
        "btn_text": "#FFFFFF"
    },
    "oled_black": {
        "name": "OLED Saf Siyah",
        "bg": "rgba(0, 0, 0, {alpha})",
        "border": "#10B981",
        "title": "#10B981",
        "accent": "#34D399",
        "secondary": "#6EE7B7",
        "text": "#FFFFFF",
        "btn_bg": "#047857",
        "btn_border": "#10B981",
        "btn_text": "#FFFFFF"
    },
    "minimal_white": {
        "name": "Minimal Beyaz",
        "bg": "rgba(248, 250, 252, {alpha})",
        "border": "#64748B",
        "title": "#0284C7",
        "accent": "#0369A1",
        "secondary": "#0F172A",
        "text": "#0F172A",
        "btn_bg": "#E2E8F0",
        "btn_border": "#94A3B8",
        "btn_text": "#0F172A"
    }
}

class DesktopPerformanceWidget(QWidget):
    visibilityChanged = pyqtSignal(bool)
    request_restore_main = pyqtSignal()
    clickThroughToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.config = ConfigManager()
        self.hw_monitor = HardwareMonitor()
        self.mem_booster = MemoryBooster()
        self.game_booster = GameBooster()

        self.drag_position = None
        self._is_boosting = False
        self._click_through_active = False

        self._init_ui()
        self._setup_position()
        self._apply_appearance()

        # Telemetry update timer (every 1.8s)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_telemetry)
        self.timer.start(1800)
        self._update_telemetry()

    def _init_ui(self):
        # Clear existing layouts if rebuilding
        if self.layout() is not None:
            QWidget().setLayout(self.layout())

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        # Glassmorphic Card Frame
        self.card = QFrame(self)
        self.card.setObjectName("DesktopWidgetCard")
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(12, 8, 12, 10)
        self.card_layout.setSpacing(4)

        layout_mode = self.config.get("desktop_widget_layout", "card")

        if layout_mode == "horizontal":
            self._build_horizontal_layout()
        elif layout_mode == "vertical":
            self._build_vertical_layout()
        else:
            self._build_card_layout()

        self.root_layout.addWidget(self.card)

    def _build_card_layout(self):
        """Builds standard detailed card layout."""
        self.card_layout.setDirection(QVBoxLayout.TopToBottom)
        self.card_layout.setContentsMargins(14, 10, 14, 12)
        self.card_layout.setSpacing(5)

        # 1. Header (Title, Drag, Close)
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        self.lbl_icon = QLabel("⚡")
        self.lbl_icon.setStyleSheet("font-size: 13px; font-weight: bold;")
        self.lbl_title = QLabel("NovaCare Monitör")
        self.lbl_title.setStyleSheet("font-weight: 800; font-size: 11.5px; letter-spacing: 0.5px;")

        hdr.addWidget(self.lbl_icon)
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()

        if self.config.get("desktop_widget_click_through", False):
            self.lbl_ct_badge = QLabel("🖱️")
            self.lbl_ct_badge.setToolTip("Tıklamayı Geçir (Click-Through) Modu Aktif")
            hdr.addWidget(self.lbl_ct_badge)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(18, 18)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("Widget'ı Gizle (Tepsiden tekrar açabilirsiniz)")
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
        self.card_layout.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.10);")
        self.card_layout.addWidget(sep)

        # 2. Modular Telemetry Labels
        self.lbl_cpu = QLabel("⚡ CPU: %0 (0.0 GHz)")
        self.lbl_cpu.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.lbl_cpu.setWordWrap(True)
        self.lbl_cpu.setVisible(self.config.get("widget_show_cpu", True))
        self.card_layout.addWidget(self.lbl_cpu)

        self.lbl_ram = QLabel("🧠 RAM: %0 (0.0 / 0.0 GB)")
        self.lbl_ram.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.lbl_ram.setWordWrap(True)
        self.lbl_ram.setVisible(self.config.get("widget_show_ram", True))
        self.card_layout.addWidget(self.lbl_ram)

        self.lbl_gpu = QLabel("🎮 GPU: %0 (- °C)")
        self.lbl_gpu.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.lbl_gpu.setWordWrap(True)
        self.lbl_gpu.setVisible(self.config.get("widget_show_gpu", True))
        self.card_layout.addWidget(self.lbl_gpu)

        self.lbl_disk = QLabel("💾 Disk: ↓ 0 B/s   ↑ 0 B/s")
        self.lbl_disk.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_disk.setWordWrap(True)
        self.lbl_disk.setVisible(self.config.get("widget_show_disk_io", True))
        self.card_layout.addWidget(self.lbl_disk)

        self.lbl_net = QLabel("🌐 Ağ:   ↓ 0 KB/s   ↑ 0 KB/s")
        self.lbl_net.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_net.setWordWrap(True)
        self.lbl_net.setVisible(self.config.get("widget_show_net", True))
        self.card_layout.addWidget(self.lbl_net)

        self.lbl_top = QLabel("🔥 Lider: -")
        self.lbl_top.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_top.setWordWrap(True)
        self.lbl_top.setVisible(self.config.get("widget_show_top_app", True))
        self.card_layout.addWidget(self.lbl_top)

        self.lbl_uptime = QLabel("⏱️ Açık Kalma: -")
        self.lbl_uptime.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_uptime.setWordWrap(True)
        self.lbl_uptime.setVisible(self.config.get("widget_show_uptime", True))
        self.card_layout.addWidget(self.lbl_uptime)

        # 3. Mini Quick Actions Row
        self.quick_actions_frame = QWidget()
        qa_lay = QHBoxLayout(self.quick_actions_frame)
        qa_lay.setContentsMargins(0, 4, 0, 0)
        qa_lay.setSpacing(6)

        # RAM Boost
        self.btn_boost = QPushButton("⚡ Boşalt")
        self.btn_boost.setCursor(Qt.PointingHandCursor)
        self.btn_boost.setFixedHeight(24)
        self.btn_boost.setToolTip("Anında RAM Çalışma Kümelerini Boşalt")
        self.btn_boost.clicked.connect(self._on_quick_ram_boost)
        qa_lay.addWidget(self.btn_boost, 1)

        # Game Mode Toggle
        is_gm = self.game_booster.is_game_mode_active()
        self.btn_game = QPushButton("🔥 Aktif" if is_gm else "🎮 Oyun")
        self.btn_game.setCursor(Qt.PointingHandCursor)
        self.btn_game.setFixedHeight(24)
        self.btn_game.setToolTip("Oyun & Nihai Performans Modu Devrede" if is_gm else "Oyun & Nihai Performans Modunu Aç")
        self.btn_game.clicked.connect(self._toggle_game_mode)
        qa_lay.addWidget(self.btn_game, 1)

        # Silent Mode Toggle
        is_silent = self.config.get("silent_mode_enabled", False)
        self.btn_silent = QPushButton("🔕 Sessiz" if is_silent else "🔔 Açık")
        self.btn_silent.setCursor(Qt.PointingHandCursor)
        self.btn_silent.setFixedHeight(24)
        self.btn_silent.setToolTip("Sessiz Mod Devrede (Bildirimler gizlendi)" if is_silent else "Bildirimleri Sessize Al")
        self.btn_silent.clicked.connect(self._toggle_silent_mode)
        qa_lay.addWidget(self.btn_silent, 1)

        self.quick_actions_frame.setVisible(self.config.get("widget_show_quick_actions", True))
        self.card_layout.addWidget(self.quick_actions_frame)
        self.card_layout.setSizeConstraint(QLayout.SetMinimumSize)

        # Calculate appropriate height
        visible_count = sum([
            self.config.get("widget_show_cpu", True),
            self.config.get("widget_show_ram", True),
            self.config.get("widget_show_gpu", True),
            self.config.get("widget_show_disk_io", True),
            self.config.get("widget_show_net", True),
            self.config.get("widget_show_top_app", True),
            self.config.get("widget_show_uptime", True),
        ])
        base_h = 55 + (visible_count * 20)
        if self.config.get("widget_show_quick_actions", True):
            base_h += 34
        self.setMinimumSize(280, max(135, base_h))
        self.resize(280, max(135, base_h))

    def _build_horizontal_layout(self):
        """Builds slim horizontal bar layout (perfect above taskbar)."""
        self.card_layout.setDirection(QVBoxLayout.TopToBottom)
        self.card_layout.setContentsMargins(10, 4, 10, 4)

        row = QHBoxLayout()
        row.setSpacing(10)

        lbl_logo = QLabel("⚡ NovaCare")
        lbl_logo.setStyleSheet("font-weight: 800; font-size: 11px;")
        row.addWidget(lbl_logo)

        self.lbl_cpu = QLabel("CPU: %0")
        self.lbl_cpu.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_cpu.setVisible(self.config.get("widget_show_cpu", True))
        row.addWidget(self.lbl_cpu)

        self.lbl_ram = QLabel("RAM: %0")
        self.lbl_ram.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_ram.setVisible(self.config.get("widget_show_ram", True))
        row.addWidget(self.lbl_ram)

        self.lbl_gpu = QLabel("GPU: %0")
        self.lbl_gpu.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        self.lbl_gpu.setVisible(self.config.get("widget_show_gpu", True))
        row.addWidget(self.lbl_gpu)

        self.lbl_disk = QLabel("💾 0 B/s")
        self.lbl_disk.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_disk.setVisible(self.config.get("widget_show_disk_io", True))
        row.addWidget(self.lbl_disk)

        self.lbl_net = QLabel("🌐 0 B/s")
        self.lbl_net.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_net.setVisible(self.config.get("widget_show_net", True))
        row.addWidget(self.lbl_net)

        self.lbl_top = QLabel("🔥 -")
        self.lbl_top.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_top.setVisible(self.config.get("widget_show_top_app", True))
        row.addWidget(self.lbl_top)

        self.lbl_uptime = QLabel("⏱️ -")
        self.lbl_uptime.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_uptime.setVisible(self.config.get("widget_show_uptime", True))
        row.addWidget(self.lbl_uptime)

        # Quick Actions
        self.btn_boost = QPushButton("⚡ Boşalt")
        self.btn_boost.setFixedHeight(20)
        self.btn_boost.setCursor(Qt.PointingHandCursor)
        self.btn_boost.clicked.connect(self._on_quick_ram_boost)
        self.btn_boost.setVisible(self.config.get("widget_show_quick_actions", True))
        row.addWidget(self.btn_boost)

        is_gm = self.game_booster.is_game_mode_active()
        self.btn_game = QPushButton("🔥" if is_gm else "🎮")
        self.btn_game.setFixedSize(22, 20)
        self.btn_game.setCursor(Qt.PointingHandCursor)
        self.btn_game.setToolTip("Oyun Modu: Aktif (Kapatmak için tıkla)" if is_gm else "Oyun Modunu Aç")
        self.btn_game.clicked.connect(self._toggle_game_mode)
        self.btn_game.setVisible(self.config.get("widget_show_quick_actions", True))
        row.addWidget(self.btn_game)

        is_silent = self.config.get("silent_mode_enabled", False)
        self.btn_silent = QPushButton("🔕" if is_silent else "🔔")
        self.btn_silent.setFixedSize(22, 20)
        self.btn_silent.setCursor(Qt.PointingHandCursor)
        self.btn_silent.setToolTip("Sessiz Mod: Aktif (Bildirimler gizlendi)" if is_silent else "Sessiz Moda Al")
        self.btn_silent.clicked.connect(self._toggle_silent_mode)
        self.btn_silent.setVisible(self.config.get("widget_show_quick_actions", True))
        row.addWidget(self.btn_silent)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(16, 16)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background: transparent; color: #94A3B8; border: none; font-size: 10px; font-weight: bold;")
        btn_close.clicked.connect(self.hide)
        row.addWidget(btn_close)

        self.card_layout.addLayout(row)

        visible_count = sum([
            self.config.get("widget_show_cpu", True),
            self.config.get("widget_show_ram", True),
            self.config.get("widget_show_gpu", True),
            self.config.get("widget_show_disk_io", True),
            self.config.get("widget_show_net", True),
            self.config.get("widget_show_top_app", True),
            self.config.get("widget_show_uptime", True),
        ])
        has_qa = self.config.get("widget_show_quick_actions", True)
        bar_w = 120 + (visible_count * 115) + (100 if has_qa else 0)
        self.setFixedSize(max(440, bar_w), 36)

    def _build_vertical_layout(self):
        """Builds slim vertical strip layout (perfect for docking on screen edge)."""
        self.card_layout.setDirection(QVBoxLayout.TopToBottom)
        self.card_layout.setContentsMargins(10, 8, 10, 8)
        self.card_layout.setSpacing(4)

        hdr = QHBoxLayout()
        lbl_logo = QLabel("⚡ NovaCare")
        lbl_logo.setStyleSheet("font-weight: 800; font-size: 11px;")
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(16, 16)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("background: transparent; color: #94A3B8; border: none; font-size: 10px; font-weight: bold;")
        btn_close.clicked.connect(self.hide)
        hdr.addWidget(lbl_logo)
        hdr.addStretch()
        hdr.addWidget(btn_close)
        self.card_layout.addLayout(hdr)

        self.lbl_cpu = QLabel("⚡ CPU\n%0")
        self.lbl_cpu.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_cpu.setVisible(self.config.get("widget_show_cpu", True))
        self.card_layout.addWidget(self.lbl_cpu)

        self.lbl_ram = QLabel("🧠 RAM\n%0")
        self.lbl_ram.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_ram.setVisible(self.config.get("widget_show_ram", True))
        self.card_layout.addWidget(self.lbl_ram)

        self.lbl_gpu = QLabel("🎮 GPU\n%0")
        self.lbl_gpu.setStyleSheet("font-size: 10px; font-weight: 600;")
        self.lbl_gpu.setVisible(self.config.get("widget_show_gpu", True))
        self.card_layout.addWidget(self.lbl_gpu)

        self.lbl_disk = QLabel("💾 Disk\n0 B/s")
        self.lbl_disk.setStyleSheet("font-size: 9.5px; font-weight: 600;")
        self.lbl_disk.setVisible(self.config.get("widget_show_disk_io", True))
        self.card_layout.addWidget(self.lbl_disk)

        self.lbl_net = QLabel("🌐 Ağ\n0 B/s")
        self.lbl_net.setStyleSheet("font-size: 9.5px; font-weight: 600;")
        self.lbl_net.setVisible(self.config.get("widget_show_net", True))
        self.card_layout.addWidget(self.lbl_net)

        self.lbl_top = QLabel("🔥 Lider\n-")
        self.lbl_top.setStyleSheet("font-size: 9.5px; font-weight: 600;")
        self.lbl_top.setVisible(self.config.get("widget_show_top_app", True))
        self.card_layout.addWidget(self.lbl_top)

        self.lbl_uptime = QLabel("⏱️ Açık\n-")
        self.lbl_uptime.setStyleSheet("font-size: 9.5px; font-weight: 600;")
        self.lbl_uptime.setVisible(self.config.get("widget_show_uptime", True))
        self.card_layout.addWidget(self.lbl_uptime)

        # Quick Actions
        self.btn_boost = QPushButton("⚡ Boşalt")
        self.btn_boost.setFixedHeight(22)
        self.btn_boost.setCursor(Qt.PointingHandCursor)
        self.btn_boost.clicked.connect(self._on_quick_ram_boost)
        self.btn_boost.setVisible(self.config.get("widget_show_quick_actions", True))
        self.card_layout.addWidget(self.btn_boost)

        qa_mini = QHBoxLayout()
        qa_mini.setSpacing(4)
        is_gm = self.game_booster.is_game_mode_active()
        self.btn_game = QPushButton("🔥" if is_gm else "🎮")
        self.btn_game.setFixedHeight(20)
        self.btn_game.setCursor(Qt.PointingHandCursor)
        self.btn_game.setToolTip("Oyun Modu: Aktif" if is_gm else "Oyun Modunu Aç")
        self.btn_game.clicked.connect(self._toggle_game_mode)
        qa_mini.addWidget(self.btn_game)

        is_silent = self.config.get("silent_mode_enabled", False)
        self.btn_silent = QPushButton("🔕" if is_silent else "🔔")
        self.btn_silent.setFixedHeight(20)
        self.btn_silent.setCursor(Qt.PointingHandCursor)
        self.btn_silent.setToolTip("Sessiz Mod: Aktif" if is_silent else "Sessiz Moda Al")
        self.btn_silent.clicked.connect(self._toggle_silent_mode)
        qa_mini.addWidget(self.btn_silent)

        if self.config.get("widget_show_quick_actions", True):
            self.card_layout.addLayout(qa_mini)

        visible_count = sum([
            self.config.get("widget_show_cpu", True),
            self.config.get("widget_show_ram", True),
            self.config.get("widget_show_gpu", True),
            self.config.get("widget_show_disk_io", True),
            self.config.get("widget_show_net", True),
            self.config.get("widget_show_top_app", True),
            self.config.get("widget_show_uptime", True),
        ])
        has_qa = self.config.get("widget_show_quick_actions", True)
        v_h = 55 + (visible_count * 38) + (60 if has_qa else 0)
        self.setFixedSize(130, max(120, min(650, v_h)))

    def apply_appearance(self):
        """Public method to rebuild UI layout and apply theme/opacity/click-through."""
        self._init_ui()
        self._apply_appearance()

    def _apply_appearance(self):
        """Applies theme colors, glassmorphism, opacity, and click-through mode."""
        self.layout_mode = self.config.get("desktop_widget_layout", "card")
        theme_key = self.config.get("desktop_widget_theme", "neon_cyan")
        self.theme_name = theme_key
        theme = THEME_PRESETS.get(theme_key, THEME_PRESETS["neon_cyan"])

        # Opacity slider: 0.20 to 1.00
        opacity = float(self.config.get("desktop_widget_opacity", 0.90))
        opacity = max(0.20, min(1.00, opacity))
        self.opacity = opacity

        bg_css = theme["bg"].format(alpha=f"{opacity:.2f}")
        border_col = theme["border"]
        text_col = theme["text"]
        btn_bg = theme["btn_bg"]
        btn_border = theme["btn_border"]

        btn_text = theme.get("btn_text", "#FFFFFF")

        # Custom RGB override if chosen
        if theme_key == "custom_rgb":
            custom_hex = self.config.get("desktop_widget_custom_color", "#38BDF8")
            c = QColor(custom_hex)
            if not c.isValid():
                c = QColor("#38BDF8")
            r, g, b = c.red(), c.green(), c.blue()
            bg_css = f"rgba({max(5, r//5)}, {max(5, g//5)}, {max(8, b//5)}, {opacity:.2f})"
            border_col = c.name()
            btn_bg = c.name()
            btn_border = c.name()
            btn_text = "#0F172A" if c.lightness() > 140 else "#FFFFFF"

        # Supported hover background lightening/darkening rule
        btn_c = QColor(btn_bg)
        if btn_c.lightness() > 140:
            btn_hover_bg = btn_c.darker(112).name()
        else:
            if btn_c.red() < 25 and btn_c.green() < 25 and btn_c.blue() < 25:
                btn_hover_bg = "#262626"
            else:
                btn_hover_bg = btn_c.lighter(118).name()

        card_style = f"""
            QFrame#DesktopWidgetCard {{
                background-color: {bg_css};
                border: 1px solid {border_col};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_col};
                background: transparent;
                border: none;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                font-size: 10px;
                font-weight: 700;
                border-radius: 5px;
                border: 1px solid {btn_border};
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
            }}
        """
        self.card.setStyleSheet(card_style)

        # Apply Click-Through mode
        ct_enabled = self.config.get("desktop_widget_click_through", False)
        self.set_click_through(ct_enabled)

    def set_click_through(self, enabled: bool):
        """Passes mouse clicks directly through the widget window to windows beneath it."""
        changed = (getattr(self, '_click_through_active', None) != enabled)
        self._click_through_active = enabled
        self.click_through = enabled
        self.config.set("desktop_widget_click_through", enabled)
        if hasattr(self, 'lbl_ct_badge') and self.lbl_ct_badge is not None:
            try:
                self.lbl_ct_badge.setVisible(enabled)
            except (RuntimeError, Exception):
                pass

        if changed:
            self.clickThroughToggled.emit(enabled)

        if sys.platform == 'win32' and _get_window_long and _set_window_long:
            try:
                hwnd = wintypes.HWND(int(self.winId()))
                style = _get_window_long(hwnd, GWL_EXSTYLE)
                if enabled:
                    _set_window_long(hwnd, GWL_EXSTYLE, LONG_PTR(style | WS_EX_TRANSPARENT | WS_EX_LAYERED))
                else:
                    _set_window_long(hwnd, GWL_EXSTYLE, LONG_PTR(style & ~WS_EX_TRANSPARENT))
            except Exception as e:
                log_debug(f"DesktopPerformanceWidget set_click_through error: {e}")


    def _setup_position(self):
        """Multi-monitor aware position initialization with bounds checking."""
        saved_pos = self.config.get("desktop_widget_pos")
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            self.move(100, 100)
            return

        avail = screen.availableGeometry()

        if saved_pos and isinstance(saved_pos, list) and len(saved_pos) == 2:
            x, y = saved_pos
            # Validate if coordinates belong to any connected monitor and clamp within screen
            for s in QApplication.screens():
                s_geom = s.availableGeometry()
                if (s_geom.left() - 50) <= x <= s_geom.right() and (s_geom.top() - 50) <= y <= s_geom.bottom():
                    clamped_x = max(s_geom.left() + 8, min(x, s_geom.left() + s_geom.width() - self.width() - 8))
                    clamped_y = max(s_geom.top() + 8, min(y, s_geom.top() + s_geom.height() - self.height() - 8))
                    self.move(clamped_x, clamped_y)
                    return

        # Default: Bottom-right corner above taskbar
        default_x = avail.left() + avail.width() - self.width() - 24
        default_y = avail.top() + avail.height() - self.height() - 24
        self.move(default_x, default_y)

    def snap_to_edge_or_corner(self):
        """Snaps widget magnetically to nearest screen edge or corner."""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if not screen:
            return

        avail = screen.availableGeometry()
        snap_threshold = 30
        cur_x = self.x()
        cur_y = self.y()
        w = self.width()
        h = self.height()

        # Horizontal snap
        if abs(cur_x - avail.left()) < snap_threshold:
            cur_x = avail.left() + 8
        elif abs((cur_x + w) - (avail.left() + avail.width())) < snap_threshold:
            cur_x = avail.left() + avail.width() - w - 8

        # Vertical snap
        if abs(cur_y - avail.top()) < snap_threshold:
            cur_y = avail.top() + 8
        elif abs((cur_y + h) - (avail.top() + avail.height())) < snap_threshold:
            cur_y = avail.top() + avail.height() - h - 8

        # Guarantee fully within monitor boundaries
        cur_x = max(avail.left() + 8, min(cur_x, avail.left() + avail.width() - w - 8))
        cur_y = max(avail.top() + 8, min(cur_y, avail.top() + avail.height() - h - 8))

        self.move(cur_x, cur_y)
        self.config.set("desktop_widget_pos", [cur_x, cur_y])

    def snap_to_corner(self):
        """Snaps widget explicitly to bottom-right corner."""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = avail.x() + avail.width() - self.width() - 24
            y = avail.y() + avail.height() - self.height() - 24
            self.move(x, y)
            self.config.set("desktop_widget_pos", [x, y])

    def _update_telemetry(self):
        """Pulls latest hardware telemetry and updates UI widgets."""
        if not self.isVisible():
            return
        try:
            stats = self.hw_monitor.get_hardware_stats()
            self.update_stats(stats)
        except Exception as e:
            log_debug(f"DesktopPerformanceWidget telemetry error: {e}")

    def update_stats(self, stats: dict):
        """Updates display labels with live hardware metrics."""
        cpu_pct = stats.get("cpu_percent", 0)
        cpu_freq = stats.get("cpu_freq_ghz", 0.0)
        cpu_temp = stats.get("cpu_temp")
        ram_pct = stats.get("ram_percent", 0)
        ram_used = stats.get("ram_used_gb", 0)
        ram_total = stats.get("ram_total_gb", 0)
        down_str = stats.get("net_down_str", "0 KB/s")
        up_str = stats.get("net_up_str", "0 KB/s")
        d_read = stats.get("disk_read_str", "0 B/s")
        d_write = stats.get("disk_write_str", "0 B/s")
        top_str = stats.get("top_consumer_str", "-")
        uptime = stats.get("uptime_str", "-")

        gpu_load = stats.get("gpu_load", 0)
        gpu_temp = stats.get("gpu_temp")
        gpu_vram_used = stats.get("gpu_mem_used_mb", 0)
        gpu_vram_tot = stats.get("gpu_mem_total_mb", 0)
        has_gpu = stats.get("has_gpu", False)

        layout_mode = self.config.get("desktop_widget_layout", "card")
        temp_str = f" | {cpu_temp:.0f}°C" if cpu_temp is not None else ""

        if layout_mode == "horizontal":
            if hasattr(self, 'lbl_cpu'):
                self.lbl_cpu.setText(f"CPU: %{cpu_pct:.0f}{temp_str}")
            if hasattr(self, 'lbl_ram'):
                self.lbl_ram.setText(f"RAM: %{ram_pct:.0f}")
            if hasattr(self, 'lbl_gpu'):
                g_temp = f" ({gpu_temp}°C)" if gpu_temp is not None else ""
                self.lbl_gpu.setText(f"GPU: %{gpu_load}{g_temp}" if has_gpu else "GPU: Yok")
            if hasattr(self, 'lbl_disk'):
                self.lbl_disk.setText(f"💾 {d_read}")
            if hasattr(self, 'lbl_net'):
                self.lbl_net.setText(f"🌐 ↓ {down_str}")
            if hasattr(self, 'lbl_top'):
                self.lbl_top.setText(f"🔥 {top_str}")
            if hasattr(self, 'lbl_uptime'):
                self.lbl_uptime.setText(f"⏱️ {uptime}")
        elif layout_mode == "vertical":
            if hasattr(self, 'lbl_cpu'):
                self.lbl_cpu.setText(f"⚡ CPU\n%{cpu_pct:.0f}{temp_str}")
            if hasattr(self, 'lbl_ram'):
                self.lbl_ram.setText(f"🧠 RAM\n%{ram_pct:.0f}")
            if hasattr(self, 'lbl_gpu'):
                g_temp = f" {gpu_temp}°C" if gpu_temp is not None else ""
                self.lbl_gpu.setText(f"🎮 GPU\n%{gpu_load}{g_temp}" if has_gpu else "🎮 GPU\nYok")
            if hasattr(self, 'lbl_disk'):
                self.lbl_disk.setText(f"💾 Disk\n{d_read}")
            if hasattr(self, 'lbl_net'):
                self.lbl_net.setText(f"🌐 Ağ\n↓{down_str}")
            if hasattr(self, 'lbl_top'):
                self.lbl_top.setText(f"🔥 Lider\n{top_str}")
            if hasattr(self, 'lbl_uptime'):
                self.lbl_uptime.setText(f"⏱️ Açık\n{uptime}")
        else:
            if hasattr(self, 'lbl_cpu'):
                self.lbl_cpu.setText(f"⚡ CPU: %{cpu_pct:.0f}  ({cpu_freq:.1f} GHz{temp_str})")
            if hasattr(self, 'lbl_ram'):
                self.lbl_ram.setText(f"🧠 RAM: %{ram_pct:.0f}  ({ram_used} / {ram_total} GB)")
            if hasattr(self, 'lbl_gpu'):
                if has_gpu:
                    g_temp_str = f" | {gpu_temp}°C" if gpu_temp is not None else ""
                    vram_str = f" | {gpu_vram_used}/{gpu_vram_tot} MB" if gpu_vram_tot > 0 else ""
                    self.lbl_gpu.setText(f"🎮 GPU: %{gpu_load}{g_temp_str}{vram_str}")
                else:
                    self.lbl_gpu.setText("🎮 GPU: Harici GPU Algılanmadı")
            if hasattr(self, 'lbl_disk'):
                self.lbl_disk.setText(f"💾 Disk: ↓ {d_read}   ↑ {d_write}")
            if hasattr(self, 'lbl_net'):
                self.lbl_net.setText(f"🌐 Ağ:   ↓ {down_str}   ↑ {up_str}")
            if hasattr(self, 'lbl_top'):
                self.lbl_top.setText(f"🔥 Lider: {top_str}")
            if hasattr(self, 'lbl_uptime'):
                self.lbl_uptime.setText(f"⏱️ Sistem: {uptime}")

    def _on_quick_ram_boost(self):
        """Executes 1-click RAM purge asynchronously and displays success confirmation."""
        if self._is_boosting:
            return
        self._is_boosting = True
        self.btn_boost.setText("⏳...")
        self.btn_boost.setEnabled(False)

        from ui.views.memory_view import RamBoostWorker
        self.ram_boost_worker = RamBoostWorker(self.mem_booster)
        self.ram_boost_worker.finished.connect(self._on_ram_boost_finished)
        self.ram_boost_worker.start()

    def _on_ram_boost_finished(self, freed_bytes: int, count: int):
        freed_str = format_bytes(freed_bytes)
        self.btn_boost.setText(f"✨+{freed_str}")

        QTimer.singleShot(400, self._update_telemetry)

        def _restore():
            try:
                if hasattr(self, 'btn_boost') and self.btn_boost:
                    self.btn_boost.setText("⚡ Boşalt")
                    self.btn_boost.setEnabled(True)
            except (RuntimeError, Exception):
                pass
            self._is_boosting = False

        QTimer.singleShot(2200, _restore)

    def _toggle_game_mode(self):
        """1-Click Game Mode toggle asynchronously."""
        if hasattr(self, 'game_mode_worker') and self.game_mode_worker and self.game_mode_worker.isRunning():
            return
        current = self.game_booster.is_game_mode_active()
        activating = not current
        self.btn_game.setEnabled(False)
        self.btn_game.setText("⏳...")

        from ui.views.dashboard_view import GameModeWorker
        self.game_mode_worker = GameModeWorker(self.game_booster, activating)
        self.game_mode_worker.finished.connect(self._on_game_mode_finished)
        self.game_mode_worker.start()

    def _on_game_mode_finished(self, state: dict, was_activating: bool):
        self.btn_game.setEnabled(True)
        layout_mode = self.config.get("desktop_widget_layout", "card")
        if was_activating:
            self.btn_game.setText("🔥 Aktif" if layout_mode == "card" else "🔥")
            self.btn_game.setToolTip("Oyun & Nihai Performans Modu Devrede")
        else:
            self.btn_game.setText("🎮 Oyun" if layout_mode == "card" else "🎮")
            self.btn_game.setToolTip("Oyun Modu Kapalı")

    def _toggle_silent_mode(self):
        """1-Click Silent Mode toggle."""
        cur = self.config.get("silent_mode_enabled", False)
        new_val = not cur
        self.config.set("silent_mode_enabled", new_val)
        layout_mode = self.config.get("desktop_widget_layout", "card")
        if new_val:
            self.btn_silent.setText("🔕 Sessiz" if layout_mode == "card" else "🔕")
            self.btn_silent.setToolTip("Sessiz Mod Devrede (Bildirimler gizlendi)")
        else:
            self.btn_silent.setText("🔔 Açık" if layout_mode == "card" else "🔔")
            self.btn_silent.setToolTip("Bildirimler Normal")

    def switch_layout_mode(self, mode: str):
        """Switches widget layout mode (card, horizontal, vertical)."""
        self.config.set("desktop_widget_layout", mode)
        self._init_ui()
        self._setup_position()
        self._apply_appearance()
        self._update_telemetry()

    def set_opacity_pct(self, pct: int):
        """Sets card opacity percentage (20 to 100)."""
        alpha = max(0.20, min(1.00, pct / 100.0))
        self.config.set("desktop_widget_opacity", alpha)
        self._apply_appearance()

    def set_theme_preset(self, theme_key: str):
        """Sets color theme preset."""
        self.config.set("desktop_widget_theme", theme_key)
        self._apply_appearance()

    def choose_custom_rgb(self):
        """Opens RGB color picker for widget background."""
        col = QColorDialog.getColor(QColor("#38BDF8"), self, "Widget Tema Rengi Seçin")
        if col.isValid():
            self.config.set("desktop_widget_theme", "custom_rgb")
            self.config.set("desktop_widget_custom_color", col.name())
            self._apply_appearance()

    def toggle_modular_item(self, config_key: str, visible: bool):
        """Toggles visibility of a specific modular telemetry element."""
        self.config.set(config_key, visible)
        self._init_ui()
        self._apply_appearance()
        self._update_telemetry()

    # Mouse & Window Events
    def mouseDoubleClickEvent(self, event):
        """Double clicking opens and focuses the NovaCare main suite."""
        self.request_restore_main.emit()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position is not None:
            new_pos = event.globalPos() - self.drag_position
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            if self.config.get("desktop_widget_snap_to_edge", True):
                self.snap_to_edge_or_corner()
            else:
                self.config.set("desktop_widget_pos", [self.x(), self.y()])
            event.accept()

    def contextMenuEvent(self, event):
        """Rich context menu for complete on-the-fly widget personalization."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #38BDF8;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #0284C7;
                color: #FFFFFF;
            }
        """)

        # 1. Main Navigation
        act_open = QAction("⚡  NovaCare'i Aç", self)
        act_open.triggered.connect(self.request_restore_main.emit)
        menu.addAction(act_open)

        act_boost = QAction("🧠  Hızlı RAM Temizle", self)
        act_boost.triggered.connect(self._on_quick_ram_boost)
        menu.addAction(act_boost)

        menu.addSeparator()

        # 2. Layout Mode Submenu
        cur_layout = self.config.get("desktop_widget_layout", "card")
        m_layout = menu.addMenu("📐  Yerleşim Modu")
        act_l_card = QAction("Detaylı Panel (Klasik)", self)
        act_l_card.setCheckable(True)
        act_l_card.setChecked(cur_layout == "card")
        act_l_card.triggered.connect(lambda: self.switch_layout_mode("card"))
        m_layout.addAction(act_l_card)

        act_l_horiz = QAction("Yatay İnce Çubuk (Bar)", self)
        act_l_horiz.setCheckable(True)
        act_l_horiz.setChecked(cur_layout == "horizontal")
        act_l_horiz.triggered.connect(lambda: self.switch_layout_mode("horizontal"))
        m_layout.addAction(act_l_horiz)

        act_l_vert = QAction("Dikey Şerit (Kenar Çubuğu)", self)
        act_l_vert.setCheckable(True)
        act_l_vert.setChecked(cur_layout == "vertical")
        act_l_vert.triggered.connect(lambda: self.switch_layout_mode("vertical"))
        m_layout.addAction(act_l_vert)

        # 3. Theme Submenu
        cur_theme = self.config.get("desktop_widget_theme", "neon_cyan")
        m_theme = menu.addMenu("🎨  Renk ve Tema")
        themes = [
            ("neon_cyan", "Neon Camgöbeği"),
            ("cyberpunk_purple", "Cyberpunk Moru"),
            ("oled_black", "OLED Saf Siyah"),
            ("minimal_white", "Minimal Beyaz")
        ]
        for key, name in themes:
            act_t = QAction(name, self)
            act_t.setCheckable(True)
            act_t.setChecked(cur_theme == key)
            act_t.triggered.connect(lambda chk, k=key: self.set_theme_preset(k))
            m_theme.addAction(act_t)

        m_theme.addSeparator()
        act_custom_col = QAction("Özel RGB Renk Seç...", self)
        act_custom_col.triggered.connect(self.choose_custom_rgb)
        m_theme.addAction(act_custom_col)

        # 4. Opacity Submenu
        cur_opacity = int(float(self.config.get("desktop_widget_opacity", 0.90)) * 100)
        m_opac = menu.addMenu("🔍  Saydamlık (Opaklık)")
        for val in (100, 90, 75, 60, 40, 20):
            act_o = QAction(f"%{val}", self)
            act_o.setCheckable(True)
            act_o.setChecked(abs(cur_opacity - val) < 8)
            act_o.triggered.connect(lambda chk, v=val: self.set_opacity_pct(v))
            m_opac.addAction(act_o)

        # 5. Modular Indicators Submenu
        m_modules = menu.addMenu("📊  Gösterge ve Modüller")
        modules = [
            ("widget_show_cpu", "İşlemci (CPU)"),
            ("widget_show_ram", "Bellek (RAM)"),
            ("widget_show_gpu", "Ekran Kartı (GPU)"),
            ("widget_show_disk_io", "Disk I/O Hızı"),
            ("widget_show_net", "Ağ Hızı (Download/Upload)"),
            ("widget_show_top_app", "Lider Süreç Göstergesi"),
            ("widget_show_uptime", "Sistem Uptime & Çalışma Süresi"),
            ("widget_show_quick_actions", "Hızlı Eylem Butonları")
        ]
        for ckey, cname in modules:
            act_m = QAction(cname, self)
            act_m.setCheckable(True)
            act_m.setChecked(self.config.get(ckey, True))
            act_m.triggered.connect(lambda chk, k=ckey: self.toggle_modular_item(k, chk))
            m_modules.addAction(act_m)

        menu.addSeparator()

        # 6. Click-Through Toggle
        act_ct = QAction("🖱️  Tıklamayı Geçir (Click-Through)", self)
        act_ct.setCheckable(True)
        act_ct.setChecked(self._click_through_active)
        act_ct.triggered.connect(lambda chk: self.set_click_through(chk))
        menu.addAction(act_ct)

        # 7. Snap to Edge Toggle
        act_snap_edge = QAction("🧲  Kenara Mıknatısla (Snap to Edge)", self)
        act_snap_edge.setCheckable(True)
        act_snap_edge.setChecked(self.config.get("desktop_widget_snap_to_edge", True))
        act_snap_edge.triggered.connect(lambda chk: self.config.set("desktop_widget_snap_to_edge", chk))
        menu.addAction(act_snap_edge)

        act_snap_corner = QAction("📍  Ekran Köşesine Hizala", self)
        act_snap_corner.triggered.connect(self.snap_to_corner)
        menu.addAction(act_snap_corner)

        menu.addSeparator()

        act_close = QAction("✕  Widget'ı Gizle", self)
        act_close.triggered.connect(self.hide)
        menu.addAction(act_close)

        menu.exec_(QCursor.pos())

    def showEvent(self, event):
        super().showEvent(event)
        HardwareMonitor().set_throttled(False)
        self.visibilityChanged.emit(True)
        self._update_telemetry()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.visibilityChanged.emit(False)
        app = QApplication.instance()
        main_win = None
        for w in (app.topLevelWidgets() if app else []):
            if w.__class__.__name__ == "MainWindow":
                main_win = w
                break
        if main_win and (main_win.isHidden() or main_win.isMinimized()):
            HardwareMonitor().set_throttled(True)

    def closeEvent(self, event):
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        for w_attr in ('ram_boost_worker', 'game_mode_worker'):
            if hasattr(self, w_attr):
                w = getattr(self, w_attr)
                if w and getattr(w, 'isRunning', lambda: False)():
                    w.quit()
                    w.wait(300)
        super().closeEvent(event)
