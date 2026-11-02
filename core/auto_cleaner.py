"""
NovaCare System Suite - Automated Cleaning & Smart Maintenance Engine
Executes background system cleanups based on schedule triggers (startup, daily, weekly,
scheduled specific day/time, system idle, or disk size threshold), keeping the system clean and fast automatically.
"""
import ctypes
from datetime import datetime, timedelta
from core.config import ConfigManager
from core.junk_cleaner import JunkCleaner
from core.memory_booster import MemoryBooster
from core.privacy_tweaker import PrivacyTweaker
from core.utils import format_bytes

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

def get_system_idle_seconds() -> float:
    """Returns number of seconds elapsed since last user mouse or keyboard interaction."""
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception:
        pass
    return 0.0

class AutoCleaner:
    def __init__(self):
        self.config = ConfigManager()
        self.junk_cleaner = JunkCleaner()
        self.memory_booster = MemoryBooster()
        self.privacy_tweaker = PrivacyTweaker()

    def should_trigger(self) -> tuple[bool, str]:
        """
        Evaluates whether an auto-clean cycle should run based on configured rules.
        Returns (should_run, reason_string).
        """
        if not self.config.get("auto_clean_enabled", False):
            return False, "Otomatik temizleme devre dışı."

        schedule = self.config.get("auto_clean_schedule", "daily")
        last_run_str = self.config.get("last_auto_clean_time", "")

        # 1. Startup trigger
        if schedule == "startup":
            if not last_run_str:
                return True, "İlk sistem başlangıcı temizliği"
            try:
                last_dt = datetime.fromisoformat(last_run_str)
                if datetime.now() - last_dt > timedelta(minutes=10):
                    return True, "Sistem başlangıcı planlı temizliği"
            except Exception:
                return True, "Sistem başlangıcı temizliği"
            return False, "Başlangıç temizliği yakın zamanda yapıldı."

        # 2. Daily trigger (runs once every ~20-24 hours)
        elif schedule == "daily":
            if not last_run_str:
                return True, "İlk günlük bakım temizliği"
            try:
                last_dt = datetime.fromisoformat(last_run_str)
                if datetime.now() - last_dt > timedelta(hours=20):
                    return True, "Günlük planlı bakım zamanı geldi"
            except Exception:
                return True, "Günlük planlı bakım"
            return False, "Günlük temizlik bugün zaten yapıldı."

        # 3. Weekly trigger (runs once every 6-7 days)
        elif schedule == "weekly":
            if not last_run_str:
                return True, "İlk haftalık bakım temizliği"
            try:
                last_dt = datetime.fromisoformat(last_run_str)
                if datetime.now() - last_dt > timedelta(days=6):
                    return True, "Haftalık planlı bakım zamanı geldi"
            except Exception:
                return True, "Haftalık planlı bakım"
            return False, "Haftalık temizlik bu hafta zaten yapıldı."

        # 4. System Idle trigger (runs when computer is untouched for X minutes)
        elif schedule == "idle":
            idle_target_min = self.config.get("auto_clean_idle_minutes", 10)
            idle_sec = get_system_idle_seconds()
            if idle_sec >= (idle_target_min * 60.0):
                # Ensure we don't repeat clean continuously while idle (require 4 hours between idle cleans)
                if last_run_str:
                    try:
                        last_dt = datetime.fromisoformat(last_run_str)
                        if datetime.now() - last_dt < timedelta(hours=4):
                            return False, "Sistem boşta fakat bakım yakın zamanda yapıldı."
                    except Exception:
                        pass
                return True, f"Sistem {int(idle_sec // 60)} dakikadır boşta (Akıllı Boşta Bakım)"
            return False, f"Sistem henüz yeterince boşta değil ({int(idle_sec // 60)} / {idle_target_min} dk)."

        # 5. Scheduled specific day & time trigger (e.g. Sunday 03:00)
        elif schedule == "scheduled_time":
            target_day = self.config.get("auto_clean_target_day", 6) # 0=Mon, 6=Sun, -1=Everyday
            target_hour = self.config.get("auto_clean_target_hour", 3)
            now = datetime.now()

            day_match = (target_day == -1) or (now.weekday() == target_day)
            hour_match = (now.hour >= target_hour)

            if day_match and hour_match:
                if last_run_str:
                    try:
                        last_dt = datetime.fromisoformat(last_run_str)
                        # Check if already ran today
                        if last_dt.date() == now.date():
                            return False, "Planlı bakım bugün zaten çalıştırıldı."
                    except Exception:
                        pass
                day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
                d_name = "Her gün" if target_day == -1 else day_names[target_day]
                return True, f"Zamanlanmış bakım zamanı geldi ({d_name} {target_hour:02d}:00)"
            return False, "Planlanan bakım saatine henüz ulaşılmadı."

        # 6. Threshold trigger (when junk size exceeds threshold MB)
        elif schedule == "threshold":
            threshold_mb = self.config.get("auto_clean_threshold_mb", 1024)
            now = datetime.now()
            last_scan_str = self.config.get("last_threshold_scan_time", "")
            if last_scan_str:
                try:
                    last_scan_dt = datetime.fromisoformat(last_scan_str)
                    elapsed = (now - last_scan_dt).total_seconds()
                    # 30-minute cooldown (1800 seconds) between full disk scans to prevent disk wear
                    if elapsed < 1800:
                        cached_bytes = self.config.get("last_threshold_junk_bytes", 0)
                        if cached_bytes >= threshold_mb * 1024 * 1024:
                            return True, f"Gereksiz dosya boyutu {threshold_mb} MB sınırını aştı ({format_bytes(cached_bytes)})"
                        rem_min = int(max(1, (1800 - elapsed) // 60))
                        return False, f"Gereksiz dosya taraması bekleme süresinde ({rem_min} dk kaldı, son: {format_bytes(cached_bytes)} / {threshold_mb} MB)"
                except Exception:
                    pass

            cats = self.junk_cleaner.scan_all()
            total_bytes = sum(c.size for c in cats)
            self.config.set("last_threshold_scan_time", now.isoformat())
            self.config.set("last_threshold_junk_bytes", total_bytes)

            if total_bytes >= threshold_mb * 1024 * 1024:
                return True, f"Gereksiz dosya boyutu {threshold_mb} MB sınırını aştı ({format_bytes(total_bytes)})"
            return False, f"Gereksiz dosya boyutu eşiğin altında ({format_bytes(total_bytes)} / {threshold_mb} MB)"

        return False, "Koşul sağlanmadı."


    def execute_cleanup(self) -> dict:
        """
        Executes the configured automatic cleanup tasks.
        Safely purges junk, optimizes RAM, and wipes traces if enabled.
        """
        clean_junk = self.config.get("auto_clean_junk", True)
        clean_ram = self.config.get("auto_clean_ram", True)
        clean_traces = self.config.get("auto_clean_traces", False)

        freed_junk = 0
        cleaned_files = 0
        freed_ram = 0
        cleaned_traces = 0

        # 1. Clean Junk Files
        if clean_junk:
            try:
                cats = self.junk_cleaner.scan_all()
                if cats:
                    clean_recycle = self.config.get("auto_clean_recycle_bin", False)
                    cat_ids = {
                        c.id for c in cats
                        if clean_recycle or (c.id != "recycle_bin" and not getattr(c, "is_recycle_bin", False))
                    }
                    freed_junk, cleaned_files, _ = self.junk_cleaner.clean_categories(cat_ids)
            except Exception:
                pass

        # 2. Optimize RAM Working Sets
        if clean_ram:
            try:
                freed_ram, _ = self.memory_booster.optimize_ram()
            except Exception:
                pass

        # 3. Clean Privacy Traces
        if clean_traces:
            try:
                traces = self.privacy_tweaker.scan_privacy_traces()
                if traces:
                    trace_ids = {t.id for t in traces}
                    cleaned_traces = self.privacy_tweaker.clean_privacy_traces(trace_ids)
            except Exception:
                pass

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        now_iso = datetime.now().isoformat()
        self.config.set("last_auto_clean_time", now_iso)
        self.config.set("last_auto_clean_display", now_str)
        self.config.set("last_auto_clean_freed_bytes", freed_junk + freed_ram)
        self.config.set("last_threshold_junk_bytes", 0)
        self.config.set("last_threshold_scan_time", now_iso)

        return {
            "timestamp": now_str,
            "freed_junk_bytes": freed_junk,
            "freed_junk_str": format_bytes(freed_junk),
            "cleaned_files_count": cleaned_files,
            "freed_ram_bytes": freed_ram,
            "freed_ram_str": format_bytes(freed_ram),
            "cleaned_traces_count": cleaned_traces,
            "total_freed_bytes": freed_junk + freed_ram,
            "total_freed_str": format_bytes(freed_junk + freed_ram)
        }
