"""
NovaCare System Suite - Game Booster & Ultimate Performance Engine
Temporarily pauses non-essential background services, switches Windows Power Plan
to Ultimate Performance, trims working set memory, and flawlessly restores the original
state when gaming session ends.
"""
import os
import sys
import re
import json
import subprocess
import psutil
from core.config import ConfigManager
from core.memory_booster import MemoryBooster

# Non-essential services that can be safely suspended during gaming
GAME_MODE_SERVICES = [
    ("Spooler", "Yazıcı Biriktiricisi"),
    ("WSearch", "Windows Search İndeksleme"),
    ("SysMain", "SysMain / SuperFetch"),
    ("WerSvc", "Windows Hata Raporlama"),
    ("MapsBroker", "İndirilen Haritalar Yöneticisi"),
    ("XblGameSave", "Xbox Live Oyun Kaydı Eşitleyicisi"),
    ("XboxGipSvc", "Xbox Aksesuar Yönetim Servisi"),
    ("DiagTrack", "Bağlı Kullanıcı Deneyimleri ve Telemetri")
]

class GameBooster:
    def __init__(self):
        self.config = ConfigManager()
        self.state_file = os.path.join(self.config.config_dir, "game_mode_state.json")

    def is_active(self) -> bool:
        """Checks if Game Mode is currently active."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("active", False)
            except Exception:
                pass
        return False

    def get_current_power_scheme(self) -> tuple[str, str]:
        """Returns the active Windows power scheme GUID and name."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            out = subprocess.check_output("powercfg /getactivescheme", shell=True, creationflags=flags).decode("cp1254", errors="ignore")
            m = re.search(r"([a-f0-9\-]{36})\s+\((.*?)\)", out, re.I)
            if m:
                return m.group(1), m.group(2)
        except Exception:
            pass
        return "", "Bilinmiyor"

    def ensure_ultimate_power_plan(self) -> str:
        """Finds or creates Windows Ultimate Performance power plan."""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            out = subprocess.check_output("powercfg /list", shell=True, creationflags=flags).decode("cp1254", errors="ignore")
            # 1. Search for existing Ultimate / Nihai plan
            for line in out.splitlines():
                if "nihai" in line.lower() or "ultimate" in line.lower():
                    m = re.search(r"([a-f0-9\-]{36})", line, re.I)
                    if m:
                        return m.group(1)

            # 2. Try to duplicate standard Ultimate Performance scheme
            dup_out = subprocess.check_output(
                "powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61",
                shell=True,
                creationflags=flags
            ).decode("cp1254", errors="ignore")
            m = re.search(r"([a-f0-9\-]{36})", dup_out, re.I)
            if m:
                return m.group(1)

            # 3. Fallback to High Performance
            for line in out.splitlines():
                if "yüksek" in line.lower() or "high performance" in line.lower():
                    m = re.search(r"([a-f0-9\-]{36})", line, re.I)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

    def activate(self) -> dict:
        """
        Activates Game Mode:
        1. Records current power scheme and running services.
        2. Sets power scheme to Ultimate Performance.
        3. Stops non-essential background services.
        4. Trims RAM working sets for maximum available game memory.
        """
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        prev_guid, prev_name = self.get_current_power_scheme()
        stopped_svcs = []

        # Find running target services
        for svc_name, friendly in GAME_MODE_SERVICES:
            try:
                s = psutil.win_service_get(svc_name)
                if s.status() == "running":
                    # Stop service
                    subprocess.run(["net", "stop", svc_name, "/y"], capture_output=True, timeout=5, creationflags=flags)
                    stopped_svcs.append(svc_name)
            except Exception:
                continue

        # Switch power plan
        ultimate_guid = self.ensure_ultimate_power_plan()
        if ultimate_guid:
            subprocess.run(["powercfg", "/setactive", ultimate_guid], capture_output=True, creationflags=flags)

        # Optimize RAM
        booster = MemoryBooster()
        freed, _ = booster.optimize_ram()

        state = {
            "active": True,
            "previous_power_guid": prev_guid,
            "previous_power_name": prev_name,
            "stopped_services": stopped_svcs,
            "freed_ram_bytes": freed
        }

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

        return state

    def deactivate(self) -> dict:
        """
        Restores previous state:
        1. Restores original Windows power scheme.
        2. Restarts the services that were previously suspended.
        3. Cleans up saved state.
        """
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if not os.path.exists(self.state_file):
            return {"active": False, "restored_services": 0}

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}

        # 1. Restore power scheme
        prev_guid = state.get("previous_power_guid")
        if prev_guid:
            subprocess.run(["powercfg", "/setactive", prev_guid], capture_output=True, creationflags=flags)

        # 2. Restart previously stopped services
        stopped_svcs = state.get("stopped_services", [])
        restarted_count = 0
        for svc_name in stopped_svcs:
            try:
                subprocess.run(["net", "start", svc_name], capture_output=True, timeout=5, creationflags=flags)
                restarted_count += 1
            except Exception:
                continue

        # 3. Remove state file
        try:
            os.remove(self.state_file)
        except Exception:
            pass

        return {
            "active": False,
            "previous_power_name": state.get("previous_power_name", "Standart"),
            "restored_services": restarted_count
        }
