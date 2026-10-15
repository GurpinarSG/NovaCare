"""
NovaCare - Create Windows Desktop and Folder Shortcuts with Application Icon
"""
import os
import sys
import subprocess

def create_shortcuts():
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pythonw = os.path.join(sys.exec_prefix, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    main_py = os.path.join(app_dir, "main.py")
    ico = os.path.join(app_dir, "assets", "icon.ico")

    # 1. Project folder shortcut
    folder_lnk = os.path.join(app_dir, "NovaCare.lnk")

    # 2. User Desktop shortcut (handle OneDrive or standard Desktop)
    user_home = os.path.expanduser("~")
    desktop_dirs = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "OneDrive", "Masaüstü"),
        os.path.join(user_home, "Masaüstü"),
        os.path.join(user_home, "OneDrive", "Desktop")
    ]

    target_desktops = [d for d in desktop_dirs if os.path.exists(d)]

    ps_commands = [
        f'$Wsh = New-Object -ComObject WScript.Shell;',
        f'$s = $Wsh.CreateShortcut("{folder_lnk}");',
        f'$s.TargetPath = "{pythonw}";',
        f'$s.Arguments = \'"{main_py}"\';',
        f'$s.WorkingDirectory = "{app_dir}";',
        f'$s.IconLocation = "{ico}";',
        f'$s.Description = "NovaCare System Care Suite 2026";',
        f'$s.Save();'
    ]

    for d in target_desktops:
        desk_lnk = os.path.join(d, "NovaCare.lnk")
        ps_commands.extend([
            f'$d = $Wsh.CreateShortcut("{desk_lnk}");',
            f'$d.TargetPath = "{pythonw}";',
            f'$d.Arguments = \'"{main_py}"\';',
            f'$d.WorkingDirectory = "{app_dir}";',
            f'$d.IconLocation = "{ico}";',
            f'$d.Description = "NovaCare System Care Suite 2026";',
            f'$d.Save();'
        ])

    full_ps = " ".join(ps_commands)
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", full_ps], check=True)
    print("Shortcuts created successfully!")

if __name__ == "__main__":
    create_shortcuts()
