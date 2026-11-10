"""
Automated Test Suite for NovaCare UI/UX, Design System, Contrast & Accessibility Fixes
Validates:
1. WCAG 2.1 AA Contrast Tokens in Light and Dark Themes.
2. CircularHealthGauge Threshold Synchronization across tiers and boundaries.
3. Disabled Button States and Styling in QSS for both themes.
4. Navigation Button Jitter Prevention (3px transparent border).
5. All 12 Stacked View Root Margins consistency (24, 20, 24, 20).
6. Desktop Widget Minimal White preset contrast and valid QSS hover transitions.
7. Disk Analyzer and Duplicate Finder Empty State row resets.
8. Table Header Sort Arrow definitions and asset availability.
9. Privacy View badge text and contrast safety.
"""
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication, QScrollArea, QTableWidgetItem
from PyQt5.QtCore import Qt
from ui.styles import get_active_theme_colors, get_stylesheet, COLOR_WARNING, sync_theme_globals
from ui.components import CircularHealthGauge
from ui.desktop_widget import THEME_PRESETS, DesktopPerformanceWidget
from ui.main_window import MainWindow
import ui.views.startup_view as startup_view

passed = 0
failed = 0

def assert_true(condition, msg):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {msg}")
    else:
        failed += 1
        print(f"  [FAIL] {msg}")

