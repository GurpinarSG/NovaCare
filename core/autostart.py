"""
NovaCare System Suite - Windows Autostart Manager
Configures NovaCare to start automatically on Windows boot (minimized to system tray).
"""
import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "NovaCare"

def get_autostart_command() -> str:
    """Returns the full execution command for autostart using pythonw (no console window)."""
    # 1. Look for pythonw in current python environment
    pythonw = os.path.join(sys.exec_prefix, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_py = os.path.join(app_root, "main.py")

    return f'"{pythonw}" "{main_py}" --autostart'

def is_autostart_enabled() -> bool:
    """Checks whether NovaCare is currently registered in Windows Run key."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except OSError:
        return False

def set_autostart(enable: bool) -> bool:
    """Enables or disables automatic startup on Windows boot."""
    try:
        if enable:
            cmd = get_autostart_command()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            return True
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
            return True
    except Exception:
        return False

def ensure_default_autostart():
    """Ensures autostart is active by default on user system."""
    if not is_autostart_enabled():
        set_autostart(True)
