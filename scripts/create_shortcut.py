"""
NovaCare - Create Windows Desktop and Folder Shortcuts with Application Icon
Ensures only clean 'NovaCare.lnk' shortcuts exist, removing old 'Başlat' variants.
"""
import os
import sys
import subprocess
import base64
from core.utils import get_system32_path

def create_shortcuts():
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pythonw = os.path.join(sys.exec_prefix, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    main_py = os.path.join(app_dir, "main.py")
    ico = os.path.join(app_dir, "assets", "icon.ico")

    # Cleanup legacy launcher files
    legacy_files = [
        os.path.join(app_dir, "Başlat.lnk"),
        os.path.join(app_dir, "Baslat.lnk"),
        os.path.join(app_dir, "Başlat_NovaCare.bat"),
        os.path.join(app_dir, "Baslat.bat"),
    ]
    for lf in legacy_files:
        if os.path.exists(lf):
            try:
                os.remove(lf)
                print(f"Removed legacy file: {os.path.basename(lf)}")
            except Exception:
                pass

    user_home = os.path.expanduser("~")
    desktop_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Masaüstü"),
        os.path.join(user_home, "Masaüstü"),
        os.path.join(user_home, "OneDrive", "Desktop")
    ]
    target_desktops = [d for d in desktop_dirs if os.path.exists(d)]

    # Clean legacy shortcuts on desktops
    for d in target_desktops:
        for legacy_name in ["Başlat.lnk", "Baslat.lnk", "Başlat_NovaCare.bat", "Baslat.bat"]:
            lp = os.path.join(d, legacy_name)
            if os.path.exists(lp):
                try:
                    os.remove(lp)
                    print(f"Removed legacy desktop shortcut: {lp}")
                except Exception:
                    pass

    def _ps_esc(s: str) -> str:
        return str(s).replace("'", "''")

    folder_lnk = os.path.join(app_dir, "NovaCare.lnk")
    ps_folder_lnk = _ps_esc(folder_lnk)
    ps_pythonw = _ps_esc(pythonw)
    ps_main_py = _ps_esc(main_py)
    ps_app_dir = _ps_esc(app_dir)
    ps_ico = _ps_esc(ico)

    # Build PowerShell script to create only NovaCare.lnk
    ps_commands = ['$Wsh = New-Object -ComObject WScript.Shell;']

    # 1. Project folder shortcut
    ps_commands.extend([
        f"$s = $Wsh.CreateShortcut('{ps_folder_lnk}');",
        f"$s.TargetPath = '{ps_pythonw}';",
        f"$s.Arguments = '\"' + '{ps_main_py}' + '\"';",
        f"$s.WorkingDirectory = '{ps_app_dir}';",
        f"$s.IconLocation = '{ps_ico}';",
        "$s.Description = 'NovaCare System Care Suite 2026';",
        "$s.Save();"
    ])

    # 2. Desktop shortcuts
    for d in target_desktops:
        desk_lnk = os.path.join(d, "NovaCare.lnk")
        ps_desk_lnk = _ps_esc(desk_lnk)
        ps_commands.extend([
            f"$d = $Wsh.CreateShortcut('{ps_desk_lnk}');",
            f"$d.TargetPath = '{ps_pythonw}';",
            f"$d.Arguments = '\"' + '{ps_main_py}' + '\"';",
            f"$d.WorkingDirectory = '{ps_app_dir}';",
            f"$d.IconLocation = '{ps_ico}';",
            "$d.Description = 'NovaCare System Care Suite 2026';",
            "$d.Save();"
        ])

    full_ps = " ".join(ps_commands)
    encoded_cmd = base64.b64encode(full_ps.encode("utf-16le")).decode("ascii")
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.run([get_system32_path("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_cmd], creationflags=flags, check=True)
    print("NovaCare shortcut with icon created successfully!")

if __name__ == "__main__":
    create_shortcuts()
