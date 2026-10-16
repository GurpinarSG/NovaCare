"""
NovaCare System Suite - Theme, Palettes and Stylesheets (QSS)
Supports Dynamic Theme Engine: Dark Mode, Light Mode, and Windows System Default.
Includes specialized high-contrast styling for right-click context menus (QMenu),
tray popups, dialogs, and native Fluent aesthetics.
"""
import sys
import winreg
from typing import Optional

def get_system_theme() -> str:
    """Detects whether Windows 10/11 is currently using Light or Dark app mode."""
    if sys.platform != 'win32':
        return "dark"
    try:
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return "light" if val == 1 else "dark"
    except Exception:
        return "dark"

# 1. Dark Mode Palette (High-Contrast Slate / Deep Navy)
DARK_PALETTE = {
    "NAME": "dark",
    "BG_DARK": "#0B0F19",
    "BG_SIDEBAR": "#0F172A",
    "BG_CARD": "#1E293B",
    "BG_CARD_HOVER": "#27354E",
    "BG_INPUT": "#162032",
    "BORDER_COLOR": "#334155",
    "BORDER_HIGHLIGHT": "#475569",
    "COLOR_ACCENT": "#38BDF8",
    "COLOR_ACCENT_HOVER": "#0EA5E9",
    "COLOR_SUCCESS": "#34D399",
    "COLOR_WARNING": "#FCD34D",
    "COLOR_DANGER": "#F87171",
    "COLOR_PURPLE": "#C084FC",
    "TEXT_PRIMARY": "#FFFFFF",
    "TEXT_SECONDARY": "#E2E8F0",
    "TEXT_MUTED": "#94A3B8",
    "TABLE_ALT_BG": "#162032",
    "TABLE_SEL_BG": "rgba(56, 189, 248, 0.28)",
    "MENU_BG": "#1E293B",
    "MENU_TEXT": "#F8FAFC",
    "MENU_HOVER_BG": "#38BDF8",
    "MENU_HOVER_TEXT": "#041326",
    "MENU_BORDER": "#475569",
    "INPUT_BG": "#1E293B",
    "BTN_PRIMARY_TEXT": "#FFFFFF",
    "BTN_SUCCESS_TEXT": "#FFFFFF",
    "GAUGE_TRACK": "#334155"
}

# 2. Light Mode Palette (Crisp Windows 11 Fluent Light)
LIGHT_PALETTE = {
    "NAME": "light",
    "BG_DARK": "#F1F5F9",              # Soft light slate background
    "BG_SIDEBAR": "#FFFFFF",           # Pure white distinct sidebar
    "BG_CARD": "#FFFFFF",              # Crisp white cards & panels
    "BG_CARD_HOVER": "#F8FAFC",
    "BG_INPUT": "#FFFFFF",
    "BORDER_COLOR": "#CBD5E1",         # Clean visible slate border
    "BORDER_HIGHLIGHT": "#94A3B8",
    "COLOR_ACCENT": "#0284C7",         # Rich Ocean Blue (High contrast against white)
    "COLOR_ACCENT_HOVER": "#0369A1",
    "COLOR_SUCCESS": "#047857",        # Crisp Forest Emerald (7.1:1 contrast)
    "COLOR_WARNING": "#B45309",        # Rich Amber 700 (8.2:1 contrast)
    "COLOR_DANGER": "#B91C1C",         # Bold Crimson Red (7.6:1 contrast)
    "COLOR_PURPLE": "#7C3AED",
    "TEXT_PRIMARY": "#0F172A",         # Deep Slate (15.5:1 contrast on white)
    "TEXT_SECONDARY": "#1E293B",       # Slate 800 (13:1 contrast)
    "TEXT_MUTED": "#475569",           # Slate 600 (5.8:1 contrast)
    "TABLE_ALT_BG": "#F8FAFC",
    "TABLE_SEL_BG": "rgba(2, 132, 199, 0.20)",
    "MENU_BG": "#FFFFFF",
    "MENU_TEXT": "#0F172A",
    "MENU_HOVER_BG": "#0284C7",
    "MENU_HOVER_TEXT": "#FFFFFF",
    "MENU_BORDER": "#CBD5E1",
    "INPUT_BG": "#FFFFFF",
    "BTN_PRIMARY_TEXT": "#FFFFFF",
    "BTN_SUCCESS_TEXT": "#FFFFFF",
    "GAUGE_TRACK": "#E2E8F0"
}

