"""
NovaCare System Suite - Safe Windows Registry Cleaner & Optimizer
Scans for invalid shortcuts, missing shared DLLs, obsolete startup keys, broken application paths,
and safely creates a rollback backup before fixing any issues.
"""
import os
import winreg
import json
import time
from functools import lru_cache
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from core.utils import log_debug

@dataclass
class RegistryIssue:
    id: str
    category: str
    root_name: str       # "HKCU" or "HKLM"
    sub_key: str
    value_name: str
    value_data: str
    value_type: int      # winreg.REG_SZ, etc.
    reason: str
    selected: bool = True

class RegistryCleaner:
    def __init__(self, backup_dir: Optional[str] = None):
        if backup_dir is None:
            local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            self.backup_dir = os.path.join(local_app, 'NovaCare', 'Backups')
        else:
            self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)
        self.issues: list[RegistryIssue] = []

    def _get_root_key(self, root_name: str):
        if root_name == "HKCU":
            return winreg.HKEY_CURRENT_USER
        elif root_name == "HKLM":
            return winreg.HKEY_LOCAL_MACHINE
        raise ValueError(f"Unknown root key: {root_name}")

    @staticmethod
    @lru_cache(maxsize=1024)
    def _clean_path_string(raw_cmd: str) -> str:
        """Extract clean file path from command line arguments with LRU caching."""
        cmd = raw_cmd.strip()
        if not cmd:
            return ""
        if cmd.startswith('"'):
            end_quote = cmd.find('"', 1)
            if end_quote != -1:
                return cmd[1:end_quote].strip()
            return cmd.strip('"')
        parts = cmd.split(' ', 1)
        return parts[0].strip()

    def scan_all(self, progress_callback: Optional[Callable[[str, int, int], None]] = None) -> list[RegistryIssue]:
        """
        Scan registry for safe-to-fix inconsistencies.
        """
        self.issues.clear()
        scan_steps = [
            ("Geçersiz Başlangıç Kayıtları (Run/RunOnce)", self._scan_startup_keys),
            ("Bozuk Uygulama Yolları (App Paths)", self._scan_app_paths),
            ("Eksik Paylaşılan DLL Dosyaları (Shared DLLs)", self._scan_shared_dlls),
            ("Bozuk Kaldırma Bilgileri (Uninstall Entries)", self._scan_uninstall_leftovers),
            ("Eski Dosya Uzantısı Bağlantıları", self._scan_file_extensions),
            ("Bozuk MUI Cache Girişleri", self._scan_muicache)
        ]

        total = len(scan_steps)
        for idx, (title, func) in enumerate(scan_steps):
            if progress_callback:
                progress_callback(title, idx + 1, total)
            try:
                func()
            except Exception:
                pass

        return self.issues

    def _scan_startup_keys(self):
        targets = [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
            ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run")
        ]

        for root_name, sub in targets:
            try:
                root = self._get_root_key(root_name)
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as key:
                    _, count, _ = winreg.QueryInfoKey(key)
                    for i in range(count):
                        try:
                            val_name, val_data, val_type = winreg.EnumValue(key, i)
                            if val_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                                expanded = os.path.expandvars(str(val_data))
                                exe_path = self._clean_path_string(expanded)
                                if exe_path and not os.path.exists(exe_path) and not exe_path.lower().startswith(('rundll32', 'regsvr32', 'cmd', 'powershell')):
                                    self.issues.append(RegistryIssue(
                                        id=f"startup_{root_name}_{val_name}_{i}",
                                        category="Geçersiz Başlangıç Kaydı",
                                        root_name=root_name,
                                        sub_key=sub,
                                        value_name=val_name,
                                        value_data=str(val_data),
                                        value_type=val_type,
                                        reason=f"Başlatılacak dosya mevcut değil: {exe_path}"
                                    ))
                        except OSError:
                            continue
            except OSError:
                continue

    def _scan_app_paths(self):
        targets = [
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\App Paths")
        ]
        for root_name, sub in targets:
            try:
                root = self._get_root_key(root_name)
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as base_key:
                    subkeys_count, _, _ = winreg.QueryInfoKey(base_key)
                    for i in range(min(subkeys_count, 300)):  # safety bound
                        try:
                            sub_app = winreg.EnumKey(base_key, i)
                            full_sub = f"{sub}\\{sub_app}"
                            with winreg.OpenKey(root, full_sub, 0, winreg.KEY_READ) as app_key:
                                try:
                                    val_data, val_type = winreg.QueryValueEx(app_key, "")
                                    expanded = os.path.expandvars(str(val_data))
                                    clean_p = self._clean_path_string(expanded)
                                    if clean_p and not os.path.exists(clean_p):
                                        self.issues.append(RegistryIssue(
                                            id=f"apppath_{root_name}_{sub_app}_{i}",
                                            category="Kayıp Uygulama Yolu",
                                            root_name=root_name,
                                            sub_key=full_sub,
                                            value_name="",
                                            value_data=str(val_data),
                                            value_type=val_type,
                                            reason=f"Uygulama yürütülebilir dosyası bulunamadı: {clean_p}"
                                        ))
                                except OSError:
                                    pass
                        except OSError:
                            continue
            except OSError:
                continue

    def _scan_shared_dlls(self):
        sub = r"Software\Microsoft\Windows\CurrentVersion\SharedDLLs"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub, 0, winreg.KEY_READ) as key:
                _, count, _ = winreg.QueryInfoKey(key)
                for i in range(min(count, 500)):
                    try:
                        val_name, val_data, val_type = winreg.EnumValue(key, i)
                        expanded = os.path.expandvars(val_name)
                        if expanded and not os.path.exists(expanded):
                            self.issues.append(RegistryIssue(
                                id=f"shareddll_{i}",
                                category="Eksik Paylaşılan DLL",
                                root_name="HKLM",
                                sub_key=sub,
                                value_name=val_name,
                                value_data=str(val_data),
                                value_type=val_type,
                                reason=f"Paylaşılan DLL kütüphanesi diskte bulunamadı: {val_name}"
                            ))
                    except OSError:
                        continue
        except OSError:
            pass

    def _scan_uninstall_leftovers(self):
        targets = [
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
        ]
        for root_name, sub in targets:
            try:
                root = self._get_root_key(root_name)
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as base_key:
                    sub_count, _, _ = winreg.QueryInfoKey(base_key)
                    for i in range(min(sub_count, 400)):
                        try:
                            app_guid = winreg.EnumKey(base_key, i)
                            full_sub = f"{sub}\\{app_guid}"
                            with winreg.OpenKey(root, full_sub, 0, winreg.KEY_READ) as app_key:
                                try:
                                    uninst_str, utype = winreg.QueryValueEx(app_key, "UninstallString")
                                    clean_p = self._clean_path_string(os.path.expandvars(str(uninst_str)))
                                    # Check if exe path doesn't exist and isn't msiexec
                                    if clean_p and not os.path.exists(clean_p) and not 'msiexec' in clean_p.lower():
                                        try:
                                            disp_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                                        except OSError:
                                            disp_name = app_guid
                                        self.issues.append(RegistryIssue(
                                            id=f"uninst_{root_name}_{app_guid}_{i}",
                                            category="Bozuk Kaldırma Bilgisi",
                                            root_name=root_name,
                                            sub_key=full_sub,
                                            value_name="UninstallString",
                                            value_data=str(uninst_str),
                                            value_type=utype,
                                            reason=f"Kaldırma programı mevcut değil ({disp_name}): {clean_p}"
                                        ))
                                except OSError:
                                    pass
                        except OSError:
                            continue
            except OSError:
                continue

    def _scan_file_extensions(self):
        sub = r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_READ) as key:
                count, _, _ = winreg.QueryInfoKey(key)
                for i in range(min(count, 300)):
                    try:
                        ext_name = winreg.EnumKey(key, i)
                        # Check OpenWithProgids
                        progid_sub = f"{sub}\\{ext_name}\\OpenWithProgids"
                        try:
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, progid_sub, 0, winreg.KEY_READ) as pk:
                                _, v_count, _ = winreg.QueryInfoKey(pk)
                                for vi in range(v_count):
                                    vname, vdata, vtype = winreg.EnumValue(pk, vi)
                                    # Check if progid exists in HKCR
                                    try:
                                        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, vname, 0, winreg.KEY_READ):
                                            pass
                                    except OSError:
                                        self.issues.append(RegistryIssue(
                                            id=f"fileext_{ext_name}_{vi}",
                                            category="Eski Dosya Uzantısı İlişkisi",
                                            root_name="HKCU",
                                            sub_key=progid_sub,
                                            value_name=vname,
                                            value_data=str(vdata),
                                            value_type=vtype,
                                            reason=f"Geçersiz ProgID ilişkisi: {vname} ({ext_name})"
                                        ))
                        except OSError:
                            pass
                    except OSError:
                        continue
        except OSError:
            pass

    def _scan_muicache(self):
        sub = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_READ) as key:
                _, count, _ = winreg.QueryInfoKey(key)
                for i in range(min(count, 500)):
                    try:
                        vname, vdata, vtype = winreg.EnumValue(key, i)
                        # vname is often file path.FriendlyAppName or ApplicationCompany
                        clean_target = vname.split(".ApplicationCompany")[0].split(".FriendlyAppName")[0]
                        if os.path.isabs(clean_target) and not os.path.exists(clean_target):
                            self.issues.append(RegistryIssue(
                                id=f"mui_{i}",
                                category="Bozuk MUI Cache Girişi",
                                root_name="HKCU",
                                sub_key=sub,
                                value_name=vname,
                                value_data=str(vdata),
                                value_type=vtype,
                                reason=f"Önbellekteki uygulama mevcut değil: {clean_target}"
                            ))
                    except OSError:
                        continue
        except OSError:
            pass

    def create_backup(self, issues_to_backup: list[RegistryIssue]) -> str:
        """Saves a JSON and .reg style backup of issues before repair."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"Registry_Backup_{timestamp}.json")
        reg_file = os.path.join(self.backup_dir, f"Registry_Backup_{timestamp}.reg")

        # 1. JSON Backup
        data = [asdict(issue) for issue in issues_to_backup]
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 2. Windows .reg File
        try:
            with open(reg_file, "w", encoding="utf-16") as rf:
                rf.write("Windows Registry Editor Version 5.00\r\n\r\n")
                for issue in issues_to_backup:
                    rf.write(f"[{issue.root_name}\\{issue.sub_key}]\r\n")
                    escaped_val = issue.value_name.replace('"', '\\"')
                    val_prefix = f'"{escaped_val}"' if issue.value_name else '@'
                    escaped_data = issue.value_data.replace('\\', '\\\\').replace('"', '\\"')
                    if issue.value_type in (winreg.REG_DWORD, getattr(winreg, 'REG_DWORD_LITTLE_ENDIAN', 4)):
                        try:
                            val_int = int(issue.value_data, 16) if str(issue.value_data).startswith("0x") else int(issue.value_data)
                            rf.write(f'{val_prefix}=dword:{val_int:08x}\r\n\r\n')
                        except (ValueError, TypeError):
                            rf.write(f'{val_prefix}="{escaped_data}"\r\n\r\n')
                    else:
                        rf.write(f'{val_prefix}="{escaped_data}"\r\n\r\n')
        except Exception:
            pass

        return backup_file

    def fix_issues(
        self,
        issues: list[RegistryIssue],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> tuple[int, int, str]:
        """
        Safely fixes (deletes broken values/keys) after auto-backing up.
        Returns: (fixed_count, failed_count, backup_file_path)
        """
        if not issues:
            return 0, 0, ""

        backup_path = self.create_backup(issues)
        fixed_count = 0
        failed_count = 0
        total = len(issues)

        for idx, issue in enumerate(issues):
            if progress_callback:
                progress_callback(issue.category, idx + 1, total)

            try:
                root = self._get_root_key(issue.root_name)
                try:
                    with winreg.OpenKey(root, issue.sub_key, 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, issue.value_name)
                        fixed_count += 1
                except Exception:
                    # If deleting default value failed and subkey is an empty orphaned container, delete key
                    if not issue.value_name and "\\" in issue.sub_key:
                        parent_sub, child_name = issue.sub_key.rsplit("\\", 1)
                        with winreg.OpenKey(root, parent_sub, 0, winreg.KEY_SET_VALUE) as pkey:
                            winreg.DeleteKey(pkey, child_name)
                            fixed_count += 1
                    else:
                        raise
            except Exception as e:
                log_debug(f"RegistryCleaner: Failed fixing issue {issue.id}: {e}")
                failed_count += 1

        # Remove fixed items from issues using O(N+M) set lookup
        fixed_ids = {i.id for i in issues}
        self.issues = [i for i in self.issues if i.id not in fixed_ids]
        return fixed_count, failed_count, backup_path
