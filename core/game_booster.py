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
            out = subprocess.check_output("powercfg /getactivescheme", shell=True, timeout=5, creationflags=flags).decode("cp1254", errors="ignore")
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
            out = subprocess.check_output("powercfg /list", shell=True, timeout=5, creationflags=flags).decode("cp1254", errors="ignore")
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
                timeout=5,
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
            subprocess.run(["powercfg", "/setactive", ultimate_guid], capture_output=True, timeout=5, creationflags=flags)

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
            subprocess.run(["powercfg", "/setactive", prev_guid], capture_output=True, timeout=5, creationflags=flags)

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

# Pre-defined registry of popular games for instant detection
POPULAR_GAMES_DATABASE = [
    {"name": "Counter-Strike 2", "exe": "cs2.exe"},
    {"name": "VALORANT", "exe": "VALORANT-Win64-Shipping.exe"},
    {"name": "League of Legends", "exe": "LeagueClientUx.exe"},
    {"name": "Grand Theft Auto V", "exe": "GTA5.exe"},
    {"name": "Cyberpunk 2077", "exe": "Cyberpunk2077.exe"},
    {"name": "Apex Legends", "exe": "r5apex.exe"},
    {"name": "Fortnite", "exe": "FortniteClient-Win64-Shipping.exe"},
    {"name": "EA SPORTS FC 24", "exe": "FC24.exe"},
    {"name": "EA SPORTS FC 25", "exe": "FC25.exe"},
    {"name": "Dota 2", "exe": "dota2.exe"},
    {"name": "PUBG: BATTLEGROUNDS", "exe": "TslGame.exe"},
    {"name": "Red Dead Redemption 2", "exe": "RDR2.exe"},
    {"name": "Rainbow Six Siege", "exe": "RainbowSix.exe"},
    {"name": "The Witcher 3: Wild Hunt", "exe": "witcher3.exe"},
    {"name": "Minecraft", "exe": "javaw.exe"},
    {"name": "Call of Duty: Warzone", "exe": "cod.exe"},
    {"name": "Roblox", "exe": "RobloxPlayerBeta.exe"},
    {"name": "Overwatch 2", "exe": "Overwatch.exe"},
    {"name": "Genshin Impact", "exe": "GenshinImpact.exe"},
    {"name": "Rocket League", "exe": "RocketLeague.exe"}
]

class GameProfileManager:
    """Manages game profiles, auto-boost configuration, and local library scanning."""
    def __init__(self):
        self.config = ConfigManager()

    def get_profiles(self) -> list[dict]:
        profiles = self.config.get("game_profiles", [])
        if profiles:
            # Filter out legacy placeholder games that don't have valid paths and don't exist
            filtered = []
            for p in profiles:
                p_path = p.get("path", "")
                if p_path and os.path.exists(p_path):
                    filtered.append(p)
                elif not p_path and p.get("id") in {"cs2", "valorant", "lol", "gta5", "cyberpunk"}:
                    # Drop uninstalled hardcoded dummy preset
                    continue
                else:
                    filtered.append(p)
            if len(filtered) != len(profiles):
                self.save_profiles(filtered)
            return filtered
        return []

    def save_profiles(self, profiles: list[dict]):
        self.config.set("game_profiles", profiles)

    def add_profile(self, name: str, exe: str, path: str = "", auto_boost: bool = True) -> dict:
        clean_name = name.strip()
        clean_exe = os.path.basename(exe.strip())
        if not clean_exe.lower().endswith(".exe"):
            clean_exe += ".exe"

        import uuid
        profile_id = str(uuid.uuid4())[:8]

        profiles = self.get_profiles()
        # Avoid exact duplicate exe
        for p in profiles:
            if p.get("exe", "").lower() == clean_exe.lower():
                p["name"] = clean_name
                if path:
                    p["path"] = path
                p["auto_boost"] = auto_boost
                self.save_profiles(profiles)
                return p

        new_prof = {
            "id": profile_id,
            "name": clean_name or clean_exe,
            "exe": clean_exe,
            "path": path,
            "auto_boost": auto_boost
        }
        profiles.append(new_prof)
        self.save_profiles(profiles)
        return new_prof

    def remove_profile(self, profile_id: str) -> bool:
        profiles = self.get_profiles()
        initial_len = len(profiles)
        profiles = [p for p in profiles if p.get("id") != profile_id]
        if len(profiles) != initial_len:
            self.save_profiles(profiles)
            return True
        return False

    def toggle_profile_boost(self, profile_id: str, enabled: bool) -> bool:
        profiles = self.get_profiles()
        for p in profiles:
            if p.get("id") == profile_id:
                p["auto_boost"] = enabled
                self.save_profiles(profiles)
                return True
        return False

    def scan_installed_games(self) -> list[dict]:
        """
        Discovers games installed via Steam, Epic Games, Riot, and active processes.
        """
        found_games: list[dict] = []
        seen_exes = set()

        # 1. Check Steam standard library folders
        steam_paths = [
            r"C:\Program Files (x86)\Steam\steamapps\common",
            r"C:\Program Files\Steam\steamapps\common",
            r"D:\SteamLibrary\steamapps\common",
            r"E:\SteamLibrary\steamapps\common",
            r"D:\Games\SteamLibrary\steamapps\common"
        ]

        # Also inspect Steam libraryfolders.vdf
        vdf_path = r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf"
        if os.path.exists(vdf_path):
            try:
                with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if '"path"' in line.lower():
                            parts = line.split('"')
                            if len(parts) >= 4:
                                custom_steam = os.path.join(parts[3], "steamapps", "common")
                                if custom_steam not in steam_paths and os.path.exists(custom_steam):
                                    steam_paths.append(custom_steam)
            except Exception:
                pass

        for s_path in steam_paths:
            if os.path.exists(s_path):
                try:
                    for game_folder in os.listdir(s_path):
                        full_folder = os.path.join(s_path, game_folder)
                        if os.path.isdir(full_folder):
                            # Search for top-level or bin executables with pruned traversal
                            for root, dirs, files in os.walk(full_folder):
                                rel = os.path.relpath(root, full_folder)
                                if rel != "." and rel.count(os.sep) >= 1:
                                    dirs.clear()
                                for file in files:
                                    if file.lower().endswith(".exe"):
                                        f_low = file.lower()
                                        if any(k in f_low for k in ["crash", "unitycrash", "unins", "setup", "update", "redist", "vcredist", "dxsetup", "touchup"]):
                                            continue
                                        if f_low not in seen_exes:
                                            seen_exes.add(f_low)
                                            found_games.append({
                                                "name": game_folder,
                                                "exe": file,
                                                "path": os.path.join(root, file)
                                            })
                                        break
                except Exception:
                    pass

        # 2. Check Riot Games
        riot_candidates = [
            (r"C:\Riot Games\VALORANT\live\VALORANT.exe", "VALORANT", "VALORANT-Win64-Shipping.exe"),
            (r"C:\Riot Games\League of Legends\LeagueClientUx.exe", "League of Legends", "LeagueClientUx.exe")
        ]
        for p, name, exe in riot_candidates:
            if os.path.exists(p) and exe.lower() not in seen_exes:
                seen_exes.add(exe.lower())
                found_games.append({"name": name, "exe": exe, "path": p})

        # 3. Check Epic Games
        epic_path = r"C:\Program Files\Epic Games"
        if os.path.exists(epic_path):
            try:
                for game_folder in os.listdir(epic_path):
                    full_folder = os.path.join(epic_path, game_folder)
                    if os.path.isdir(full_folder):
                        for root, dirs, files in os.walk(full_folder):
                            rel = os.path.relpath(root, full_folder)
                            if rel != "." and rel.count(os.sep) >= 1:
                                dirs.clear()
                            for file in files:
                                if file.lower().endswith(".exe") and not any(k in file.lower() for k in ["crash", "unins", "setup", "launcher"]):
                                    f_low = file.lower()
                                    if f_low not in seen_exes:
                                        seen_exes.add(f_low)
                                        found_games.append({
                                            "name": game_folder,
                                            "exe": file,
                                            "path": os.path.join(root, file)
                                        })
                                    break
            except Exception:
                pass

        # 4. Check against POPULAR_GAMES_DATABASE for currently running processes
        try:
            for p in psutil.process_iter(['name', 'exe']):
                try:
                    p_name = p.info.get('name')
                    p_exe = p.info.get('exe')
                    if p_name:
                        for db_game in POPULAR_GAMES_DATABASE:
                            if p_name.lower() == db_game["exe"].lower() and p_name.lower() not in seen_exes:
                                seen_exes.add(p_name.lower())
                                found_games.append({
                                    "name": db_game["name"],
                                    "exe": p_name,
                                    "path": p_exe or ""
                                })
                except Exception:
                    continue
        except Exception:
            pass

        return found_games


