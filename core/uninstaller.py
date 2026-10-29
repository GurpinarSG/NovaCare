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
    selected: bool = True

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

    def launch_uninstaller(self, app: InstalledApp, quiet: bool = False) -> subprocess.Popen:
        """Launches the standard or quiet uninstaller in background."""
        cmd = app.quiet_uninstall_string if (quiet and app.quiet_uninstall_string) else app.uninstall_string
        if not cmd:
            raise ValueError("Kaldırma komutu mevcut değil.")

        expanded = os.path.expandvars(cmd)
        # Windows command runner - fix MsiExec /I to /X if needed
        if "msiexec" in expanded.lower() and "/i" in expanded.lower() and "/x" not in expanded.lower():
            import re
            expanded = re.sub(r'(?i)/i\s*', '/X ', expanded)

        try:
            return subprocess.Popen(expanded, shell=True)
        except OSError as e:
            if getattr(e, 'winerror', None) == 740 or '740' in str(e) or 'elevation' in str(e).lower():
                # UAC Elevation required - launch elevated via PowerShell Start-Process
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                ps_cmd = f"Start-Process cmd.exe -ArgumentList '/c', '{expanded}' -Verb RunAs"
                return subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], creationflags=flags)
            raise e

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
        """Scans filesystem and registry for remnants related to this app."""
        leftovers: list[LeftoverItem] = []
        app_name_parts = [p.lower() for p in app.name.split() if len(p) >= 3 and p.lower() not in _NAME_EXCLUSIONS]
        if not app_name_parts:
            app_name_parts = [app.name.lower()]

        # 1. Check InstallLocation
        if app.install_location and os.path.exists(app.install_location):
            leftovers.append(LeftoverItem(
                item_type="folder",
                path=app.install_location,
                details=f"Kurulum Klasörü ({app.install_location})"
            ))

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
                            # Match if matches app's prominent words
                            if any(part in dname for part in app_name_parts):
                                # Avoid false positives with common system folders
                                if dname not in _DIR_EXCLUSIONS:
                                    leftovers.append(LeftoverItem(
                                        item_type="folder",
                                        path=entry.path,
                                        details=f"Kalan Uygulama Verisi ({entry.name})"
                                    ))
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
                            if any(part in low_sub for part in app_name_parts):
                                if low_sub not in _REG_EXCLUSIONS:
                                    leftovers.append(LeftoverItem(
                                        item_type="registry",
                                        path=f"{rname}\\Software\\{sub_k}",
                                        details="Kayıt Defteri Anahtarı"
                                    ))
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
