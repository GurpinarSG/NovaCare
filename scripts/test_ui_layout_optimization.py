"""
NovaCare System Suite - Comprehensive UI Layout Optimization & Truncation Verification
Validates responsive widget sizing, boundary constraints, and text visibility across
all views and multiple window resolutions.
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

from PyQt5.QtWidgets import QApplication, QLabel, QFrame
from ui.main_window import MainWindow
from ui.desktop_widget import DesktopPerformanceWidget
from core.smart_reporter import DiskHealthInfo
from core.battery_reporter import BatteryInfo

app = QApplication.instance() or QApplication(sys.argv)
mw = MainWindow()
mw.show()
app.processEvents()

mock_disks = [
    DiskHealthInfo(
        device_id="0",
        name="Samsung SSD 980 PRO with Heatsink 1TB NVMe PCIe 4.0",
        media_type="SSD (NVMe)",
        bus_type="NVMe",
        drive_letters="C:, D:",
        size_bytes=1000204886016,
        size_str="931.5 GB",
        health_status="Healthy",
        health_status_tr="Mükemmel",
        health_percent=98,
        temperature_c=42,
        power_on_hours=5420,
        power_on_days=225,
        read_errors=0,
        write_errors=0,
        bad_sectors_status="0 Hata / Sıfır Bozuk Sektör",
        operational_status="OK"
    ),
    DiskHealthInfo(
        device_id="1",
        name="Seagate BarraCuda 2TB HDD Internal SATA 6Gb/s 7200 RPM Enterprise Storage",
        media_type="HDD",
        bus_type="SATA",
        drive_letters="E:",
        size_bytes=2000398934016,
        size_str="1.81 TB",
        health_status="Warning",
        health_status_tr="Dikkat",
        health_percent=78,
        temperature_c=52,
        power_on_hours=24500,
        power_on_days=1020,
        read_errors=16,
        write_errors=0,
        bad_sectors_status="16 Yeniden Tahsis Edilmiş Sektör",
        operational_status="Degraded / PredFail"
    )
]

mock_battery = BatteryInfo(
    has_battery=True,
    percent=82,
    power_plugged=True,
    status_text="Şarj Oluyor",
    secs_left=7200,
    runtime_formatted="2 saat 0 dk",
    design_capacity_mwh=56000,
    full_charge_capacity_mwh=52400,
    health_percent=93.6,
    wear_percent=6.4,
    cycle_count=184,
    chemistry="LION",
    manufacturer="SMP-SDI4.9",
    model_name="Primary Battery",
    computer_model="ASUSTeK COMPUTER INC. ROG Strix G16 G614JV_G614JV",
    active_power_plan="Dengeli"
)

test_resolutions = [
    (940, 580, "Minimum Screen Resolution"),
    (1180, 720, "Default Window Resolution"),
    (1366, 768, "Standard Laptop Resolution"),
    (1920, 1080, "Full HD Desktop Resolution")
]

all_truncations = []

for w, h, label in test_resolutions:
    mw.resize(w, h)
    app.processEvents()
    print(f"\n================ Testing {label}: {w}x{h} ================")

    # 1. Test General Health View in depth
    mw._on_nav_clicked(9)
    gh = mw.view_general_health
    gh.set_sub_tab(0)
    app.processEvents()
    hw = gh.view_hardware
    hw._render_disk_cards(mock_disks)
    app.processEvents()

    print(f"✓ GeneralHealthView: width={gh.width()}, HardwareHealthView: width={hw.width()}")

    # Check Disk Cards fitting inside HardwareHealthView
    for i in range(hw.disks_container.count()):
        item = hw.disks_container.itemAt(i)
        if item and item.widget():
            dw = item.widget()
            diff = dw.width() - hw.width()
            assert diff <= 4, f"Disk card {i} overflows container by {diff}px (card={dw.width()}, parent={hw.width()})"
            assert dw.height() >= 190, f"Disk card {i} is squashed: height {dw.height()}px < 190px"
            print(f"  ✓ DiskCard [{i}] fits safely: {dw.width()}x{dw.height()}px")

            # Check individual metric tiles and labels
            for f in dw.findChildren(QFrame):
                if f.objectName() == "MetricTile":
                    assert f.height() >= 50, f"Metric tile is vertically squashed: {f.height()}px < 50px"
                    for lbl in f.findChildren(QLabel):
                        assert lbl.height() >= 14, f"Metric tile label '{lbl.text()[:20]}' squashed: height={lbl.height()}px < 14px"

            # Check individual labels for truncation
            for lbl in dw.findChildren(QLabel):
                if lbl.text() and not lbl.wordWrap():
                    hint_w = lbl.sizeHint().width()
                    if lbl.width() < (hint_w - 6):
                        all_truncations.append(f"[{w}x{h}] DiskCard lbl '{lbl.text()[:30]}' width={lbl.width()} < hint={hint_w}")

    # Check Hardware StatCards
    for name, card in [("CPU", hw.card_cpu), ("GPU", hw.card_gpu), ("RAM", hw.card_ram), ("Power", hw.card_power)]:
        if card.isVisible():
            assert card.width() >= 120, f"StatCard {name} too narrow: {card.width()}px"
            assert card.height() >= 70, f"StatCard {name} too short: {card.height()}px"
            print(f"  ✓ StatCard [{name}] geometry: {card.width()}x{card.height()} (wordWrap={card.sub_lbl.wordWrap()})")

    # Check Battery View subtab
    if gh.has_battery and gh.view_battery:
        gh.set_sub_tab(1)
        app.processEvents()
        bv = gh.view_battery
        bv.last_info = mock_battery
        bv.card_charge.set_value(f"%{mock_battery.percent}", mock_battery.status_text)
        bv.card_health.set_value(f"%{mock_battery.health_percent:.1f}", f"Aşınma: %{mock_battery.wear_percent:.1f}")
        bv.card_capacity.set_value(f"{mock_battery.full_charge_capacity_mwh:,} mWh", f"Tasarım: {mock_battery.design_capacity_mwh:,} mWh")
        bv.card_hardware.set_value(mock_battery.manufacturer, mock_battery.model_name)
        bv.lbl_info_plan.setText(f"⚡ Aktif Güç Planı: <b>{mock_battery.active_power_plan}</b>")
        bv.lbl_info_cycle.setText(f"🔄 Şarj Döngü Sayısı: <b>{mock_battery.cycle_count} döngü</b>")
        bv.lbl_info_mfg.setText(f"🏭 Üretici & Model: <b>{mock_battery.manufacturer} {mock_battery.model_name}</b>")
        bv.lbl_info_chem.setText(f"🧪 Kimya / Cihaz: <b>{mock_battery.chemistry} ({mock_battery.computer_model})</b>")
        app.processEvents()

        print(f"  ✓ BatteryView: width={bv.width()}x{bv.height()}")
        for lbl in (bv.lbl_info_plan, bv.lbl_info_cycle, bv.lbl_info_mfg, bv.lbl_info_chem):
            assert lbl.wordWrap(), f"Battery parameter label missing wordWrap: {lbl.text()}"

    # Navigate to all tabs and ensure views render without geometry errors
    for idx in range(mw.stack.count()):
        mw._on_nav_clicked(idx)
        app.processEvents()
        view = mw.stack.currentWidget()
        assert view.width() > 0 and view.height() > 0, f"Tab {idx} has invalid geometry: {view.size()}"

print(f"\n✓ All {mw.stack.count()} main views validated across 4 resolutions.")

# 2. Test DesktopPerformanceWidget
print("\n================ Testing DesktopPerformanceWidget ================")
dw = DesktopPerformanceWidget()
dw.show()
app.processEvents()

for mode in ["card", "horizontal", "vertical"]:
    dw.config.set("desktop_widget_layout", mode)
    dw._init_ui()
    app.processEvents()
    assert dw.width() > 0 and dw.height() > 0, f"Desktop widget in mode {mode} has invalid geometry"
    print(f"✓ DesktopPerformanceWidget mode '{mode}': {dw.width()}x{dw.height()}")

dw.close()

# Cleanup MainWindow
mw.cleanup_workers()
mw.close()
app.processEvents()

if all_truncations:
    print(f"\n❌ Truncation warnings detected ({len(all_truncations)}):")
    for t in all_truncations:
        print(f"  - {t}")
    sys.exit(1)

print("\n>>> ALL UI LAYOUT & TEXT VISIBILITY TESTS PASSED WITH 0 TRUNCATIONS! <<<")
sys.stdout.flush()
os._exit(0)