from PyQt5.QtCore import QThread, pyqtSignal

class AutoGameWatcher(QThread):
    """
    Background daemon thread that monitors active game processes.
    Automatically enters Game Mode when a registered game starts,
    and restores standard power plan when the game exits.
    """
    game_started = pyqtSignal(str)   # game name
    game_stopped = pyqtSignal(str)   # game name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.game_booster = GameBooster()
        self.profile_mgr = GameProfileManager()
        self._running = True
        self._active_game_id = None
        self._auto_activated = False

    def stop(self):
        self._running = False

    def _interruptible_sleep(self, ms: int = 3000):
        step = 50
        elapsed = 0
        while elapsed < ms and self._running:
            self.msleep(min(step, ms - elapsed))
            elapsed += step

    def run(self):
        while self._running:
            try:
                # Check user preference
                if not self.config.get("auto_game_mode_enabled", True):
                    self._interruptible_sleep(3000)
                    continue

                profiles = self.profile_mgr.get_profiles()
                active_profile_map = {
                    p.get("exe", "").lower(): p
                    for p in profiles
                    if p.get("auto_boost", True) and p.get("exe")
                }

                if not active_profile_map:
                    self._interruptible_sleep(3000)
                    continue

                # Query running processes
                running_exes = set()
                for p in psutil.process_iter(['name']):
                    try:
                        n = p.info.get('name')
                        if n:
                            running_exes.add(n.lower())
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # 1. If a game is currently tracked as running, check if it closed
                if self._active_game_id is not None:
                    curr_prof = next((p for p in profiles if p.get("id") == self._active_game_id), None)
                    if curr_prof and curr_prof.get("exe", "").lower() in running_exes:
                        # Game is still active
                        self._interruptible_sleep(3000)
                        continue
                    else:
                        # Game was closed!
                        closed_name = curr_prof.get("name", "Oyun") if curr_prof else "Oyun"
                        self._active_game_id = None
                        if self._auto_activated and self.game_booster.is_active():
                            self.game_booster.deactivate()
                            self._auto_activated = False
                        self.game_stopped.emit(closed_name)
                        self._interruptible_sleep(2000)
                        continue

                # 2. If no game is currently tracked, check if any registered game started
                for exe, prof in active_profile_map.items():
                    if exe in running_exes:
                        self._active_game_id = prof.get("id")
                        if not self.game_booster.is_active():
                            self.game_booster.activate()
                            self._auto_activated = True
                        self.game_started.emit(prof.get("name", exe))
                        break

            except Exception:
                pass

            self._interruptible_sleep(3000)

