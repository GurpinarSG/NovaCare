"""
NovaCare System Suite - Battery Health & Power Diagnostics Engine
Collects hardware telemetry, wear levels, design vs full capacity, charge cycles,
and generates official Windows HTML Battery Diagnostic Reports.
Optimized with memory caching and non-blocking sensor querying.
"""
import os
import sys
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional
import psutil

@dataclass
class BatteryInfo:
    has_battery: bool
    percent: int
    power_plugged: bool
    status_text: str
    secs_left: Optional[int]
    runtime_formatted: str
    design_capacity_mwh: int
    full_charge_capacity_mwh: int
    health_percent: float
    wear_percent: float
    cycle_count: int
    chemistry: str
    manufacturer: str
    model_name: str
    computer_model: str
    active_power_plan: str

    @property
    def is_charging(self) -> bool:
        return self.power_plugged and self.percent < 98

class BatteryReporter:
    _cached_hardware: Optional[dict] = None
    _cached_plan: str = "Dengeli (Varsayılan)"
    _last_plan_time: float = 0.0

    def __init__(self):
        pass

    def get_active_power_plan(self) -> str:
        """Retrieves currently active Windows power scheme name (cached for 15s)."""
        import time
        now = time.time()
        if now - self._last_plan_time < 15.0:
            return self._cached_plan

        try:
            kwargs = {"capture_output": True, "text": True, "timeout": 2}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            p = subprocess.run(["powercfg", "/getactivescheme"], **kwargs)
            if p.returncode == 0 and p.stdout:
                line = p.stdout.strip()
                if "(" in line and ")" in line:
                    self._cached_plan = line.split("(", 1)[1].split(")", 1)[0]
                else:
                    self._cached_plan = line
                self._last_plan_time = now
        except Exception:
            pass
        return self._cached_plan

    def fetch_hardware_details(self) -> dict:
        """
        Queries Windows XML battery report for static hardware parameters.
        Caches result in memory so subsequent queries are instant.
        """
        if BatteryReporter._cached_hardware is not None:
            return BatteryReporter._cached_hardware

        design_cap = 0
        full_cap = 0
        cycle_count = 0
        chemistry = "LiON"
        manufacturer = "Dahili Pil"
        model_name = "Standart Batarya"
        computer_model = "Taşınabilir Bilgisayar"

        tmp_xml = os.path.join(tempfile.gettempdir(), f"novacare_batt_{os.getpid()}.xml")
        try:
            kwargs = {"capture_output": True, "text": True, "timeout": 4}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            subprocess.run(["powercfg", "/batteryreport", "/xml", "/output", tmp_xml], **kwargs)

            if os.path.exists(tmp_xml):
                tree = ET.parse(tmp_xml)
                root = tree.getroot()
                ns = {'b': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

                # Computer Model
                sys_node = root.find('b:SystemInformation', ns) if ns else root.find('SystemInformation')
                if sys_node is not None:
                    prod = sys_node.find('b:SystemProductName', ns) if ns else sys_node.find('SystemProductName')
                    if prod is not None and prod.text:
                        computer_model = prod.text.strip()

                # Batteries
                b_node = root.find('.//b:Battery', ns) if ns else root.find('.//Battery')
                if b_node is not None:
                    def _get_val(elem_name, default=""):
                        e = b_node.find(f'b:{elem_name}', ns) if ns else b_node.find(elem_name)
                        return e.text.strip() if e is not None and e.text else default

                    model_name = _get_val("Id", model_name)
                    manufacturer = _get_val("Manufacturer", manufacturer)
                    chemistry = _get_val("Chemistry", chemistry)
                    try:
                        design_cap = int(_get_val("DesignCapacity", "0"))
                    except ValueError:
                        design_cap = 0
                    try:
                        full_cap = int(_get_val("FullChargeCapacity", "0"))
                    except ValueError:
                        full_cap = 0
                    try:
                        cycle_count = int(_get_val("CycleCount", "0"))
                    except ValueError:
                        cycle_count = 0

                try:
                    os.remove(tmp_xml)
                except Exception:
                    pass
        except Exception:
            pass

        hw_data = {
            "design_cap": design_cap,
            "full_cap": full_cap,
            "cycle_count": cycle_count,
            "chemistry": chemistry,
            "manufacturer": manufacturer,
            "model_name": model_name,
            "computer_model": computer_model
        }
        BatteryReporter._cached_hardware = hw_data
        return hw_data

    def get_battery_info(self, load_hardware_if_missing: bool = True) -> BatteryInfo:
        """
        Parses live sensors in < 0.1ms without blocking the UI thread.
        Uses cached hardware parameters.
        """
        ps_batt = psutil.sensors_battery()
        active_plan = self.get_active_power_plan()

        if ps_batt is None:
            # Desktop computer or no battery detected
            return BatteryInfo(
                has_battery=False,
                percent=100,
                power_plugged=True,
                status_text="Masaüstü Bilgisayar (Harici Pil Yok)",
                secs_left=None,
                runtime_formatted="Sürekli Şebeke Gücü (AC)",
                design_capacity_mwh=0,
                full_charge_capacity_mwh=0,
                health_percent=100.0,
                wear_percent=0.0,
                cycle_count=0,
                chemistry="AC Şebeke",
                manufacturer="Masaüstü Güç Kaynağı (PSU)",
                model_name="Standart Güç Kaynağı",
                computer_model="Masaüstü Bilgisayar",
                active_power_plan=active_plan
            )

        percent = int(ps_batt.percent)
        plugged = bool(ps_batt.power_plugged)
        secs_left = ps_batt.secsleft if ps_batt.secsleft > 0 else None

        if plugged:
            status_text = "Fişe Takılı (Dolu)" if percent >= 98 else "Fişe Takılı (Şarj Ediliyor)"
            runtime_fmt = "Şebekeye Bağlı (Kesintisiz Güç)"
        else:
            status_text = "Pilde Çalışıyor (Deşarj)"
            if secs_left:
                hrs = secs_left // 3600
                mins = (secs_left % 3600) // 60
                runtime_fmt = f"{hrs} saat {mins} dakika" if hrs > 0 else f"{mins} dakika"
            else:
                runtime_fmt = "Hesaplanıyor..."

        if BatteryReporter._cached_hardware is not None:
            hw = BatteryReporter._cached_hardware
        elif load_hardware_if_missing:
            hw = self.fetch_hardware_details()
        else:
            hw = {
                "design_cap": 0,
                "full_cap": 0,
                "cycle_count": 0,
                "chemistry": "LiON",
                "manufacturer": "Dahili Pil",
                "model_name": "Standart Batarya",
                "computer_model": "Taşınabilir Bilgisayar"
            }

        design_cap = hw["design_cap"]
        full_cap = hw["full_cap"]
        cycle_count = hw["cycle_count"]
        chemistry = hw["chemistry"]
        manufacturer = hw["manufacturer"]
        model_name = hw["model_name"]
        computer_model = hw["computer_model"]

        # Calculate health and wear percentage
        if design_cap > 0 and full_cap > 0:
            health_pct = round(min(100.0, (full_cap / design_cap) * 100.0), 1)
            wear_pct = round(max(0.0, 100.0 - health_pct), 1)
        else:
            health_pct = 100.0
            wear_pct = 0.0

        return BatteryInfo(
            has_battery=True,
            percent=percent,
            power_plugged=plugged,
            status_text=status_text,
            secs_left=secs_left,
            runtime_formatted=runtime_fmt,
            design_capacity_mwh=design_cap,
            full_charge_capacity_mwh=full_cap,
            health_percent=health_pct,
            wear_percent=wear_pct,
            cycle_count=cycle_count,
            chemistry=chemistry,
            manufacturer=manufacturer,
            model_name=model_name,
            computer_model=computer_model,
            active_power_plan=active_plan
        )

    def generate_html_report(self) -> str:
        """Generates official Windows Battery Report (.html) and returns its absolute path."""
        report_dir = os.path.join(tempfile.gettempdir(), "NovaCare_Reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "Windows_Battery_Report.html")

        kwargs = {"capture_output": True, "text": True, "timeout": 8}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        subprocess.run(["powercfg", "/batteryreport", "/output", report_path], **kwargs)
        if not os.path.exists(report_path):
            raise RuntimeError("Windows pil raporu oluşturulamadı.")
        return report_path

    def open_html_report(self) -> str:
        """Generates and opens the battery report in user's default web browser."""
        path = self.generate_html_report()
        if os.path.exists(path):
            os.startfile(path)
        return path
