"""
NovaCare System Suite - Software Uninstaller & Deep Leftover Cleaner
Lists installed software, runs standard/silent uninstallers, and scans
file system and registry for residual leftovers.
"""
import os
import winreg
import subprocess
from dataclasses import dataclass
from core.utils import safe_remove_directory, safe_remove_file, delete_registry_key_tree, log_debug

_NAME_EXCLUSIONS = frozenset({'microsoft', 'windows', 'the', 'for', 'corporation', 'setup', 'edition', 'suite'})
_DIR_EXCLUSIONS = frozenset({'system32', 'syswow64', 'common files', 'microsoft', 'windows'})
_REG_EXCLUSIONS = frozenset({'microsoft', 'classes', 'registeredapplications', 'policies'})

@dataclass
class InstalledApp:
    id: str
    name: str
    version: str
    publisher: str
    install_date: str
    size_bytes: int
    uninstall_string: str
    quiet_uninstall_string: str
    install_location: str
    icon_path: str
    registry_path: str
    root_name: str

@dataclass
class LeftoverItem:
    item_type: str   # "file", "folder", "registry"
    path: str
    details: str
    selected: bool = False

class AppUninstaller:
    def __init__(self):
        self.apps: list[InstalledApp] = []

    @staticmethod
    def _get_reg_val(key, name: str, default: str = "") -> str:
        """Helper to read registry string value without re-allocating inner functions."""
        try:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val).strip()
        except OSError:
            return default

    def scan_installed_apps(self) -> list[InstalledApp]:
        self.apps.clear()
        targets = [
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        seen_names = set()

        for root_name, sub in targets:
            root = winreg.HKEY_LOCAL_MACHINE if root_name == "HKLM" else winreg.HKEY_CURRENT_USER
            try:
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as base_key:
                    sub_count, _, _ = winreg.QueryInfoKey(base_key)
                    for i in range(sub_count):
                        try:
                            app_sub = winreg.EnumKey(base_key, i)
                            full_sub = f"{sub}\\{app_sub}"
                            with winreg.OpenKey(root, full_sub, 0, winreg.KEY_READ) as app_key:
                                name = self._get_reg_val(app_key, "DisplayName")
                                if not name:
                                    continue

                                # Ignore system components or windows updates if SystemComponent == 1
                                try:
                                    sc, _ = winreg.QueryValueEx(app_key, "SystemComponent")
                                    if sc == 1:
                                        continue
                                except OSError:
                                    pass

                                # Avoid duplicate names
                                norm_name = name.strip().lower()
                                if norm_name in seen_names:
                                    continue
                                seen_names.add(norm_name)

                                version = self._get_reg_val(app_key, "DisplayVersion", "1.0")
                                publisher = self._get_reg_val(app_key, "Publisher", "Bilinmiyor")
                                inst_date = self._get_reg_val(app_key, "InstallDate", "")
                                if len(inst_date) == 8 and inst_date.isdigit():
                                    inst_date = f"{inst_date[:4]}-{inst_date[4:6]}-{inst_date[6:]}"

                                size_kb = 0
                                try:
                                    sz_val, _ = winreg.QueryValueEx(app_key, "EstimatedSize")
                                    size_kb = int(sz_val)
                                except (OSError, ValueError):
                                    pass

                                uninst_str = self._get_reg_val(app_key, "UninstallString")
                                quiet_uninst = self._get_reg_val(app_key, "QuietUninstallString")
                                inst_loc = self._get_reg_val(app_key, "InstallLocation")
                                icon_p = self._get_reg_val(app_key, "DisplayIcon")

                                self.apps.append(InstalledApp(
                                    id=f"{root_name}_{app_sub}",
                                    name=name,
                                    version=version,
                                    publisher=publisher,
                                    install_date=inst_date,
                                    size_bytes=size_kb * 1024,
                                    uninstall_string=uninst_str,
                                    quiet_uninstall_string=quiet_uninst,
                                    install_location=inst_loc,
                                    icon_path=icon_p,
                                    registry_path=full_sub,
                                    root_name=root_name
                                ))
                        except OSError:
                            continue
            except OSError:
                continue

        # Sort alphabetically by name
        self.apps.sort(key=lambda a: a.name.lower())
        return self.apps

    @staticmethod
    def _parse_uninstall_tokens(cmd: str) -> list[str]:
        """
        Robustly parses uninstaller command lines using shlex.split(posix=False).
        Properly handles unquoted executables with spaces, missing closing quotes, and flags.
        """
        import shlex
        cmd = cmd.strip()
        if not cmd:
            return []

        # If executable is quoted, handle potential unclosed trailing quotes
        if cmd.startswith('"'):
            end_q = cmd.find('"', 1)
            if end_q == -1:
                # Close unbalanced quote before the first flag or at the end
                first_flag = -1
                for flag_prefix in (' /', ' -'):
                    idx = cmd.find(flag_prefix, 1)
                    if idx != -1 and (first_flag == -1 or idx < first_flag):
                        first_flag = idx
                if first_flag != -1:
                    cmd = cmd[:first_flag] + '"' + cmd[first_flag:]
                else:
                    cmd = cmd + '"'
            try:
                return [t.strip('"') for t in shlex.split(cmd, posix=False) if t.strip()]
            except ValueError:
                pass

        # If unquoted, test whether candidate token sequences resolve to an existing executable
        tokens = cmd.split()
        if not tokens:
            return []

        found_exe = None
        arg_start_idx = 0
        # 1. Greedy check if a file exists on disk
        for i in range(len(tokens), 0, -1):
            cand = " ".join(tokens[:i]).strip('"')
            if cand and os.path.isfile(cand):
                found_exe = cand
                arg_start_idx = i
                break

        # 2. Check for common executable extension boundaries (.exe, .bat, .cmd, .msi)
        if not found_exe:
            KNOWN_EXTS = ('.exe', '.bat', '.cmd', '.msi')
            for i, tok in enumerate(tokens):
                clean_tok = tok.strip('"').lower()
                if any(clean_tok.endswith(ext) or (ext + '"') in clean_tok for ext in KNOWN_EXTS):
                    found_exe = " ".join(tokens[:i + 1]).strip('"')
                    arg_start_idx = i + 1
                    break

        if found_exe and arg_start_idx > 0:
            exe_part = found_exe
            rest = " ".join(tokens[arg_start_idx:]).strip()
            if rest:
                try:
                    args = [t.strip('"') for t in shlex.split(rest, posix=False) if t.strip()]
                except ValueError:
                    args = [t.strip('"') for t in rest.split() if t.strip()]
                return [exe_part] + args
            return [exe_part]

        # Standard shlex.split with quote balancing fallback
        try:
            return [t.strip('"') for t in shlex.split(cmd, posix=False) if t.strip()]
        except ValueError:
            return [t.strip('"') for t in cmd.replace('"', '').split() if t.strip()]

    def launch_uninstaller(self, app: InstalledApp, quiet: bool = False) -> subprocess.Popen:
        """Launches the standard or quiet uninstaller in background without shell=True."""
        cmd = app.quiet_uninstall_string if (quiet and app.quiet_uninstall_string) else app.uninstall_string
        if not cmd:
            raise ValueError("Kaldırma komutu mevcut değil.")

        expanded = os.path.expandvars(cmd)
        # Windows command runner - fix MsiExec /I to /X if needed
        if "msiexec" in expanded.lower() and "/i" in expanded.lower() and "/x" not in expanded.lower():
            import re
            expanded = re.sub(r'(?i)/i\s*', '/X ', expanded)

        tokens = self._parse_uninstall_tokens(expanded)
        if not tokens:
            raise ValueError("Kaldırma komutu çözümlenemedi.")

        try:
            return subprocess.Popen(tokens)
        except OSError as e:
            if getattr(e, 'winerror', None) == 740 or '740' in str(e) or 'elevation' in str(e).lower():
                # UAC Elevation required - launch elevated via PowerShell Start-Process safely without parameter injection
                import base64
                exe = tokens[0]
                args = tokens[1:]
                ps_exe = exe.replace("'", "''")
                cmd_line = subprocess.list2cmdline(args)
                ps_cmd_line = cmd_line.replace("'", "''")
                if ps_cmd_line:
                    ps_script = f"Start-Process -FilePath '{ps_exe}' -ArgumentList '{ps_cmd_line}' -Verb RunAs -Wait"
                else:
                    ps_script = f"Start-Process -FilePath '{ps_exe}' -Verb RunAs -Wait"

                encoded_ps = base64.b64encode(ps_script.encode('utf-16le')).decode('ascii')
                ps_tokens = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_ps]
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                return subprocess.Popen(ps_tokens, creationflags=flags)
            raise e

    # Alias for task consistency
    run_uninstaller = launch_uninstaller

    def scan_multiple_leftovers(self, apps: list[InstalledApp]) -> list[LeftoverItem]:
        """Scans remnants for multiple apps and removes duplicates."""
        all_leftovers: list[LeftoverItem] = []
        seen_paths = set()
        for app in apps:
            items = self.scan_leftovers(app)
            for it in items:
                norm_p = it.path.lower().strip()
                if norm_p not in seen_paths:
                    seen_paths.add(norm_p)
                    all_leftovers.append(it)
        return all_leftovers

    def scan_leftovers(self, app: InstalledApp) -> list[LeftoverItem]:
        """Scans filesystem and registry for remnants related to this app using safe full name / install path matching."""
        leftovers: list[LeftoverItem] = []
        import re

        norm_name = app.name.strip().lower()
        clean_name = re.sub(r'\b(v?\d+(\.\d+)*|64-bit|32-bit|x64|x86)\b', '', norm_name, flags=re.IGNORECASE).strip(' -_')

        # Critical system root path checker
        def is_critical_system_folder(path: str) -> bool:
            if not path or not isinstance(path, str):
                return True
            norm = os.path.normpath(os.path.abspath(path)).lower()
            if os.path.dirname(norm) == norm:
                return True
            system_roots = {
                os.path.normpath(os.environ.get('SYSTEMROOT', r'C:\Windows')).lower(),
                os.path.normpath(os.environ.get('ProgramFiles', r'C:\Program Files')).lower(),
                os.path.normpath(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')).lower(),
                os.path.normpath(os.environ.get('USERPROFILE', r'C:\Users')).lower(),
                os.path.normpath(os.environ.get('APPDATA', '')).lower(),
                os.path.normpath(os.environ.get('LOCALAPPDATA', '')).lower(),
                os.path.normpath(os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData')).lower(),
            }
            return norm in system_roots or len(norm.split(os.sep)) < 3

        # 1. Check InstallLocation
        loc_name = ""
        if app.install_location and os.path.exists(app.install_location):
            if not is_critical_system_folder(app.install_location):
                leftovers.append(LeftoverItem(
                    item_type="folder",
                    path=os.path.normpath(app.install_location),
                    details=f"Kurulum Klasörü ({app.install_location})",
                    selected=False
                ))
                cand_loc = os.path.basename(os.path.normpath(app.install_location)).lower()
                if cand_loc and len(cand_loc) >= 3 and cand_loc not in _NAME_EXCLUSIONS:
                    loc_name = cand_loc

        # Target candidate names for safe folder and registry key matching
        candidate_names = set()
        if clean_name and len(clean_name) >= 3 and clean_name not in _NAME_EXCLUSIONS:
            candidate_names.add(clean_name)
        if norm_name and len(norm_name) >= 3 and norm_name not in _NAME_EXCLUSIONS:
            candidate_names.add(norm_name)
        if loc_name:
            candidate_names.add(loc_name)

        if not candidate_names:
            return leftovers

        publisher_name = app.publisher.strip().lower() if (app.publisher and app.publisher.lower() not in ('bilinmiyor', 'unknown', 'microsoft corporation', 'microsoft')) else ""

        def matches_app(entry_lower: str) -> bool:
            if entry_lower in _DIR_EXCLUSIONS or entry_lower in _REG_EXCLUSIONS:
                return False
            for cand in candidate_names:
                if entry_lower == cand:
                    return True
                # Bounded matching with space or hyphen (e.g. "Google Chrome - Dev")
                if len(cand) >= 4 and (entry_lower.startswith(cand + " ") or entry_lower.startswith(cand + "-")):
                    return True
            return False

        # 2. Check standard program directories
        dirs_to_check = [
            os.environ.get('PROGRAMFILES', r'C:\Program Files'),
            os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
            os.environ.get('APPDATA', ''),
            os.environ.get('LOCALAPPDATA', ''),
            os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData')
        ]

        for base_dir in dirs_to_check:
            if not base_dir or not os.path.exists(base_dir):
                continue
            try:
                with os.scandir(base_dir) as it:
                    for entry in it:
                        if entry.is_dir():
                            dname = entry.name.lower()
                            if matches_app(dname):
                                if not is_critical_system_folder(entry.path):
                                    leftovers.append(LeftoverItem(
                                        item_type="folder",
                                        path=entry.path,
                                        details=f"Kalan Uygulama Verisi ({entry.name})",
                                        selected=False
                                    ))
                            elif publisher_name and dname == publisher_name:
                                # Inspect subdirectories under the publisher folder
                                try:
                                    with os.scandir(entry.path) as sub_it:
                                        for sub_entry in sub_it:
                                            if sub_entry.is_dir() and matches_app(sub_entry.name.lower()):
                                                if not is_critical_system_folder(sub_entry.path):
                                                    leftovers.append(LeftoverItem(
                                                        item_type="folder",
                                                        path=sub_entry.path,
                                                        details=f"Kalan Uygulama Verisi ({entry.name}\\{sub_entry.name})",
                                                        selected=False
                                                    ))
                                except (PermissionError, OSError):
                                    pass
            except (PermissionError, OSError):
                continue

        # 3. Check registry software keys
        for root, rname in [(winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")]:
            soft_path = r"Software"
            try:
                with winreg.OpenKey(root, soft_path, 0, winreg.KEY_READ) as k:
                    count, _, _ = winreg.QueryInfoKey(k)
                    for i in range(count):
                        try:
                            sub_k = winreg.EnumKey(k, i)
                            low_sub = sub_k.lower()
                            if matches_app(low_sub):
                                leftovers.append(LeftoverItem(
                                    item_type="registry",
                                    path=f"{rname}\\Software\\{sub_k}",
                                    details="Kayıt Defteri Anahtarı",
                                    selected=False
                                ))
                            elif publisher_name and low_sub == publisher_name:
                                try:
                                    with winreg.OpenKey(root, f"Software\\{sub_k}", 0, winreg.KEY_READ) as pub_k:
                                        pub_count, _, _ = winreg.QueryInfoKey(pub_k)
                                        for pi in range(pub_count):
                                            pub_sub = winreg.EnumKey(pub_k, pi)
                                            if matches_app(pub_sub.lower()):
                                                leftovers.append(LeftoverItem(
                                                    item_type="registry",
                                                    path=f"{rname}\\Software\\{sub_k}\\{pub_sub}",
                                                    details="Kayıt Defteri Anahtarı",
                                                    selected=False
                                                ))
                                except OSError:
                                    pass
                        except OSError:
                            continue
            except OSError:
                pass

        return leftovers

    def clean_leftovers(self, leftovers: list[LeftoverItem]) -> tuple[int, int]:
        """Cleans checked leftovers. Returns (cleaned_count, failed_count)."""
        cleaned = 0
        failed = 0
        for item in leftovers:
            if not item.selected:
                continue
            try:
                if item.item_type == "folder":
                    if safe_remove_directory(item.path):
                        cleaned += 1
                    else:
                        failed += 1
                elif item.item_type == "file":
                    if safe_remove_file(item.path):
                        cleaned += 1
                    else:
                        failed += 1
                elif item.item_type == "registry":
                    parts = item.path.split('\\', 1)
                    if len(parts) == 2:
                        rname, sub = parts
                        root = winreg.HKEY_CURRENT_USER if rname == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                        # Delete subkey tree recursively and safely
                        if delete_registry_key_tree(root, sub):
                            cleaned += 1
                        else:
                            failed += 1
            except Exception as e:
                log_debug(f"clean_leftovers failed for {item.path}: {e}")
                failed += 1

        return cleaned, failed