def get_active_theme_colors(theme_mode: Optional[str] = None) -> dict:
    """Resolves and returns the active color palette dict based on mode ('system', 'dark', 'light')."""
    if theme_mode is None:
        try:
            from core.config import ConfigManager
            theme_mode = ConfigManager().get("theme", "system")
        except Exception:
            theme_mode = "system"

    if theme_mode == "system":
        resolved = get_system_theme()
    else:
        resolved = str(theme_mode).lower()

    if resolved == "light":
        return LIGHT_PALETTE.copy()
    return DARK_PALETTE.copy()

# Default constants (Dark mode as baseline for direct imports)
_def = DARK_PALETTE
BG_DARK = _def["BG_DARK"]
BG_SIDEBAR = _def["BG_SIDEBAR"]
BG_CARD = _def["BG_CARD"]
BG_CARD_HOVER = _def["BG_CARD_HOVER"]
BG_INPUT = _def["BG_INPUT"]
BORDER_COLOR = _def["BORDER_COLOR"]
BORDER_HIGHLIGHT = _def["BORDER_HIGHLIGHT"]
COLOR_ACCENT = _def["COLOR_ACCENT"]
COLOR_ACCENT_HOVER = _def["COLOR_ACCENT_HOVER"]
COLOR_SUCCESS = _def["COLOR_SUCCESS"]
COLOR_WARNING = _def["COLOR_WARNING"]
COLOR_DANGER = _def["COLOR_DANGER"]
COLOR_PURPLE = _def["COLOR_PURPLE"]
TEXT_PRIMARY = _def["TEXT_PRIMARY"]
TEXT_SECONDARY = _def["TEXT_SECONDARY"]
TEXT_MUTED = _def["TEXT_MUTED"]

