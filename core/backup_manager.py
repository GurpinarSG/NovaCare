"""
NovaCare System Suite - Backup & Rescue Center
Manages registry backups, restoration, and Windows System Restore points.
"""
import os
import json
import winreg
import subprocess
from dataclasses import dataclass
from typing import Optional
from core.utils import format_bytes

@dataclass
class BackupEntry:
    filename: str
    filepath: str
    timestamp: str
    issue_count: int
    size_str: str

class BackupManager:
    def __init__(self, backup_dir: Optional[str] = None):
        if backup_dir is None:
            local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            self.backup_dir = os.path.join(local_app, 'NovaCare', 'Backups')
        else:
            self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def list_backups(self) -> list[BackupEntry]:
        """Lists all existing registry backup files sorted by creation date."""
        entries: list[BackupEntry] = []
        if not os.path.exists(self.backup_dir):
            return entries

        for fname in os.listdir(self.backup_dir):
            if fname.startswith("Registry_Backup_") and fname.endswith(".json"):
                fpath = os.path.join(self.backup_dir, fname)
                try:
                    sz = os.path.getsize(fpath)
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        count = len(data) if isinstance(data, list) else 0

                    # Parse timestamp from filename: Registry_Backup_YYYYMMDD_HHMMSS.json
                    ts_part = fname.replace("Registry_Backup_", "").replace(".json", "")
                    if len(ts_part) == 15 and "_" in ts_part:
                        d, t = ts_part.split("_")
                        formatted_ts = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
                    else:
                        formatted_ts = ts_part

                    entries.append(BackupEntry(
                        filename=fname,
                        filepath=fpath,
                        timestamp=formatted_ts,
                        issue_count=count,
                        size_str=format_bytes(sz)
                    ))
                except Exception:
                    continue

        # Sort newest first
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries

    def restore_backup(self, backup_filepath: str) -> tuple[int, int]:
        """
        Restores registry entries from a JSON backup file.
        Returns: (restored_count, failed_count)
        """
        if not os.path.exists(backup_filepath):
            return 0, 0

        restored = 0
        failed = 0

        try:
            with open(backup_filepath, "r", encoding="utf-8") as f:
                items = json.load(f)

            for item in items:
                try:
                    root = winreg.HKEY_CURRENT_USER if item.get('root_name') == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                    sub_key = item.get('sub_key')
                    val_name = item.get('value_name')
                    val_data = item.get('value_data')
                    val_type = item.get('value_type', winreg.REG_SZ)

                    with winreg.CreateKey(root, sub_key) as k:
                        winreg.SetValueEx(k, val_name, 0, val_type, val_data)
                        restored += 1
                except Exception:
                    failed += 1
        except Exception:
            return 0, 1

        return restored, failed

    def create_system_restore_point(self, description: str = "NovaCare Bakım Öncesi") -> bool:
        """Invokes PowerShell to create a Windows System Restore Point."""
        cmd = f'powershell.exe -ExecutionPolicy Bypass -Command "Checkpoint-Computer -Description \\"{description}\\" -RestorePointType \\"MODIFY_SETTINGS\\""'
        try:
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45, creationflags=flags)
            return res.returncode == 0
        except Exception:
            return False

    def open_system_restore_ui(self):
        """Launches the Windows native System Restore wizard (rstrui.exe)."""
        try:
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.Popen("rstrui.exe", shell=True, creationflags=flags)
        except Exception:
            pass