def calculate_luminance(hex_code):
    h = hex_code.lstrip('#')
    r, g, b = [int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
    def adjust(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)

def contrast_ratio(hex1, hex2):
    l1 = calculate_luminance(hex1)
    l2 = calculate_luminance(hex2)
    top = max(l1, l2) + 0.05
    bot = min(l1, l2) + 0.05
    return top / bot

print("=" * 70)
print("TEST 1: WCAG Contrast Tokens Validation (Light & Dark)")
print("=" * 70)

dark_colors = get_active_theme_colors(theme_mode="dark")
light_colors = get_active_theme_colors(theme_mode="light")

# Dark Mode Primary Text vs Background
dark_cr_primary = contrast_ratio(dark_colors["TEXT_PRIMARY"], dark_colors["BG_DARK"])
dark_cr_secondary = contrast_ratio(dark_colors["TEXT_SECONDARY"], dark_colors["BG_DARK"])
assert_true(dark_cr_primary >= 7.0, f"Dark Theme TEXT_PRIMARY contrast ({dark_cr_primary:.2f}:1) >= 7.0:1")
assert_true(dark_cr_secondary >= 4.5, f"Dark Theme TEXT_SECONDARY contrast ({dark_cr_secondary:.2f}:1) >= 4.5:1 (WCAG AA)")

# Light Mode Primary & Secondary Text vs Light Background & Cards
light_cr_primary = contrast_ratio(light_colors["TEXT_PRIMARY"], light_colors["BG_DARK"])
light_cr_secondary = contrast_ratio(light_colors["TEXT_SECONDARY"], light_colors["BG_DARK"])
light_cr_primary_card = contrast_ratio(light_colors["TEXT_PRIMARY"], light_colors["BG_CARD"])
light_cr_secondary_card = contrast_ratio(light_colors["TEXT_SECONDARY"], light_colors["BG_CARD"])
assert_true(light_cr_primary >= 7.0, f"Light Theme TEXT_PRIMARY contrast on BG_DARK ({light_cr_primary:.2f}:1) >= 7.0:1")
assert_true(light_cr_secondary >= 4.5, f"Light Theme TEXT_SECONDARY contrast on BG_DARK ({light_cr_secondary:.2f}:1) >= 4.5:1 (WCAG AA)")
assert_true(light_cr_primary_card >= 7.0, f"Light Theme TEXT_PRIMARY contrast on BG_CARD ({light_cr_primary_card:.2f}:1) >= 7.0:1")
assert_true(light_cr_secondary_card >= 4.5, f"Light Theme TEXT_SECONDARY contrast on BG_CARD ({light_cr_secondary_card:.2f}:1) >= 4.5:1 (WCAG AA)")

# Button Text Tokens WCAG Contrast (Primary, Success, Danger, Warning)
for mode, colors in [("Dark", dark_colors), ("Light", light_colors)]:
    cr_prim = contrast_ratio(colors["BTN_PRIMARY_TEXT"], colors["COLOR_ACCENT"])
    cr_succ = contrast_ratio(colors["BTN_SUCCESS_TEXT"], colors["COLOR_SUCCESS"])
    cr_dang = contrast_ratio(colors["BTN_DANGER_TEXT"], colors["COLOR_DANGER"])
    cr_warn = contrast_ratio(colors["BTN_WARNING_TEXT"], colors["COLOR_WARNING"])
    assert_true(cr_prim >= 4.5, f"[{mode}] BTN_PRIMARY_TEXT contrast on COLOR_ACCENT ({cr_prim:.2f}:1) >= 4.5:1")
    assert_true(cr_succ >= 4.5, f"[{mode}] BTN_SUCCESS_TEXT contrast on COLOR_SUCCESS ({cr_succ:.2f}:1) >= 4.5:1")
    assert_true(cr_dang >= 4.5, f"[{mode}] BTN_DANGER_TEXT contrast on COLOR_DANGER ({cr_dang:.2f}:1) >= 4.5:1")
    assert_true(cr_warn >= 4.5, f"[{mode}] BTN_WARNING_TEXT contrast on COLOR_WARNING ({cr_warn:.2f}:1) >= 4.5:1")

# Minimal White Desktop Widget Button Contrast
mw_bg = THEME_PRESETS["minimal_white"]["btn_bg"]
mw_text = THEME_PRESETS["minimal_white"]["btn_text"]
mw_cr = contrast_ratio(mw_text, mw_bg)
assert_true(mw_cr >= 4.5, f"Desktop widget minimal_white button contrast ({mw_cr:.2f}:1) >= 4.5:1")
assert_true(mw_text.upper() in ["#0F172A", "#000000"], f"Desktop widget minimal_white uses dark text: {mw_text}")

# Privacy Warning Button Dark Mode Contrast (#041326 on #F59E0B)
warn_btn_cr = contrast_ratio("#041326", COLOR_WARNING)
assert_true(warn_btn_cr >= 4.5, f"Privacy View warning button text contrast on amber ({warn_btn_cr:.2f}:1) >= 4.5:1")

print("\n" + "=" * 70)
print("TEST 2: CircularHealthGauge Threshold Synchronization")
print("=" * 70)

test_scores = [
    (100, "Mükemmel", "COLOR_SUCCESS"),
    (85, "Mükemmel", "COLOR_SUCCESS"),
    (84, "İyi", "COLOR_ACCENT"),
    (65, "İyi", "COLOR_ACCENT"),
    (64, "Bakım Önerilir", "COLOR_WARNING"),
    (40, "Bakım Önerilir", "COLOR_WARNING"),
    (39, "Kritik", "COLOR_DANGER"),
    (0, "Kritik", "COLOR_DANGER"),
    (-10, "Kritik", "COLOR_DANGER"),
    (110, "Mükemmel", "COLOR_SUCCESS")
]

for score, exp_text, exp_color_key in test_scores:
    text, color_key = CircularHealthGauge.get_tier_info(score)
    assert_true(text == exp_text and color_key == exp_color_key,
                f"Score {score} correctly mapped to '{text}' ({color_key})")

print("\n" + "=" * 70)
print("TEST 3: Stylesheet Rules (Disabled States, Jitter, Sort Arrows)")
print("=" * 70)

for theme_name in ["dark", "light"]:
    qss = get_stylesheet(theme_name)
    assert_true("QPushButton.primary-btn" in qss and ".primary-btn" in qss, f"[{theme_name}] .primary-btn dual selector defined")
    assert_true("QPushButton.success-btn:disabled" in qss, f"[{theme_name}] QPushButton.success-btn:disabled defined")
    assert_true("QPushButton.danger-btn:disabled" in qss, f"[{theme_name}] QPushButton.danger-btn:disabled defined")
    assert_true("QPushButton.warning-btn:disabled" in qss, f"[{theme_name}] QPushButton.warning-btn:disabled defined")
    assert_true("QPushButton.secondary-btn:disabled" in qss, f"[{theme_name}] QPushButton.secondary-btn:disabled defined")
    
    # Verify secondary disabled uses muted border color (not white BG_INPUT)
    p = dark_colors if theme_name == "dark" else light_colors
    assert_true(f"background-color: {p['BORDER_COLOR']};" in qss, f"[{theme_name}] secondary-btn:disabled uses muted border color ({p['BORDER_COLOR']})")
    
    assert_true("border-left: 3px solid transparent;" in qss, f"[{theme_name}] .nav-btn has 3px solid transparent border (prevents jitter)")
    assert_true("QHeaderView::down-arrow" in qss, f"[{theme_name}] QHeaderView::down-arrow defined")
    assert_true("QHeaderView::up-arrow" in qss, f"[{theme_name}] QHeaderView::up-arrow defined")
    assert_true(".text-secondary" in qss, f"[{theme_name}] .text-secondary class defined")
    assert_true("#TextSecondary" in qss, f"[{theme_name}] #TextSecondary selector defined")
    assert_true(".text-accent" in qss and "#TextAccent" in qss, f"[{theme_name}] .text-accent and #TextAccent defined")
    assert_true(".text-success" in qss and "#TextSuccess" in qss, f"[{theme_name}] .text-success and #TextSuccess defined")
    assert_true(".text-warning" in qss and "#TextWarning" in qss, f"[{theme_name}] .text-warning and #TextWarning defined")
    assert_true(".text-danger" in qss and "#TextDanger" in qss, f"[{theme_name}] .text-danger and #TextDanger defined")
    assert_true("#AdminBannerSuccess" in qss and "#AdminBannerWarning" in qss, f"[{theme_name}] AdminBanner styles defined")

# Check Asset Existence for Sort Arrows
assets_dir = os.path.join(root_dir, "assets")
for arrow_file in ["arrow_down_white.png", "arrow_up_white.png", "arrow_down_dark.png", "arrow_up_dark.png"]:
    file_path = os.path.join(assets_dir, arrow_file)
    assert_true(os.path.isfile(file_path), f"Sort arrow asset exists: {arrow_file}")

print("\n" + "=" * 70)
print("TEST 4: Desktop Widget Hover & Style Rules")
print("=" * 70)

app = QApplication.instance() or QApplication(sys.argv)
dw = DesktopPerformanceWidget()

# Verify no invalid opacity in desktop widget stylesheet
for preset_key in THEME_PRESETS.keys():
    dw.config.set("desktop_widget_theme", preset_key)
    dw._apply_appearance()
    sheet = dw.card.styleSheet()
    assert_true("opacity:" not in sheet, f"Preset '{preset_key}' stylesheet contains no invalid 'opacity:' rule")
    assert_true("QPushButton:hover" in sheet, f"Preset '{preset_key}' stylesheet has QPushButton:hover rule")

# Check extreme pure black hover edge case (#000000)
dw.config.set("desktop_widget_theme", "custom_rgb")
dw.config.set("desktop_widget_custom_color", "#000000")
dw._apply_appearance()
sheet_black = dw.card.styleSheet()
assert_true("background-color: #262626;" in sheet_black, "Desktop widget pure black background raises hover to visible #262626")
assert_true("background-color: #000000;" not in sheet_black.split("QPushButton:hover")[1], "Desktop widget hover is not black on black")

dw.close()

print("\n" + "=" * 70)
print("TEST 5: All 12 MainWindow Views Content Alignment & Margins Consistency")
print("=" * 70)

mw = MainWindow()
mw.show()
app.processEvents()

expected_margins = (24, 20, 24, 20)
views_to_check = [
    ("Dashboard", mw.view_dashboard),
    ("Junk Cleaner", mw.view_junk),
    ("Registry Cleaner", mw.view_registry),
    ("Disk Analyzer", mw.view_disk),
    ("Startup Manager", mw.view_startup),
    ("Uninstaller", mw.view_uninstaller),
    ("Memory & CPU", mw.view_memory),
    ("Network Optimizer", mw.view_network),
    ("General Health", mw.view_general_health),
    ("Privacy & Shield", mw.view_privacy),
    ("Rescue Center", mw.view_rescue),
    ("Settings", mw.view_settings)
]

def get_effective_content_margins(view):
    # If the root layout has margins, that defines the page boundary
    if view.layout():
        m = view.layout().contentsMargins()
        if (m.left(), m.top(), m.right(), m.bottom()) != (0, 0, 0, 0):
            return (m.left(), m.top(), m.right(), m.bottom())
    # If the root layout is (0,0,0,0) due to full-view QScrollArea, check inner content layout
    for child in view.children():
        if isinstance(child, QScrollArea):
            w = child.widget()
            if w and w.layout():
                m = w.layout().contentsMargins()
                return (m.left(), m.top(), m.right(), m.bottom())
    if view.layout():
        m = view.layout().contentsMargins()
        return (m.left(), m.top(), m.right(), m.bottom())
    return None

for name, view in views_to_check:
    actual = get_effective_content_margins(view)
    assert_true(actual is not None, f"View '{name}' has a valid content layout")
    if actual:
        assert_true(actual == expected_margins, f"View '{name}' effective content margins == {expected_margins} (actual: {actual})")

print("\n" + "=" * 70)
print("TEST 6: Disk Analyzer & Duplicate Finder Empty State Reset")
print("=" * 70)

# Simulate empty filter on Disk Analyzer table
disk_view = mw.view_disk
disk_view.table.setRowCount(5)
assert_true(disk_view.table.rowCount() == 5, "Disk view table seeded with 5 rows")
disk_view._on_scan_finished([])
assert_true(disk_view.table.rowCount() == 0, "Disk view table reset to 0 rows on empty list")
assert_true("bulunamadı" in disk_view.lbl_status.text(), "Disk view status informs user when 0 files match")

# Simulate empty filter on Duplicate Finder table
disk_view.dup_table.setRowCount(5)
assert_true(disk_view.dup_table.rowCount() == 5, "Duplicate view table seeded with 5 rows")
disk_view._on_dup_finished([])
assert_true(disk_view.dup_table.rowCount() == 0, "Duplicate view table reset to 0 rows on empty list")
assert_true("bulunamadı" in disk_view.lbl_dup_status.text(), "Duplicate view status informs user when 0 groups match")

print("\n" + "=" * 70)
print("TEST 7: Privacy Shield Badge Semantics Check")
print("=" * 70)

# Check privacy view source code for anti-spy badge text
privacy_file = os.path.join(root_dir, "ui", "views", "privacy_view.py")
with open(privacy_file, "r", encoding="utf-8") as f:
    priv_code = f.read()

assert_true("🛡️ Korumada (Engellendi)" in priv_code, "Privacy view uses clear '🛡️ Korumada (Engellendi)' badge")
assert_true("⚠️ Varsayılan (İzin Verildi)" in priv_code, "Privacy view uses clear '⚠️ Varsayılan (İzin Verildi)' badge")
assert_true("Cortana'yı Devre Dışı Bırak" in priv_code or "telemetry" in priv_code.lower(), "Privacy rules present")

print("\n" + "=" * 70)
print("TEST 8: Dynamic Module Theme Synchronization (sync_theme_globals)")
print("=" * 70)

sync_theme_globals("light")
import ui.styles as ui_styles
assert_true(ui_styles.TEXT_PRIMARY == "#0F172A", "sync_theme_globals('light') dynamically updated ui.styles.TEXT_PRIMARY to #0F172A")
assert_true(startup_view.COLOR_WARNING == "#B45309", "sync_theme_globals('light') dynamically updated startup_view.COLOR_WARNING to #B45309")
assert_true(startup_view.COLOR_SUCCESS == "#047857", "sync_theme_globals('light') dynamically updated startup_view.COLOR_SUCCESS to #047857")

sync_theme_globals("dark")
assert_true(ui_styles.TEXT_PRIMARY == "#FFFFFF", "sync_theme_globals('dark') dynamically reverted ui.styles.TEXT_PRIMARY to #FFFFFF")
assert_true(startup_view.COLOR_WARNING == "#FCD34D", "sync_theme_globals('dark') dynamically reverted startup_view.COLOR_WARNING to #FCD34D")
assert_true(startup_view.COLOR_SUCCESS == "#34D399", "sync_theme_globals('dark') dynamically reverted startup_view.COLOR_SUCCESS to #34D399")

print("\n" + "=" * 70)
print("TEST 9: Disk Analyzer Table Natural Numeric Sorting")
print("=" * 70)

assert_true(disk_view.table.isSortingEnabled(), "Disk view table sorting is enabled")
assert_true(disk_view.dup_table.isSortingEnabled(), "Duplicate view table sorting is enabled")

# Verify size numeric sorting vs alphabetical
disk_view.table.setSortingEnabled(False)
disk_view.table.setRowCount(2)
item_small_name = QTableWidgetItem("file_small.bin")
item_small_size = QTableWidgetItem("50 MB")
item_small_size.setData(Qt.DisplayRole, "50 MB")
item_small_size.setData(Qt.EditRole, 50 * 1024 * 1024)
disk_view.table.setItem(0, 0, item_small_name)
disk_view.table.setItem(0, 1, item_small_size)

item_big_name = QTableWidgetItem("file_big.bin")
item_big_size = QTableWidgetItem("2 GB")
item_big_size.setData(Qt.DisplayRole, "2 GB")
item_big_size.setData(Qt.EditRole, 2 * 1024 * 1024 * 1024)
disk_view.table.setItem(1, 0, item_big_name)
disk_view.table.setItem(1, 1, item_big_size)

disk_view.table.setSortingEnabled(True)
# Sort ascending by size column (index 1): 50 MB should be first, 2 GB should be second
disk_view.table.sortItems(1, Qt.AscendingOrder)
assert_true(disk_view.table.item(0, 0).text() == "file_small.bin", "Numeric sort ascending: 50 MB precedes 2 GB")

# Sort descending by size column: 2 GB should be first, 50 MB should be second
disk_view.table.sortItems(1, Qt.DescendingOrder)
assert_true(disk_view.table.item(0, 0).text() == "file_big.bin", "Numeric sort descending: 2 GB precedes 50 MB")
disk_view.table.setRowCount(0)

print("\n" + "=" * 70)
print("TEST 10: Dynamic Sidebar Admin Badge Theme Updating")
print("=" * 70)

mw.apply_theme("light")
admin_card_sheet_light = mw.admin_card.styleSheet()
admin_lbl_sheet_light = mw.lbl_admin.styleSheet()
assert_true("#FEF3C7" in admin_card_sheet_light or "#ECFDF5" in admin_card_sheet_light, "Light mode admin card has light background")
assert_true("#B45309" in admin_lbl_sheet_light or "#047857" in admin_lbl_sheet_light, "Light mode admin badge text uses dark accessible amber/green")
light_admin_cr = contrast_ratio("#047857", "#ECFDF5") if "#047857" in admin_lbl_sheet_light else contrast_ratio("#B45309", "#FEF3C7")
assert_true(light_admin_cr >= 4.5, f"Light mode admin badge text contrast ({light_admin_cr:.2f}:1) >= 4.5:1")

mw.apply_theme("dark")
admin_card_sheet_dark = mw.admin_card.styleSheet()
admin_lbl_sheet_dark = mw.lbl_admin.styleSheet()
assert_true("rgba(" in admin_card_sheet_dark, "Dark mode admin card uses semi-transparent dark container")
assert_true("#FCD34D" in admin_lbl_sheet_dark or "#34D399" in admin_lbl_sheet_dark, "Dark mode admin badge text uses bright accessible amber/green")

mw.cleanup_workers()
mw.close()
app.processEvents()

print("\n" + "=" * 70)
print(f"DESIGN SYSTEM FIXES TEST SUMMARY: {passed} PASSED, {failed} FAILED")
print("=" * 70)

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
