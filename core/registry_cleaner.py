"""
NovaCare System Suite - Safe Windows Registry Cleaner & Optimizer
Scans for invalid shortcuts, missing shared DLLs, obsolete startup keys, broken application paths,
and safely creates a rollback backup before fixing any issues.
"""
import os
import shutil
import winreg
import json
import time

from functools import lru_cache
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from core.utils import log_debug, delete_registry_key_tree
from core.backup_manager import compute_backup_hmac

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
    all_values: Optional[list] = None

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
        """Extract clean file path from command line arguments with greedy token joining and LRU caching."""
        cmd = raw_cmd.strip()
        if not cmd:
            return ""
        if cmd.startswith('"'):
            end_quote = cmd.find('"', 1)
            if end_quote != -1:
                return cmd[1:end_quote].strip()
            return cmd.strip('"')

        # Check if entire unquoted string is an existing file
        if os.path.exists(cmd):
            return cmd

        tokens = cmd.split()
        if not tokens:
            return ""

        # 1. Greedy check: join tokens from longest to shortest and check if a matching file exists on disk
        for i in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:i]).strip('"')
            if candidate and os.path.isfile(candidate):
                return candidate

        # 2. If file does not exist, look for common executable/library extensions
        # to find the boundary of the unquoted program path before arguments
        KNOWN_EXTS = ('.exe', '.dll', '.bat', '.cmd', '.vbs', '.cpl', '.scr', '.msi', '.com', '.ps1', '.msc', '.jar')
        for i, token in enumerate(tokens):
            clean_tok = token.strip('"').lower()
            for ext in KNOWN_EXTS:
                if clean_tok.endswith(ext) or (ext + '"') in clean_tok:
                    return " ".join(tokens[:i + 1]).strip('"')
                if (ext + ',') in clean_tok:
                    tok_part = token.split(',')[0].strip('"')
                    return " ".join(tokens[:i] + [tok_part]).strip('"')
                if (ext + '/') in clean_tok:
                    tok_part = token.split('/')[0].strip('"')
                    return " ".join(tokens[:i] + [tok_part]).strip('"')

        # 3. If no file or extension found, check if directory exists (longest directory match)
        for i in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:i]).strip('"')
            if candidate and os.path.isdir(candidate):
                return candidate

        return tokens[0].strip('"')

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
                                if exe_path:
                                    exists = os.path.exists(exe_path) or bool(shutil.which(exe_path))
                                    if not exists and not exe_path.lower().startswith(('rundll32', 'regsvr32', 'cmd', 'powershell')):
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
                                    base_bin = os.path.basename(clean_p).lower()
                                    SYSTEM_EXCLUDED_BINS = {"rundll32.exe", "msiexec.exe", "regsvr32.exe", "cmd.exe", "powershell.exe"}
                                    # Check if exe path doesn't exist and isn't a known system launcher or in PATH
                                    if clean_p and not os.path.exists(clean_p):
                                        if base_bin in SYSTEM_EXCLUDED_BINS or shutil.which(clean_p) or shutil.which(base_bin):
                                            continue
                                        try:
                                            disp_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                                        except OSError:
                                            disp_name = app_guid

                                        # Collect all values of this uninstaller subkey for complete backup
                                        all_vals = []
                                        try:
                                            _, val_count, _ = winreg.QueryInfoKey(app_key)
                                            for vi in range(val_count):
                                                vn, vd, vt = winreg.EnumValue(app_key, vi)
                                                all_vals.append({"name": vn, "type": vt, "data": vd})
                                        except OSError:
                                            pass

                                        self.issues.append(RegistryIssue(
                                            id=f"uninst_{root_name}_{app_guid}_{i}",
                                            category="Bozuk Kaldırma Bilgisi",
                                            root_name=root_name,
                                            sub_key=full_sub,
                                            value_name="",
                                            value_data=str(uninst_str),
                                            value_type=utype,
                                            reason=f"Kaldırma programı mevcut değil ({disp_name}): {clean_p}",
                                            all_values=all_vals
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

        # 1. JSON Backup with HMAC-SHA256 signature
        data = []
        for issue in issues_to_backup:
            item = asdict(issue)
            all_vals = item.get("all_values")
            # If all_values was not pre-populated, attempt to read existing values before deletion
            if not all_vals and (issue.id.startswith("uninst_") or issue.category == "Bozuk Kaldırma Bilgisi" or (not issue.value_name and "uninstall" in issue.sub_key.lower())):
                try:
                    root = self._get_root_key(issue.root_name)
                    with winreg.OpenKey(root, issue.sub_key, 0, winreg.KEY_READ) as k:
                        _, val_count, _ = winreg.QueryInfoKey(k)
                        vals = []
                        for vi in range(val_count):
                            vn, vd, vt = winreg.EnumValue(k, vi)
                            vals.append({"name": vn, "type": vt, "data": vd})
                        if vals:
                            all_vals = vals
                            item["all_values"] = vals
                except OSError:
                    pass
            if all_vals:
                item["subkey_values"] = all_vals
            data.append(item)

        hmac_sig = compute_backup_hmac(data)
        payload = {
            "version": 1,
            "timestamp": timestamp,
            "hmac": hmac_sig,
            "items": data
        }
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        # 2. Windows .reg File
        try:
            with open(reg_file, "w", encoding="utf-16") as rf:
                rf.write("Windows Registry Editor Version 5.00\r\n\r\n")
                for issue_dict in data:
                    r_name = issue_dict.get("root_name", "")
                    s_key = issue_dict.get("sub_key", "")
                    rf.write(f"[{r_name}\\{s_key}]\r\n")
                    all_vals = issue_dict.get("all_values")
                    if all_vals and isinstance(all_vals, list):
                        for v in all_vals:
                            vn = v.get("name", "")
                            vd = v.get("data", "")
                            vt = v.get("type", winreg.REG_SZ)
                            esc_val = vn.replace('"', '\\"')
                            val_prefix = f'"{esc_val}"' if vn else '@'
                            esc_data = str(vd).replace('\\', '\\\\').replace('"', '\\"')
                            if vt in (winreg.REG_DWORD, getattr(winreg, 'REG_DWORD_LITTLE_ENDIAN', 4)):
                                try:
                                    val_int = int(vd, 16) if str(vd).startswith("0x") else int(vd)
                                    rf.write(f'{val_prefix}=dword:{val_int:08x}\r\n')
                                except (ValueError, TypeError):
                                    rf.write(f'{val_prefix}="{esc_data}"\r\n')
                            else:
                                rf.write(f'{val_prefix}="{esc_data}"\r\n')
                        rf.write("\r\n")
                    else:
                        vname = issue_dict.get("value_name", "")
                        vdata = str(issue_dict.get("value_data", ""))
                        vtype = issue_dict.get("value_type", winreg.REG_SZ)
                        escaped_val = vname.replace('"', '\\"')
                        val_prefix = f'"{escaped_val}"' if vname else '@'
                        escaped_data = vdata.replace('\\', '\\\\').replace('"', '\\"')
                        if vtype in (winreg.REG_DWORD, getattr(winreg, 'REG_DWORD_LITTLE_ENDIAN', 4)):
                            try:
                                val_int = int(vdata, 16) if str(vdata).startswith("0x") else int(vdata)
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

        successfully_fixed_ids = set()
        for idx, issue in enumerate(issues):
            if progress_callback:
                progress_callback(issue.category, idx + 1, total)

            try:
                root = self._get_root_key(issue.root_name)
                # Leftover uninstaller entries: delete entire uninstaller subkey to avoid orphaned Add/Remove Programs entry
                if issue.id.startswith("uninst_") or issue.category == "Bozuk Kaldırma Bilgisi" or (not issue.value_name and "\\" in issue.sub_key):
                    if delete_registry_key_tree(root, issue.sub_key):
                        fixed_count += 1
                        successfully_fixed_ids.add(issue.id)
                    else:
                        raise OSError(f"Could not safely delete registry key tree: {issue.sub_key}")
                else:
                    try:
                        with winreg.OpenKey(root, issue.sub_key, 0, winreg.KEY_SET_VALUE) as key:
                            winreg.DeleteValue(key, issue.value_name)
                            fixed_count += 1
                            successfully_fixed_ids.add(issue.id)
                    except Exception:
                        if not issue.value_name and "\\" in issue.sub_key:
                            if delete_registry_key_tree(root, issue.sub_key):
                                fixed_count += 1
                                successfully_fixed_ids.add(issue.id)
                            else:
                                raise OSError(f"Could not safely delete registry key tree: {issue.sub_key}")
                        else:
                            raise
            except Exception as e:
                log_debug(f"RegistryCleaner: Failed fixing issue {issue.id}: {e}")
                failed_count += 1


        # Remove fixed items from issues using O(N+M) set lookup
        self.issues = [i for i in self.issues if i.id not in successfully_fixed_ids]
        return fixed_count, failed_count, backup_path