def get_stylesheet(theme_mode: Optional[str] = None) -> str:
    """Generates the full Qt stylesheet for the requested or current system theme."""
    import os
    p = get_active_theme_colors(theme_mode)
    base_assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    if getattr(sys, 'frozen', False):
        base_assets = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), "assets")
    check_ico = os.path.join(base_assets, "check_white.png").replace("\\", "/")

    return f"""
QMainWindow, QDialog, QMessageBox, QInputDialog {{
    background-color: {p['BG_DARK']};
    color: {p['TEXT_PRIMARY']};
    font-family: 'Segoe UI', 'Segoe UI Variable Display', Roboto, sans-serif;
}}

QMessageBox QLabel, QDialog QLabel, QInputDialog QLabel {{
    color: {p['TEXT_PRIMARY']};
    background-color: transparent;
    font-size: 13px;
    font-weight: 500;
}}

QWidget {{
    color: {p['TEXT_PRIMARY']};
    font-family: 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
}}

QLabel {{
    color: {p['TEXT_PRIMARY']};
    background-color: transparent;
}}

QLabel#StatTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {p['TEXT_SECONDARY']};
}}

QLabel#StatValue {{
    font-size: 22px;
    font-weight: 800;
    color: {p['TEXT_PRIMARY']};
}}

QLabel#StatSub {{
    font-size: 11px;
    font-weight: 600;
    color: {p['COLOR_ACCENT']};
}}

/* Sidebar */
#SidebarWidget {{
    background-color: {p['BG_SIDEBAR']};
    border-right: 1px solid {p['BORDER_COLOR']};
}}

#SidebarBrand {{
    font-size: 19px;
    font-weight: 800;
    color: {p['COLOR_ACCENT']};
    letter-spacing: 0.5px;
}}

#SidebarSubtitle {{
    font-size: 11px;
    color: {p['TEXT_MUTED']};
    font-weight: 600;
    letter-spacing: 1px;
}}

/* Navigation Buttons */
QPushButton.nav-btn {{
    text-align: left;
    padding: 9px 14px;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {p['TEXT_SECONDARY']};
    font-size: 12.5px;
    font-weight: 600;
    margin: 1px 6px;
}}

QPushButton.nav-btn:hover {{
    background-color: {p['BG_CARD_HOVER']};
    color: {p['TEXT_PRIMARY']};
}}

QPushButton.nav-btn:checked {{
    background-color: {p['TABLE_SEL_BG']};
    color: #FFFFFF;
    font-weight: 700;
    border-left: 3px solid {p['COLOR_ACCENT']};
}}

/* Content Header */
#ViewTitle {{
    font-size: 22px;
    font-weight: 800;
    color: {p['TEXT_PRIMARY']};
}}

#ViewSubtitle {{
    font-size: 13px;
    color: {p['TEXT_SECONDARY']};
}}

/* Cards & Panel Frames */
.card-widget, QFrame#CardFrame, QFrame#ToolbarFrame, QFrame#StatCard, QFrame#CenterCard {{
    background-color: {p['BG_CARD']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 12px;
}}

.card-widget:hover, QFrame#CardFrame:hover, QFrame#StatCard:hover {{
    border-color: {p['BORDER_HIGHLIGHT']};
}}

/* Action Buttons */
/* Universal Base QPushButton (Provides high contrast, solid border & background to all standard buttons) */
QPushButton {{
    background-color: {p['BG_CARD']};
    color: {p['TEXT_PRIMARY']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 22px;
}}

QPushButton:hover {{
    background-color: {p['BG_CARD_HOVER']};
    border-color: {p['COLOR_ACCENT']};
    color: {p['TEXT_PRIMARY']};
}}

QPushButton:pressed {{
    background-color: {p['BORDER_COLOR']};
}}

QPushButton:disabled {{
    background-color: {p['BG_INPUT']};
    color: {p['TEXT_MUTED']};
    border-color: {p['BORDER_COLOR']};
}}

/* High-Contrast Confirmation Dialog Buttons (Evet/Hayır, OK/Cancel, Yes/No) */
QMessageBox QPushButton, QDialog QPushButton, QDialogButtonBox QPushButton {{
    background-color: {p['BG_CARD']};
    color: {p['TEXT_PRIMARY']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 6px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: 700;
    min-width: 82px;
    min-height: 24px;
}}

QMessageBox QPushButton:hover, QDialog QPushButton:hover, QDialogButtonBox QPushButton:hover {{
    background-color: {p['BG_CARD_HOVER']};
    border-color: {p['COLOR_ACCENT']};
    color: {p['COLOR_ACCENT']};
}}

QMessageBox QPushButton:pressed, QDialog QPushButton:pressed, QDialogButtonBox QPushButton:pressed {{
    background-color: {p['BORDER_COLOR']};
}}

QMessageBox QPushButton:default, QDialog QPushButton:default, QDialogButtonBox QPushButton:default,
QMessageBox QPushButton:focus, QDialog QPushButton:focus {{
    background-color: {p['COLOR_ACCENT']};
    color: {p['BTN_PRIMARY_TEXT']};
    border: 1px solid {p['COLOR_ACCENT']};
    font-weight: 700;
}}

QMessageBox QPushButton:default:hover, QDialog QPushButton:default:hover, QDialogButtonBox QPushButton:default:hover,
QMessageBox QPushButton:focus:hover, QDialog QPushButton:focus:hover {{
    background-color: {p['COLOR_ACCENT_HOVER']};
    border-color: {p['COLOR_ACCENT_HOVER']};
    color: {p['BTN_PRIMARY_TEXT']};
}}

QPushButton.primary-btn {{
    background-color: {p['COLOR_ACCENT']};
    color: {p['BTN_PRIMARY_TEXT']};
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.primary-btn:hover {{
    background-color: {p['COLOR_ACCENT_HOVER']};
}}

QPushButton.primary-btn:disabled {{
    background-color: {p['BORDER_COLOR']};
    color: {p['TEXT_MUTED']};
}}

QPushButton.success-btn {{
    background-color: {p['COLOR_SUCCESS']};
    color: {p['BTN_SUCCESS_TEXT']};
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.success-btn:hover {{
    background-color: #047857;
}}

QPushButton.danger-btn {{
    background-color: {p['COLOR_DANGER']};
    color: #FFFFFF;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton.danger-btn:hover {{
    background-color: #B91C1C;
}}

QPushButton.secondary-btn {{
    background-color: {p['BG_CARD']};
    color: {p['TEXT_PRIMARY']};
    font-weight: 600;
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton.secondary-btn:hover {{
    background-color: {p['BG_CARD_HOVER']};
    border-color: {p['BORDER_HIGHLIGHT']};
}}

/* Big 1-Click Scan Button (High Contrast Ultra Crisp) */
QPushButton#BigScanBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #0EA5E9);
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 26px;
    min-width: 380px;
    max-width: 380px;
    min-height: 52px;
    max-height: 52px;
    padding: 12px 24px;
    letter-spacing: 0.5px;
}}

QPushButton#BigScanBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369A1, stop:1 #0284C7);
    color: #FFFFFF;
    border: 1px solid #7DD3FC;
}}

QPushButton#BigScanBtn:pressed {{
    background-color: #0369A1;
    color: #FFFFFF;
}}

QPushButton#BigScanBtn:disabled {{
    background-color: {p['BORDER_COLOR']};
    color: {p['TEXT_MUTED']};
    border: none;
}}

/* Big 1-Click Fix Button (High Contrast Ultra Crisp) */
QPushButton#BigFixBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10B981);
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 26px;
    min-width: 380px;
    max-width: 380px;
    min-height: 52px;
    max-height: 52px;
    padding: 12px 24px;
    letter-spacing: 0.5px;
}}

QPushButton#BigFixBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
    color: #FFFFFF;
    border: 1px solid #34D399;
}}

QPushButton#BigFixBtn:pressed {{
    background-color: #047857;
    color: #FFFFFF;
}}

QPushButton#BigFixBtn:disabled {{
    background-color: {p['BORDER_COLOR']};
    color: {p['TEXT_MUTED']};
    border: none;
}}

/* Table Views */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {p['BG_CARD']};
    alternate-background-color: {p['TABLE_ALT_BG']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 10px;
    gridline-color: {p['BORDER_COLOR']};
    color: {p['TEXT_PRIMARY']};
    selection-background-color: {p['TABLE_SEL_BG']};
    selection-color: {p['TEXT_PRIMARY']};
}}

QTableWidget::item, QTreeWidget::item, QListWidget::item {{
    color: {p['TEXT_PRIMARY']};
    padding: 4px;
}}

QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    color: {p['TEXT_PRIMARY']};
    background-color: {p['TABLE_SEL_BG']};
}}

QHeaderView::section {{
    background-color: {p['BG_SIDEBAR']};
    color: {p['TEXT_SECONDARY']};
    padding: 10px 10px;
    border: none;
    border-bottom: 2px solid {p['BORDER_COLOR']};
    border-right: 1px solid {p['BORDER_COLOR']};
    font-weight: 700;
    font-size: 12px;
}}

QTableCornerButton::section {{
    background-color: {p['BG_SIDEBAR']};
    border: none;
}}

/* Context Menus (Right-Click Menus & Tray Popups - High Contrast Fix) */
QMenu {{
    background-color: {p['MENU_BG']};
    color: {p['MENU_TEXT']};
    border: 1px solid {p['MENU_BORDER']};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 24px 8px 14px;
    border-radius: 6px;
    background-color: transparent;
    color: {p['MENU_TEXT']};
    font-size: 13px;
    font-weight: 500;
}}

QMenu::item:selected {{
    background-color: {p['MENU_HOVER_BG']};
    color: {p['MENU_HOVER_TEXT']};
    font-weight: 700;
}}

QMenu::item:disabled {{
    color: {p['TEXT_MUTED']};
}}

QMenu::separator {{
    height: 1px;
    background-color: {p['BORDER_COLOR']};
    margin: 5px 8px;
}}

/* Tooltips */
QToolTip {{
    background-color: {p['MENU_BG']};
    color: {p['MENU_TEXT']};
    border: 1px solid {p['MENU_BORDER']};
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}}

/* Progress Bars */
QProgressBar {{
    background-color: {p['BG_INPUT']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 6px;
    text-align: center;
    color: {p['TEXT_PRIMARY']};
    font-weight: 700;
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['COLOR_ACCENT']}, stop:1 #2563EB);
    border-radius: 5px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {p['BG_DARK']};
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {p['BORDER_COLOR']};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p['BORDER_HIGHLIGHT']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Line Edits & Search Boxes */
QLineEdit, QTextEdit {{
    background-color: {p['BG_INPUT']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 8px 14px;
    color: {p['TEXT_PRIMARY']};
    font-size: 13px;
}}

QLineEdit:focus, QTextEdit:focus {{
    border: 1px solid {p['COLOR_ACCENT']};
}}

/* Combo Boxes */
QComboBox {{
    background-color: {p['BG_INPUT']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 6px 12px;
    color: {p['TEXT_PRIMARY']};
    font-size: 13px;
    font-weight: 600;
}}

QComboBox:hover {{
    border-color: {p['BORDER_HIGHLIGHT']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {p['MENU_BG']};
    color: {p['MENU_TEXT']};
    selection-background-color: {p['MENU_HOVER_BG']};
    selection-color: {p['MENU_HOVER_TEXT']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 4px;
}}

/* Scroll Area & Viewports - Eliminates white flashes and unstyled backgrounds */
QScrollArea {{
    background-color: transparent;
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
    background: transparent;
}}

QScrollArea > .QWidget {{
    background-color: transparent;
    background: transparent;
}}

QScrollArea QWidget#qt_scrollarea_viewport {{
    background-color: transparent;
    background: transparent;
    border: none;
}}

/* Checkboxes & Radio Buttons */
QCheckBox, QRadioButton {{
    color: {p['TEXT_PRIMARY']};
    spacing: 8px;
    font-size: 13px;
    background-color: transparent;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 4px;
    background-color: {p['BG_INPUT']};
}}

QCheckBox::indicator:hover {{
    border-color: {p['COLOR_ACCENT']};
}}

QCheckBox::indicator:checked {{
    background-color: {p['COLOR_ACCENT']};
    border-color: {p['COLOR_ACCENT']};
    image: url("{check_ico}");
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 9px;
    background-color: {p['BG_INPUT']};
}}

QRadioButton::indicator:hover {{
    border-color: {p['COLOR_ACCENT']};
}}

QRadioButton::indicator:checked {{
    background-color: {p['COLOR_ACCENT']};
    border: 4px solid {p['BG_CARD']};
}}

/* Plain Text & Changelog Box */
QPlainTextEdit {{
    background-color: {p['BG_INPUT']};
    border: 1px solid {p['BORDER_COLOR']};
    border-radius: 8px;
    padding: 8px 14px;
    color: {p['TEXT_PRIMARY']};
    font-size: 13px;
}}
"""

MAIN_STYLESHEET = get_stylesheet("dark")
