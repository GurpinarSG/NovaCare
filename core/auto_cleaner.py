"""
NovaCare System Suite - Automated Cleaning & Smart Maintenance Engine
Executes background system cleanups based on schedule triggers (startup, daily, weekly)
or size/RAM thresholds, keeping the system clean and fast automatically.
"""
import os
import time
from datetime import datetime, timedelta
from core.config import ConfigManager
from core.junk_cleaner import JunkCleaner
from core.memory_booster import MemoryBooster
from core.privacy_tweaker import PrivacyTweaker
from core.utils import format_bytes

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

        # 4. Threshold trigger (when junk size exceeds threshold MB)
        elif schedule == "threshold":
            threshold_mb = self.config.get("auto_clean_threshold_mb", 1024)
            cats = self.junk_cleaner.scan_all()
            total_bytes = sum(c.size for c in cats)
            if total_bytes >= threshold_mb * 1024 * 1024:
                return True, f"Gereksiz dosya boyutu {threshold_mb} MB sınırını aştı ({format_bytes(total_bytes)})"
            return False, f"Gereksiz dosya boyutu eşiğin altında ({format_bytes(total_bytes)} / {threshold_mb} MB)"

        return False, "Koşul sağlanmadı."

    def execute_cleanup(self) -> dict:
        """
        Executes the configured automatic cleanup tasks.
        Safely purges junk, optimizes RAM, and wisp traces if enabled.
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
                    cat_ids = {c.id for c in cats}
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
        self.config.set("last_auto_clean_time", datetime.now().isoformat())
        self.config.set("last_auto_clean_display", now_str)
        self.config.set("last_auto_clean_freed_bytes", freed_junk + freed_ram)

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
