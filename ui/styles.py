"""
NovaCare System Suite - Theme, Palettes and Stylesheets (QSS)
Modern Windows 11 Dark Fluent Aesthetic with Cyber-Cyan & Emerald Accents.
"""

# Color Constants (High-Contrast Slate / Deep Navy Modern Fluent Palette)
BG_DARK = "#0B0F19"              # Deep navy base window background
BG_SIDEBAR = "#0F172A"           # Rich slate-900 sidebar
BG_CARD = "#1E293B"              # Clean slate-800 card & panel surface
BG_CARD_HOVER = "#27354E"        # Interactive hover card state
BG_INPUT = "#1E293B"             # Solid input background
BORDER_COLOR = "#334155"         # Clearly visible slate border (1px solid)
BORDER_HIGHLIGHT = "#475569"     # Focused/hovered border

COLOR_ACCENT = "#38BDF8"         # Vivid Sky Cyan (High readability)
COLOR_ACCENT_HOVER = "#0EA5E9"
COLOR_SUCCESS = "#34D399"        # Vivid Emerald Green
COLOR_WARNING = "#FBBF24"        # Bright Amber
COLOR_DANGER = "#F87171"         # Vivid Coral Red
COLOR_PURPLE = "#A78BFA"         # Light Lavender

TEXT_PRIMARY = "#FFFFFF"         # Pure White (15.8:1 contrast on BG_CARD)
TEXT_SECONDARY = "#CBD5E1"       # Light Slate (10.4:1 contrast - WCAG AAA compliant)
TEXT_MUTED = "#94A3B8"           # Crisp Muted Slate (6.5:1 contrast - passes WCAG AA)

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
    font-weight: 800;
    color: {COLOR_ACCENT};
    letter-spacing: 0.5px;
}}

#SidebarSubtitle {{
    font-size: 11px;
    color: {TEXT_MUTED};
    font-weight: 600;
    letter-spacing: 1px;
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
    background-color: rgba(56, 189, 248, 0.16);
    color: {COLOR_ACCENT};
    font-weight: 700;
    border-left: 3px solid {COLOR_ACCENT};
}}

/* Content Header */
#ViewTitle {{
    font-size: 22px;
    font-weight: 800;
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
    color: #041326;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.primary-btn:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

QPushButton.primary-btn:disabled {{
    background-color: #334155;
    color: #64748B;
}}

QPushButton.success-btn {{
    background-color: {COLOR_SUCCESS};
    color: #022C1B;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
}}

QPushButton.success-btn:hover {{
    background-color: #10B981;
}}

QPushButton.danger-btn {{
    background-color: #EF4444;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 13px;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton.danger-btn:hover {{
    background-color: #DC2626;
}}

QPushButton.secondary-btn {{
    background-color: {BG_CARD};
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLOR_ACCENT}, stop:1 #0284C7);
    color: #041326;
    font-size: 17px;
    font-weight: 800;
    border: none;
    border-radius: 30px;
    padding: 16px 42px;
    letter-spacing: 0.5px;
}}

QPushButton#BigScanBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7DD3FC, stop:1 #0369A1);
}}

QPushButton#BigFixBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLOR_SUCCESS}, stop:1 #059669);
    color: #022C1B;
    font-size: 17px;
    font-weight: 800;
    border: none;
    border-radius: 30px;
    padding: 16px 42px;
    letter-spacing: 0.5px;
}}

QPushButton#BigFixBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6EE7B7, stop:1 #047857);
}}

/* Table Views */
QTableWidget, QTreeWidget, QListWidget {{
    background-color: {BG_CARD};
    alternate-background-color: #162032;
    border: 1px solid {BORDER_COLOR};
    border-radius: 10px;
    gridline-color: {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: rgba(56, 189, 248, 0.28);
    selection-color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {BG_SIDEBAR};
    color: {TEXT_SECONDARY};
    padding: 10px 10px;
    border: none;
    border-bottom: 2px solid {BORDER_COLOR};
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
    background-color: #0F172A;
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-weight: 700;
    font-size: 11px;
    height: 18px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_ACCENT}, stop:1 #2563EB);
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
