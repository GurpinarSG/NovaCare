"""
NovaCare System Suite - Bloatware Cleaner & Deep Telemetry Shield
Detects and uninstalls pre-installed Windows bloatware packages and shuts down
deep Windows telemetry services and background tracking.
"""
import os
import json
import subprocess
import winreg
from dataclasses import dataclass
from typing import Callable, Optional
from core.utils import log_debug

@dataclass
class BloatwareItem:
    package_name: str
    display_name: str
    description: str
    category: str
    installed: bool = False
    full_name: str = ""

KNOWN_BLOATWARE = [
    BloatwareItem(
        package_name="Microsoft.BingWeather",
        display_name="Bing Hava Durumu",
        description="Arka planda konum ve internet kullanarak hava durumu bildirimleri sunar.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Microsoft.BingNews",
        display_name="Bing Haberler & Finans",
        description="Sistem kaynaklarını kullanarak haber ve borsa akışı çeker.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Microsoft.XboxGamingOverlay",
        display_name="Xbox Game Bar",
        description="Oyunlar sırasında tuş kombinasyonlarını dinler ve arka planda bellek tüketir.",
        category="Oyun & Medya"
    ),
    BloatwareItem(
        package_name="Microsoft.549981C3F5F10",
        display_name="Cortana Asistanı",
        description="Artık kullanılmayan ve arka planda telemetri çalıştıran eski Windows sesli asistanı.",
        category="Telemetri & Asistan"
    ),
    BloatwareItem(
        package_name="Microsoft.GetHelp",
        display_name="Yardım Alın",
        description="Genellikle internet aramalarına yönlendiren Windows destek uygulaması.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Microsoft.Getstarted",
        display_name="Windows İpuçları (Başlarken)",
        description="Yeni kullanıcılar için ipucu pencereleri açan başlangıç rehberi.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Microsoft.MicrosoftSolitaireCollection",
        display_name="Microsoft Solitaire Collection",
        description="İçerisinde reklamlar barındıran sponsorlu kart oyunları koleksiyonu.",
        category="Oyun & Medya"
    ),
    BloatwareItem(
        package_name="Microsoft.YourPhone",
        display_name="Telefon Bağlantısı (Your Phone)",
        description="Telefon senkronizasyonu yapmıyorsanız arka planda boşuna çalışan senkronizasyon servisi.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Microsoft.People",
        display_name="Microsoft Kişiler",
        description="Kullanılmayan Windows adres defteri ve kişi entegrasyonu.",
        category="Gereksiz Araçlar"
    ),
    BloatwareItem(
        package_name="Clipchamp.Clipchamp",
        display_name="Clipchamp Video Düzenleyici",
        description="Windows ile gelen abonelik tabanlı çevrimiçi video düzenleme aracı.",
        category="Oyun & Medya"
    )
]

TELEMETRY_SERVICES = [
    ("DiagTrack", "Bağlı Kullanıcı Deneyimleri ve Telemetri"),
    ("dmwappushservice", "WAP Gönderimi İleti Yönlendirme"),
    ("diagnosticshub.standardcollector.service", "Microsoft Diagnostics Hub Standard Collector")
]

class BloatwareCleaner:
    def __init__(self):
        pass

    def scan_installed_bloatware(self) -> list[BloatwareItem]:
        """
        Scans for pre-installed bloatware packages from the known list.
        Optimized by filtering target names directly in PowerShell query (<0.4s).
        """
        installed_map = {}
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            pkg_names = ",".join(f"'{item.package_name}'" for item in KNOWN_BLOATWARE)
            cmd = [
                "powershell", "-NoProfile", "-Command",
                f"Get-AppxPackage -Name {pkg_names} -ErrorAction SilentlyContinue | Select-Object -Property Name, PackageFullName | ConvertTo-Json -Compress"
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8, creationflags=flags)
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        n = item.get("Name", "")
                        fn = item.get("PackageFullName", "")
                        if n:
                            installed_map[n.lower()] = fn
                except Exception:
                    for line in p.stdout.splitlines():
                        parts = line.strip().split()
                        if parts:
                            installed_map[parts[0].lower()] = parts[-1]
        except Exception as e:
            log_debug(f"BloatwareCleaner scan error: {e}")

        results: list[BloatwareItem] = []
        for item in KNOWN_BLOATWARE:
            target_key = item.package_name.lower()
            is_inst = target_key in installed_map
            full_n = installed_map.get(target_key, "")
            results.append(BloatwareItem(
                package_name=item.package_name,
                display_name=item.display_name,
                description=item.description,
                category=item.category,
                installed=is_inst,
                full_name=full_n
            ))

        return results

    def remove_bloatware_package(self, package_name: str) -> tuple[bool, str]:
        """Uninstalls a specific AppX package."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            ps_cmd = (
                f"Get-AppxPackage -Name '{package_name}' -AllUsers -ErrorAction SilentlyContinue | Remove-AppxPackage -ErrorAction SilentlyContinue; "
                f"Get-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue | Where-Object DisplayName -eq '{package_name}' | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue"
            )
            p = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=30, creationflags=flags)
            if p.returncode == 0:
                return True, "Uygulama başarıyla kaldırıldı."
            return False, p.stderr or "Kaldırma başarısız oldu."
        except Exception as e:
            return False, str(e)

    def disable_deep_telemetry(self) -> dict:
        """
        Stops and disables Windows Telemetry services and enforces
        strict telemetry blocking in Windows Registry policies.
        """
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        disabled_services = []
        registry_applied = []

        # 1. Stop and disable telemetry services
        for svc_name, friendly in TELEMETRY_SERVICES:
            try:
                # Stop service
                subprocess.run(["net", "stop", svc_name, "/y"], capture_output=True, timeout=5, creationflags=flags)
                # Set startup type to disabled
                subprocess.run(["sc", "config", svc_name, "start=disabled"], capture_output=True, timeout=5, creationflags=flags)
                disabled_services.append(friendly)
            except Exception:
                continue

        # 2. Registry Policies for Deep Telemetry Block
        reg_policies = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", winreg.REG_DWORD, 0),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\CloudContent", "DisableWindowsConsumerFeatures", winreg.REG_DWORD, 1),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", winreg.REG_DWORD, 0),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", winreg.REG_DWORD, 0),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", winreg.REG_DWORD, 0),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search", "CortanaConsent", winreg.REG_DWORD, 0),
        ]

        for root, sub_key, val_name, vtype, val in reg_policies:
            try:
                with winreg.CreateKey(root, sub_key) as k:
                    winreg.SetValueEx(k, val_name, 0, vtype, val)
                    registry_applied.append(val_name)
            except Exception:
                continue

        return {
            "disabled_services": disabled_services,
            "registry_applied": registry_applied
        }
