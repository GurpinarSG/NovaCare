"""
NovaCare System Suite - Disk S.M.A.R.T. & Hardware Health Diagnostics Engine
Queries physical SSD/HDD health, wear percentage, power-on hours, operational status,
temperatures, and bad sector / failure prediction counters via Storage CIM and WMI.
"""
import os
import sys
import json
import subprocess
from dataclasses import dataclass
from typing import Optional
from core.utils import format_bytes, log_debug

@dataclass
class DiskHealthInfo:
    device_id: str
    name: str
    media_type: str        # "SSD", "HDD", "NVMe SSD", etc.
    bus_type: str          # "NVMe", "SATA", "USB", etc.
    drive_letters: str     # "C:", "D:", etc.
    size_bytes: int
    size_str: str
    health_status: str     # "Healthy", "Warning", "Critical"
    health_status_tr: str  # "Mükemmel / Sağlıklı", "Uyarı", "Kritik"
    health_percent: int    # 0 to 100
    temperature_c: Optional[int]
    power_on_hours: Optional[int]
    power_on_days: Optional[int]
    read_errors: Optional[int]
    write_errors: Optional[int]
    bad_sectors_status: str # "Sıfır Hata / Bozuk Sektör Yok", "Hata Tespit Edildi"

class SmartReporter:
    def __init__(self):
        self._cached_results: list[DiskHealthInfo] = []

    def get_disks_health(self, force_refresh: bool = False) -> list[DiskHealthInfo]:
        """
        Gathers S.M.A.R.T. and physical disk health data with timeout safety.
        Returns cached data if recently gathered.
        """
        if self._cached_results and not force_refresh:
            return self._cached_results

        disks: list[DiskHealthInfo] = []
        try:
            ps_code = """
            Get-PhysicalDisk | ForEach-Object {
                $d = $_
                $c = $d | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue
                $letters = ($d | Get-Disk -ErrorAction SilentlyContinue | Get-Partition -ErrorAction SilentlyContinue | Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter } | ForEach-Object { $_.DriveLetter + ":" }) -join ", "
                [PSCustomObject]@{
                    DeviceId = $d.DeviceId
                    FriendlyName = $d.FriendlyName
                    MediaType = $d.MediaType
                    BusType = $d.BusType
                    HealthStatus = $d.HealthStatus
                    OperationalStatus = $d.OperationalStatus
                    Size = $d.Size
                    DriveLetters = $letters
                    Temperature = if ($c) { $c.Temperature } else { $null }
                    Wear = if ($c) { $c.Wear } else { $null }
                    PowerOnHours = if ($c) { $c.PowerOnHours } else { $null }
                    ReadErrorsTotal = if ($c) { $c.ReadErrorsTotal } else { $null }
                    WriteErrorsTotal = if ($c) { $c.WriteErrorsTotal } else { $null }
                }
            } | ConvertTo-Json -Compress
            """
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            cmd = ["powershell", "-NoProfile", "-Command", ps_code]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=12, creationflags=flags)

            if p.returncode == 0 and p.stdout.strip():
                raw_data = json.loads(p.stdout.strip())
                if isinstance(raw_data, dict):
                    raw_data = [raw_data]

                for item in raw_data:
                    dev_id = str(item.get("DeviceId", "0"))
                    name = str(item.get("FriendlyName", "Bilinmeyen Disk")).strip()
                    m_type = str(item.get("MediaType", "Disk")).upper()
                    b_type = str(item.get("BusType", "")).upper()
                    size_b = int(item.get("Size") or 0)
                    letters = str(item.get("DriveLetters") or "").strip()

                    # Clean Media Type Label
                    if b_type == "NVME":
                        full_type = "NVMe SSD"
                    elif "SSD" in m_type:
                        full_type = f"{b_type} SSD" if b_type else "SSD"
                    elif "HDD" in m_type:
                        full_type = f"{b_type} HDD" if b_type else "HDD"
                    else:
                        full_type = f"{m_type} ({b_type})" if b_type else m_type

                    # Health Status & Percentage
                    h_status = str(item.get("HealthStatus", "Healthy")).strip()
                    wear = item.get("Wear")
                    if wear is not None and isinstance(wear, (int, float)):
                        health_pct = max(0, min(100, 100 - int(wear)))
                    else:
                        health_pct = 100 if h_status.lower() == "healthy" else (65 if h_status.lower() == "warning" else 30)

                    if h_status.lower() == "healthy":
                        if health_pct >= 90:
                            h_tr = f"Mükemmel (%{health_pct})"
                        else:
                            h_tr = f"İyi (%{health_pct})"
                    elif h_status.lower() == "warning":
                        h_tr = f"Dikkat / Yıpranma (%{health_pct})"
                    else:
                        h_tr = f"Kritik / Arıza Riski (%{health_pct})"

                    temp = item.get("Temperature")
                    temp_c = int(temp) if temp is not None and isinstance(temp, (int, float)) and temp > 0 else None

                    poh = item.get("PowerOnHours")
                    poh_val = int(poh) if poh is not None and isinstance(poh, (int, float)) and poh >= 0 else None
                    pod_val = round(poh_val / 24.0) if poh_val is not None else None

                    r_err = item.get("ReadErrorsTotal")
                    w_err = item.get("WriteErrorsTotal")
                    r_val = int(r_err) if r_err is not None and isinstance(r_err, (int, float)) else 0
                    w_val = int(w_err) if w_err is not None and isinstance(w_err, (int, float)) else 0

                    if r_val == 0 and w_val == 0:
                        bad_sec = "0 Hata / Sıfır Bozuk Sektör"
                    else:
                        bad_sec = f"Uyarı: {r_val + w_val} okuma/yazma hatası"

                    disks.append(DiskHealthInfo(
                        device_id=dev_id,
                        name=name,
                        media_type=full_type,
                        bus_type=b_type,
                        drive_letters=letters if letters else "Sürücü Harfi Yok",
                        size_bytes=size_b,
                        size_str=format_bytes(size_b),
                        health_status=h_status,
                        health_status_tr=h_tr,
                        health_percent=health_pct,
                        temperature_c=temp_c,
                        power_on_hours=poh_val,
                        power_on_days=pod_val,
                        read_errors=r_val,
                        write_errors=w_val,
                        bad_sectors_status=bad_sec
                    ))
        except Exception as e:
            log_debug(f"SmartReporter error: {e}")

        # Fallback to WMI Win32_DiskDrive if Storage module didn't return any disks
        if not disks:
            disks = self._fallback_wmi_disks()

        self._cached_results = disks
        return disks

    def _fallback_wmi_disks(self) -> list[DiskHealthInfo]:
        """Fallback disk probe using Win32_DiskDrive."""
        disks = []
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            cmd = ["wmic", "diskdrive", "get", "DeviceID,Model,Size,Status,InterfaceType", "/format:csv"]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8, creationflags=flags)
            if p.returncode == 0:
                for line in p.stdout.splitlines():
                    parts = [x.strip() for x in line.split(",") if x.strip()]
                    if len(parts) >= 5 and "DeviceID" not in parts:
                        model = parts[2] if len(parts) > 2 else "Fiziksel Disk"
                        size_str = parts[4] if len(parts) > 4 else "0"
                        status = parts[5] if len(parts) > 5 else "OK"
                        sz = int(size_str) if size_str.isdigit() else 0
                        disks.append(DiskHealthInfo(
                            device_id="0",
                            name=model,
                            media_type="Fiziksel Disk",
                            bus_type="SATA/NVMe",
                            drive_letters="C:",
                            size_bytes=sz,
                            size_str=format_bytes(sz),
                            health_status="Healthy" if status.upper() == "OK" else "Warning",
                            health_status_tr="Mükemmel / Sağlıklı" if status.upper() == "OK" else "Uyarı",
                            health_percent=100 if status.upper() == "OK" else 60,
                            temperature_c=None,
                            power_on_hours=None,
                            power_on_days=None,
                            read_errors=0,
                            write_errors=0,
                            bad_sectors_status="S.M.A.R.T. Durumu: " + status
                        ))
        except Exception:
            pass
        return disks
