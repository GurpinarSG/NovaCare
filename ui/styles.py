"""
NovaCare System Suite - Theme, Palettes and Stylesheets (QSS)
Modern Windows 11 Dark Fluent Aesthetic with Cyber-Cyan & Emerald Accents.
"""

# Color Constants
BG_DARK = "#0D1117"
BG_SIDEBAR = "#161B22"
BG_CARD = "#1A202C"
BG_CARD_HOVER = "#232B3B"
BG_INPUT = "#1E2636"
BORDER_COLOR = "#2D3748"
BORDER_HIGHLIGHT = "#3D4D6B"

COLOR_ACCENT = "#00D2FF"         # Vibrant Cyan
COLOR_ACCENT_HOVER = "#33DCFF"
COLOR_SUCCESS = "#10B981"        # Emerald Green
COLOR_WARNING = "#F59E0B"        # Amber
COLOR_DANGER = "#EF4444"         # Crimson
COLOR_PURPLE = "#8B5CF6"         # Indigo / Purple

TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A0AEC0"
TEXT_MUTED = "#718096"

MAIN_STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Segoe UI Variable Display', 'Segoe UI Variable', Roboto, sans-serif;
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
}}

/* Sidebar */
#SidebarWidget {{
    background-color: {BG_SIDEBAR};
    border-right: 1px solid {BORDER_COLOR};
}}

#SidebarBrand {{
    font-size: 19px;
    font-weight: 700;
    color: {COLOR_ACCENT};
    letter-spacing: 0.5px;
}}

#SidebarSubtitle {{
    font-size: 11px;
    color: {TEXT_SECONDARY};
    font-weight: 500;
}}

/* Navigation Buttons */
QPushButton.nav-btn {{
    text-align: left;
    padding: 11px 16px;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    font-weight: 600;
    margin: 2px 8px;
}}

QPushButton.nav-btn:hover {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
}}

QPushButton.nav-btn:checked {{
    background-color: rgba(0, 210, 255, 0.15);
    color: {COLOR_ACCENT};
    border-left: 3px solid {COLOR_ACCENT};
}}

/* Content Header */
#ViewTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

#ViewSubtitle {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}

/* Cards */
.card-widget {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_COLOR};
    border-radius: 12px;
    padding: 16px;
}}

.card-widget:hover {{
    border-color: {BORDER_HIGHLIGHT};
}}

/* Action Buttons */
QPushButton.primary-btn {{
    background-color: {COLOR_ACCENT};
    color: #050B14;
    font-weight: 700;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.primary-btn:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

QPushButton.primary-btn:disabled {{
    background-color: #2D3748;
    color: #718096;
}}

QPushButton.success-btn {{
    background-color: {COLOR_SUCCESS};
    color: #05140B;
    font-weight: 700;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.success-btn:hover {{
    background-color: #1ed796;
}}

QPushButton.danger-btn {{
    background-color: {COLOR_DANGER};
    color: #FFFFFF;
    font-weight: 700;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton.danger-btn:hover {{
    background-color: #f87171;
}}

QPushButton.secondary-btn {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    font-weight: 600;
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton.secondary-btn:hover {{
    background-color: {BG_CARD_HOVER};
    border-color: {BORDER_HIGHLIGHT};
}}

/* Big 1-Click Scan Button */
QPushButton#BigScanBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLOR_ACCENT}, stop:1 #0088FF);
    color: #050B14;
    font-size: 18px;
    font-weight: 800;
    border: none;
    border-radius: 32px;
    padding: 16px 40px;
    letter-spacing: 1px;
}}

QPushButton#BigScanBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #33DCFF, stop:1 #1A94FF);
}}

QPushButton#BigFixBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLOR_SUCCESS}, stop:1 #059669);
    color: #05140B;
    font-size: 18px;
    font-weight: 800;
    border: none;
    border-radius: 32px;
    padding: 16px 40px;
    letter-spacing: 1px;
}}

QPushButton#BigFixBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #34D399, stop:1 #10B981);
}}

/* Table Views */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {BG_CARD};
    alternate-background-color: #171E2B;
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
    gridline-color: {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: rgba(0, 210, 255, 0.2);
    selection-color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_SIDEBAR};
    color: {TEXT_SECONDARY};
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid {BORDER_COLOR};
    border-right: 1px solid {BORDER_COLOR};
    font-weight: 700;
    font-size: 12px;
}}

QTableCornerButton::section {{
    background-color: {BG_SIDEBAR};
    border: none;
}}

/* Progress Bars */
QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-weight: 600;
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_ACCENT}, stop:1 #0088FF);
    border-radius: 5px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_COLOR};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {BORDER_HIGHLIGHT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Line Edits & Search Boxes */
QLineEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_COLOR};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QLineEdit:focus {{
    border: 1px solid {COLOR_ACCENT};
}}

/* Checkboxes */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}

QCheckBox::indicator:hover {{
    border-color: {COLOR_ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
    image: url(assets/check.png);
}}
"""
