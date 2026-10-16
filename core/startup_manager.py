"""
NovaCare System Suite - Startup Manager
Inspects, toggles (enable/disable), adds and removes Windows startup entries.
"""
import os
import winreg
import glob
from dataclasses import dataclass
from typing import Optional

@dataclass
class StartupItem:
    id: str
    name: str
    command: str
    location: str
    location_type: str   # "registry" or "folder"
    source_key_or_path: str
    root_name: Optional[str]  # "HKCU", "HKLM"
    enabled: bool
    boot_impact: str     # "Yüksek", "Orta", "Düşük"
    publisher: str = "Bilinmiyor"

class StartupManager:
    DISABLED_KEY = r"Software\NovaCare\DisabledStartup"

    def __init__(self):
        self.items: list[StartupItem] = []

    def _get_root_key(self, root_name: str):
        return winreg.HKEY_CURRENT_USER if root_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE

    def _estimate_impact(self, name: str, command: str) -> str:
        cmd_lower = command.lower()
        name_lower = name.lower()
        high_impact_keywords = ['steam', 'epic', 'discord', 'spotify', 'antivirus', 'cortana', 'teams', 'onedrive', 'update', 'chrome']
        low_impact_keywords = ['realtek', 'audio', 'touchpad', 'synaptics', 'f.lux', 'tray']

        for kw in high_impact_keywords:
            if kw in cmd_lower or kw in name_lower:
                return "Yüksek"
        for kw in low_impact_keywords:
            if kw in cmd_lower or kw in name_lower:
                return "Düşük"
        return "Orta"

    def scan_all(self) -> list[StartupItem]:
        self.items.clear()
        self._scan_registry_entries()
        self._scan_startup_folders()
        self._scan_disabled_entries()
        return self.items

    def _scan_registry_entries(self):
        targets = [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Kayıt Defteri (Geçerli Kullanıcı)"),
            ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "Kayıt Defteri (Tüm Sistem)"),
            ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Kayıt Defteri (32-Bit Sistem)")
        ]
        for root_name, sub, loc_desc in targets:
            try:
                root = self._get_root_key(root_name)
                with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as key:
                    count, _, _ = winreg.QueryInfoKey(key)
                    for i in range(count):
                        try:
                            val_name, val_data, _ = winreg.EnumValue(key, i)
                            cmd = str(val_data)
                            impact = self._estimate_impact(val_name, cmd)
                            self.items.append(StartupItem(
                                id=f"reg_{root_name}_{val_name}_{i}",
                                name=val_name,
                                command=cmd,
                                location=loc_desc,
                                location_type="registry",
                                source_key_or_path=sub,
                                root_name=root_name,
                                enabled=True,
                                boot_impact=impact
                            ))
                        except OSError:
                            continue
            except OSError:
                continue

    def _scan_startup_folders(self):
        user_startup = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup')
        common_startup = os.path.join(os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData'), r'Microsoft\Windows\Start Menu\Programs\Startup')

        folders = [
            (user_startup, "Başlangıç Klasörü (Kullanıcı)"),
            (common_startup, "Başlangıç Klasörü (Ortak)")
        ]

        for folder, desc in folders:
            if not os.path.exists(folder):
                continue
            try:
                for entry in os.scandir(folder):
                    if entry.is_file():
                        name = entry.name
                        enabled = True
                        if name.endswith('.disabled'):
                            name = name[:-9]
                            enabled = False

                        if name.lower().endswith(('.lnk', '.exe', '.bat', '.cmd', '.vbs')) or not enabled:
                            display_name = os.path.splitext(name)[0]
                            self.items.append(StartupItem(
                                id=f"folder_{entry.path}",
                                name=display_name,
                                command=entry.path,
                                location=desc,
                                location_type="folder",
                                source_key_or_path=entry.path,
                                root_name=None,
                                enabled=enabled,
                                boot_impact=self._estimate_impact(display_name, entry.path)
                            ))
            except Exception:
                continue

    def _scan_disabled_entries(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.DISABLED_KEY, 0, winreg.KEY_READ) as key:
                count, _, _ = winreg.QueryInfoKey(key)
                for i in range(count):
                    try:
                        vname, vdata, _ = winreg.EnumValue(key, i)
                        # vdata is stored as "original_root|original_subkey|command"
                        parts = str(vdata).split('|', 2)
                        orig_root = parts[0] if len(parts) > 0 else "HKCU"
                        orig_sub = parts[1] if len(parts) > 1 else r"Software\Microsoft\Windows\CurrentVersion\Run"
                        orig_cmd = parts[2] if len(parts) > 2 else ""

                        self.items.append(StartupItem(
                            id=f"disabled_{vname}_{i}",
                            name=vname,
                            command=orig_cmd,
                            location="Devre Dışı Bırakıldı",
                            location_type="registry_disabled",
                            source_key_or_path=orig_sub,
                            root_name=orig_root,
                            enabled=False,
                            boot_impact="Devre Dışı"
                        ))
                    except OSError:
                        continue
        except OSError:
            pass

    def toggle_item(self, item: StartupItem) -> bool:
        """Toggle startup item between Enabled and Disabled."""
        try:
            if item.location_type == "folder":
                current_path = item.source_key_or_path
                if item.enabled:
                    # Disable by appending .disabled
                    new_path = current_path + ".disabled"
                    os.rename(current_path, new_path)
                    item.source_key_or_path = new_path
                    item.enabled = False
                else:
                    # Enable by removing .disabled
                    if current_path.endswith('.disabled'):
                        new_path = current_path[:-9]
                        os.rename(current_path, new_path)
                        item.source_key_or_path = new_path
                    item.enabled = True
                return True

            elif item.location_type == "registry":
                # Disable by moving to NovaCare\DisabledStartup
                root = self._get_root_key(item.root_name or "HKCU")
                # 1. Read and delete original
                with winreg.OpenKey(root, item.source_key_or_path, 0, winreg.KEY_SET_VALUE) as src_key:
                    winreg.DeleteValue(src_key, item.name)

                # 2. Store in Disabled key
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.DISABLED_KEY) as dis_key:
                    store_val = f"{item.root_name}|{item.source_key_or_path}|{item.command}"
                    winreg.SetValueEx(dis_key, item.name, 0, winreg.REG_SZ, store_val)

                item.location_type = "registry_disabled"
                item.enabled = False
                item.location = "Devre Dışı Bırakıldı"
                return True

            elif item.location_type == "registry_disabled":
                # Enable by moving back
                # 1. Delete from Disabled key
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.DISABLED_KEY, 0, winreg.KEY_SET_VALUE) as dis_key:
                    winreg.DeleteValue(dis_key, item.name)

                # 2. Restore to original key
                root = self._get_root_key(item.root_name or "HKCU")
                with winreg.CreateKey(root, item.source_key_or_path) as orig_key:
                    winreg.SetValueEx(orig_key, item.name, 0, winreg.REG_SZ, item.command)

                item.location_type = "registry"
                item.enabled = True
                item.location = "Kayıt Defteri"
                return True

        except Exception:
            return False

    def delete_item(self, item: StartupItem) -> bool:
        """Permanently delete startup item."""
        try:
            if item.location_type == "folder":
                if os.path.exists(item.source_key_or_path):
                    os.remove(item.source_key_or_path)
                return True
            elif item.location_type == "registry":
                root = self._get_root_key(item.root_name or "HKCU")
                with winreg.OpenKey(root, item.source_key_or_path, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, item.name)
                return True
            elif item.location_type == "registry_disabled":
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.DISABLED_KEY, 0, winreg.KEY_SET_VALUE) as dis_key:
                    winreg.DeleteValue(dis_key, item.name)
                return True
        except Exception:
            return False
        return False
