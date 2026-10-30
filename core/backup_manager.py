"""
NovaCare System Suite - Backup & Rescue Center
Manages registry backups, restoration, and Windows System Restore points.
"""
import os
import json
import hmac
import hashlib
import winreg
import subprocess
from dataclasses import dataclass
from typing import Optional
from core.utils import format_bytes, log_debug
from core.security import encrypt_string, decrypt_string

ALLOWED_SUBKEY_PREFIXES = (
    r"software\microsoft\windows\currentversion\run",
    r"software\microsoft\windows\currentversion\runonce",
    r"software\wow6432node\microsoft\windows\currentversion\run",
    r"software\wow6432node\microsoft\windows\currentversion\runonce",
    r"software\microsoft\windows\currentversion\app paths",
    r"software\microsoft\windows\currentversion\shareddlls",
    r"software\microsoft\windows\currentversion\uninstall",
    r"software\wow6432node\microsoft\windows\currentversion\uninstall",
    r"software\microsoft\windows\currentversion\explorer\fileexts",
    r"software\classes\local settings\software\microsoft\windows\shell\muicache",
)

def canonicalize_root_name(root_name: str) -> Optional[str]:
    """Normalizes registry root hive names (HKCU, HKEY_CURRENT_USER, HKLM, HKEY_LOCAL_MACHINE)."""
    if not isinstance(root_name, str):
        return None
    r = root_name.strip().upper().rstrip('\\')
    if r in ("HKCU", "HKEY_CURRENT_USER"):
        return "HKCU"
    if r in ("HKLM", "HKEY_LOCAL_MACHINE"):
        return "HKLM"
    return None

def is_allowed_registry_key(root_name: str, sub_key: str) -> bool:
    """Strictly validates that registry keys belong to legitimate application cleanup roots."""
    canon_root = canonicalize_root_name(root_name)
    if not canon_root:
        return False
    if not isinstance(sub_key, str) or not sub_key.strip():
        return False
    if "\x00" in sub_key or ".." in sub_key:
        return False

    import re
    norm = re.sub(r'[\\/]+', r'\\', sub_key.strip()).strip('\\').lower()

    # Block unauthorized system hives or MuiCache/FileExts under HKLM
    if canon_root == "HKLM":
        if norm.startswith(r"software\classes") or r"fileexts" in norm:
            return False

    for prefix in ALLOWED_SUBKEY_PREFIXES:
        if norm == prefix or norm.startswith(prefix + "\\"):
            return True
    return False

