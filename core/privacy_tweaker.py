"""
NovaCare System Suite - Privacy Shield & Windows Tweaker
Cleans privacy traces (recent files, Run history, clipboard) and configures
Windows telemetry & privacy settings.
"""
import os
import winreg
import ctypes
import subprocess
from dataclasses import dataclass
from core.utils import safe_remove_file, log_debug, get_system32_path

@dataclass
class PrivacyTraceItem:
    id: str
    name: str
    description: str
    count: int
    selected: bool = True

@dataclass
class SystemTweak:
    id: str
    name: str
    description: str
    root: int
    sub_key: str
    value_name: str
    enabled_val: int
    disabled_val: int
    current_enabled: bool = False

class PrivacyTweaker:
    def __init__(self):
        self.tweaks: list[SystemTweak] = self._init_tweaks()

    def _init_tweaks(self) -> list[SystemTweak]:
        return [
            SystemTweak(
                id="telemetry",
                name="Windows Telemetri ve Tanılama Verilerini Kısıtla",
                description="Microsoft'a arka planda tanılama ve kullanım verisi gönderimini en aza indirir.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                value_name="AllowTelemetry",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="advertising_id",
                name="Kişiselleştirilmiş Reklam Kimliğini Kapat",
                description="Uygulamaların kullanıcı alışkanlıklarına göre reklam kimliği oluşturmasını engeller.",
                root=winreg.HKEY_CURRENT_USER,
                sub_key=r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo",
                value_name="Enabled",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="activity_history",
                name="Etkinlik Geçmişi ve Zaman Çizelgesini Devre Dışı Bırak",
                description="Açılan dosyaların ve pencerelerin buluta/geçmişe kaydedilmesini durdurur.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\System",
                value_name="EnableActivityFeed",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="bing_search",
                name="Başlat Menüsü Bing Web Aramalarını Kapat",
                description="Başlat menüsünde arama yaparken internette arama yapılmasını engelleyip aramayı hızlandırır.",
                root=winreg.HKEY_CURRENT_USER,
                sub_key=r"Software\Policies\Microsoft\Windows\Explorer",
                value_name="DisableSearchBoxSuggestions",
                enabled_val=1,
                disabled_val=0
            ),
            SystemTweak(
                id="game_dvr",
                name="Arka Plan Oyun Kaydını (Game DVR) Kapat",
                description="Oyun oynarken arka planda sürekli kayıt alarak FPS düşüşü yaratan servisi kapatır.",
                root=winreg.HKEY_CURRENT_USER,
                sub_key=r"System\GameConfigStore",
                value_name="GameDVR_Enabled",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="location_tracking",
                name="Sistem Konum Takibini Devre Dışı Bırak",
                description="Windows ve üçüncü parti uygulamaların konumunuza erişmesini kısıtlar.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy",
                value_name="LetAppsAccessLocation",
                enabled_val=2,  # Force deny
                disabled_val=0
            ),
            SystemTweak(
                id="cortana",
                name="Cortana Sesli Asistanı ve Arka Plan Ajanını Kapat",
                description="Kullanılmayan Cortana servisinin arka planda mikrofon ve veri dinlemesini engeller.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\Windows Search",
                value_name="AllowCortana",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="ceip",
                name="Windows Müşteri Deneyimi Geliştirme Programını (CEIP) Kapat",
                description="Microsoft sunucularına otomatik kullanım istatistiği yüklenmesini durdurur.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\SQMClient\Windows",
                value_name="CEIPEnable",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="consumer_features",
                name="Windows Tüketici Deneyimleri ve Tanıtım Önerilerini Kapat",
                description="Başlat menüsünde ve bildirimlerde sponsorlu reklam ve uygulama önerilerini engeller.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
                value_name="DisableWindowsConsumerFeatures",
                enabled_val=1,
                disabled_val=0
            ),
            SystemTweak(
                id="feedback_frequency",
                name="Windows Tanılama Geri Bildirim Sıklığını Kapat",
                description="Windows'un periyodik anket ve geri bildirim pencereleri göstermesini engeller.",
                root=winreg.HKEY_CURRENT_USER,
                sub_key=r"Software\Microsoft\Siuf\Rules",
                value_name="NumberOfSIUFInPeriod",
                enabled_val=0,
                disabled_val=1
            ),
            SystemTweak(
                id="app_diagnostics",
                name="Uygulamaların Tanılama Bilgilerine Erişimini Kısıtla",
                description="Üçüncü parti yazılımların sistem tanılama ve log verilerinize erişmesini engeller.",
                root=winreg.HKEY_LOCAL_MACHINE,
                sub_key=r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy",
                value_name="LetAppsGetDiagnosticInfo",
                enabled_val=2,  # Force deny
                disabled_val=0
            )
        ]

    def scan_privacy_traces(self) -> list[PrivacyTraceItem]:
        """Scans for user activity traces: Recent files, Run MRU, Typed Paths, Clipboard."""
        items: list[PrivacyTraceItem] = []

        # 1. Recent documents (iterator based, zero memory overhead)
        recent_dir = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Recent')
        recent_count = 0
        if os.path.exists(recent_dir):
            try:
                with os.scandir(recent_dir) as it:
                    recent_count = sum(1 for entry in it if entry.name.endswith('.lnk'))
            except OSError as e:
                log_debug(f"PrivacyTweaker recent docs scan error: {e}")
        items.append(PrivacyTraceItem(
            id="recent_docs",
            name="Son Açılan Dosyalar Geçmişi",
            description=f"Windows Gezgini son açılan dosyalar ve hızlı erişim kısayolları ({recent_count} öğe)",
            count=recent_count
        ))

        # 2. Run MRU (Çalıştır geçmişi)
        run_count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU", 0, winreg.KEY_READ) as k:
                _, run_count, _ = winreg.QueryInfoKey(k)
        except OSError:
            pass
        items.append(PrivacyTraceItem(
            id="run_mru",
            name="Çalıştır (Win+R) Komut Geçmişi",
            description=f"Çalıştır penceresinde yazılan önceki komutlar ({run_count} öğe)",
            count=run_count
        ))

        # 3. Explorer Typed Paths
        typed_count = 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths", 0, winreg.KEY_READ) as k:
                _, typed_count, _ = winreg.QueryInfoKey(k)
        except OSError:
            pass
        items.append(PrivacyTraceItem(
            id="typed_paths",
            name="Dosya Gezgini Adres Çubuğu Geçmişi",
            description=f"Gezgin adres çubuğuna el ile girilen klasör yolları ({typed_count} öğe)",
            count=typed_count
        ))

        # 4. Clipboard
        items.append(PrivacyTraceItem(
            id="clipboard",
            name="Windows Pano Hafızası",
            description="Kopyalanan metin veya görsellerin tutulduğu bellek alanı",
            count=1
        ))

        return items

    def clean_privacy_traces(self, selected_ids: set[str]) -> int:
        """Cleans selected traces. Returns count of items cleaned."""
        cleaned = 0

        # Recent files
        if "recent_docs" in selected_ids:
            recent_dir = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Recent')
            if os.path.exists(recent_dir):
                try:
                    with os.scandir(recent_dir) as it:
                        for entry in it:
                            if entry.is_file() and entry.name.endswith(('.lnk', '.destlist')):
                                if safe_remove_file(entry.path):
                                    cleaned += 1
                except OSError as e:
                    log_debug(f"PrivacyTweaker clean recent docs error: {e}")

        # Run MRU
        if "run_mru" in selected_ids:
            try:
                sub = r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_ALL_ACCESS) as k:
                    _, count, _ = winreg.QueryInfoKey(k)
                    names = [winreg.EnumValue(k, i)[0] for i in range(count)]
                    for n in names:
                        winreg.DeleteValue(k, n)
                        cleaned += 1
            except OSError as e:
                log_debug(f"PrivacyTweaker clean run MRU error: {e}")

        # Typed paths
        if "typed_paths" in selected_ids:
            try:
                sub = r"Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_ALL_ACCESS) as k:
                    _, count, _ = winreg.QueryInfoKey(k)
                    names = [winreg.EnumValue(k, i)[0] for i in range(count)]
                    for n in names:
                        winreg.DeleteValue(k, n)
                        cleaned += 1
            except OSError as e:
                log_debug(f"PrivacyTweaker clean typed paths error: {e}")

        # Clipboard
        if "clipboard" in selected_ids:
            try:
                if ctypes.windll.user32.OpenClipboard(None):
                    try:
                        ctypes.windll.user32.EmptyClipboard()
                        cleaned += 1
                    finally:
                        ctypes.windll.user32.CloseClipboard()
            except Exception as e:
                log_debug(f"PrivacyTweaker empty clipboard error: {e}")

        return cleaned

    def check_tweak_statuses(self) -> list[SystemTweak]:
        """Checks whether each tweak is currently active in the registry."""
        for tweak in self.tweaks:
            try:
                with winreg.OpenKey(tweak.root, tweak.sub_key, 0, winreg.KEY_READ) as k:
                    val, _ = winreg.QueryValueEx(k, tweak.value_name)
                    tweak.current_enabled = (val == tweak.enabled_val)
            except OSError:
                tweak.current_enabled = False
        return self.tweaks

    def apply_tweak(self, tweak: SystemTweak, enable: bool) -> bool:
        """Applies or reverts a privacy tweak in the registry."""
        val_to_set = tweak.enabled_val if enable else tweak.disabled_val
        try:
            with winreg.CreateKey(tweak.root, tweak.sub_key) as k:
                winreg.SetValueEx(k, tweak.value_name, 0, winreg.REG_DWORD, val_to_set)
                tweak.current_enabled = enable
                return True
        except PermissionError as e:
            log_debug(f"PrivacyTweaker: Permission denied applying {tweak.id}: {e}")
            return False
        except Exception as e:
            log_debug(f"PrivacyTweaker: Failed applying {tweak.id}: {e}")
            return False

    def are_all_anti_spy_enabled(self) -> bool:
        """Checks if all telemetry and privacy protection tweaks are active."""
        statuses = self.check_tweak_statuses()
        return all(t.current_enabled for t in statuses)

    def apply_all_anti_spy(self, enable: bool = True) -> tuple[int, int, list[str]]:
        """
        1-Click Anti-Spy master switch.
        Enables or disables all privacy & telemetry restriction tweaks,
        and shuts down telemetry background services (DiagTrack, dmwappushservice).
        Returns (success_count, failed_count, stopped_services).
        """
        success = 0
        failed = 0
        stopped_services = []

        for tweak in self.tweaks:
            if self.apply_tweak(tweak, enable):
                success += 1
            else:
                failed += 1

        # Manage telemetry services (stop & disable on enable=True, restore & start on enable=False)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        telemetry_svcs = [
            ("DiagTrack", "Bağlı Kullanıcı Deneyimleri ve Telemetri (DiagTrack)"),
            ("dmwappushservice", "WAP Gönderimi İleti Yönlendirme (dmwappushservice)")
        ]
        if enable:
            for svc_name, friendly in telemetry_svcs:
                try:
                    subprocess.run(
                        [get_system32_path("net"), "stop", svc_name, "/y"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, creationflags=flags
                    )
                    subprocess.run(
                        [get_system32_path("sc"), "config", svc_name, "start=disabled"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, creationflags=flags
                    )
                    stopped_services.append(friendly)
                except Exception:
                    pass
        else:
            for svc_name, friendly in telemetry_svcs:
                try:
                    subprocess.run(
                        [get_system32_path("sc"), "config", svc_name, "start=auto"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, creationflags=flags
                    )
                    subprocess.run(
                        [get_system32_path("net"), "start", svc_name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, creationflags=flags
                    )
                    stopped_services.append(friendly)
                except Exception:
                    pass

        return success, failed, stopped_services