def get_backup_hmac_key() -> bytes:
    """
    Returns a machine/user-bound HMAC secret key for backup signing.
    Protected with DPAPI when available.
    """
    local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    secret_file = os.path.join(local_app, 'NovaCare', '.backup_secret')
    if os.path.exists(secret_file):
        try:
            with open(secret_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            dec = decrypt_string(content)
            if dec:
                return bytes.fromhex(dec)
            if len(content) == 64:
                return bytes.fromhex(content)
        except Exception:
            pass

    new_key = os.urandom(32)
    try:
        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        enc = encrypt_string(new_key.hex())
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(enc if enc else new_key.hex())
    except Exception:
        seed = f"NovaCare_Secret_{os.environ.get('COMPUTERNAME', '')}_{os.environ.get('USERNAME', '')}"
        return hashlib.sha256(seed.encode('utf-8')).digest()
    return new_key

def compute_backup_hmac(items: list) -> str:
    """Computes deterministic HMAC-SHA256 signature for registry backup items."""
    key = get_backup_hmac_key()
    canonical_repr = json.dumps(items, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hmac.new(key, canonical_repr.encode('utf-8'), hashlib.sha256).hexdigest()

def verify_backup_hmac(data: dict) -> bool:
    """Verifies HMAC-SHA256 integrity of backup payload."""
    if not isinstance(data, dict):
        return False
    signature = data.get("hmac")
    items = data.get("items")
    if not signature or not isinstance(signature, str) or not isinstance(items, list):
        return False
    expected = compute_backup_hmac(items)
    return hmac.compare_digest(signature, expected)

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

        try:
            with os.scandir(self.backup_dir) as it:
                for entry in it:
                    if entry.is_file() and entry.name.startswith("Registry_Backup_") and entry.name.endswith(".json"):
                        try:
                            sz = entry.stat().st_size
                            with open(entry.path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                if isinstance(data, dict) and "items" in data:
                                    count = len(data["items"])
                                elif isinstance(data, list):
                                    count = len(data)
                                else:
                                    count = 0

                            fname = entry.name
                            ts_part = fname.replace("Registry_Backup_", "").replace(".json", "")
                            if len(ts_part) == 15 and "_" in ts_part:
                                d, t = ts_part.split("_")
                                formatted_ts = f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"
                            else:
                                formatted_ts = ts_part

                            entries.append(BackupEntry(
                                filename=fname,
                                filepath=entry.path,
                                timestamp=formatted_ts,
                                issue_count=count,
                                size_str=format_bytes(sz)
                            ))
                        except Exception as e:
                            log_debug(f"BackupManager: reading backup {entry.name} failed: {e}")
                            continue
        except OSError as e:
            log_debug(f"BackupManager: list_backups error: {e}")

        # Sort newest first
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries

    def restore_backup(self, backup_filepath: str) -> tuple[int, int]:
        """
        Restores registry entries from an HMAC-authenticated JSON backup file.
        Strictly rejects tampered backups and unauthorized root/system keys.
        Returns: (restored_count, failed_count)
        """
        if not os.path.exists(backup_filepath):
            return 0, 0

        try:
            with open(backup_filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log_debug(f"BackupManager: Error reading backup file {backup_filepath}: {e}")
            return 0, 1

        # Strict HMAC-SHA256 signature verification
        if not verify_backup_hmac(data):
            log_debug(f"BackupManager: Backup file {backup_filepath} failed HMAC integrity verification or is tampered!")
            return 0, 1

        items = data.get("items", [])
        restored = 0
        failed = 0

        for item in items:
            try:
                raw_root = item.get('root_name')
                sub_key = item.get('sub_key')

                canon_root = canonicalize_root_name(raw_root)
                # Strict allowlist validation against unauthorized HKLM writing/LPE
                if not canon_root or not is_allowed_registry_key(canon_root, sub_key):
                    log_debug(f"BackupManager: Blocked restore to unauthorized key: {raw_root}\\{sub_key}")
                    failed += 1
                    continue

                root = winreg.HKEY_CURRENT_USER if canon_root == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                val_name = item.get('value_name')
                val_data = item.get('value_data')
                val_type = item.get('value_type', winreg.REG_SZ)
                try:
                    val_type = int(val_type)
                except (ValueError, TypeError):
                    val_type = winreg.REG_SZ

                # Normalize val_data to the required type
                if val_type in (winreg.REG_DWORD, getattr(winreg, 'REG_DWORD_LITTLE_ENDIAN', 4), getattr(winreg, 'REG_QWORD', 11)):
                    if isinstance(val_data, str):
                        val_data = int(val_data, 16) if val_data.startswith("0x") else int(val_data)
                    elif val_data is None:
                        val_data = 0
                    else:
                        val_data = int(val_data)
                elif val_type == winreg.REG_BINARY:
                    if isinstance(val_data, str):
                        try:
                            val_data = bytes.fromhex(val_data.replace(" ", "").replace(",", ""))
                        except Exception:
                            val_data = val_data.encode("utf-8")
                    elif val_data is None:
                        val_data = b""
                elif val_type == winreg.REG_MULTI_SZ:
                    if isinstance(val_data, str):
                        val_data = [val_data]
                    elif val_data is None:
                        val_data = []
                elif val_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                    val_data = "" if val_data is None else str(val_data)

                with winreg.CreateKey(root, sub_key) as k:
                    winreg.SetValueEx(k, val_name, 0, val_type, val_data)
                    restored += 1
            except Exception as e:
                log_debug(f"BackupManager: Error restoring key {sub_key}: {e}")
                failed += 1

        return restored, failed

    def create_system_restore_point(self, description: str = "NovaCare Bakım Öncesi") -> bool:
        """Invokes PowerShell to create a Windows System Restore Point securely without shell injection."""
        import base64
        safe_desc = " ".join(str(description).split()).replace("'", "''")
        if not safe_desc:
            safe_desc = "NovaCare Bakim Oncesi"

        ps_script = (
            f"Enable-ComputerRestore -Drive 'C:\\' -ErrorAction SilentlyContinue; "
            f"Checkpoint-Computer -Description '{safe_desc}' -RestorePointType 'MODIFY_SETTINGS'"
        )
        encoded_ps = base64.b64encode(ps_script.encode('utf-16le')).decode('ascii')
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_ps]
        try:
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=50, creationflags=flags)
            return res.returncode == 0
        except Exception as e:
            log_debug(f"BackupManager: create_system_restore_point error: {e}")
            return False

    def open_system_restore_ui(self):
        """Launches the Windows native System Restore wizard (rstrui.exe)."""
        try:
            subprocess.Popen(["rstrui.exe"])
        except Exception:
            pass
