"""
NovaCare System Suite - Windows Autostart Manager
Configures NovaCare to start automatically on Windows boot (minimized to system tray).
Uses Windows Task Scheduler with Highest Privileges to bypass Windows UAC boot blocking,
with dual-fallback to standard Windows Run registry key.
"""
import os
import sys
import winreg
import subprocess

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "NovaCare"
TASK_NAME = "NovaCare_Autostart"

def get_target_executable_and_args() -> tuple[str, str]:
    """Returns (executable_path, arguments) for autostart."""
    if getattr(sys, 'frozen', False):
        return sys.executable, "--autostart"

    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    compiled_exe = os.path.join(app_root, "NovaCare.exe")
    if os.path.exists(compiled_exe):
        return compiled_exe, "--autostart"

    pythonw = os.path.join(sys.exec_prefix, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    main_py = os.path.join(app_root, "main.py")
    return pythonw, f'"{main_py}" --autostart'

def get_autostart_command() -> str:
    """Returns the full execution command string for autostart."""
    exe, args = get_target_executable_and_args()
    return f'"{exe}" {args}'

def is_autostart_enabled() -> bool:
    """
    Checks whether NovaCare autostart is active via Windows Task Scheduler or Run key.
    """
    # 1. Check Windows Task Scheduler
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        res = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME],
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=5
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 2. Check Windows Registry Run key
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except OSError:
        pass

    return False

def set_autostart(enable: bool) -> bool:
    """
    Enables or disables automatic startup on Windows boot.
    When enabled, registers an elevated Task Scheduler job with Highest Privileges
    so Windows allows the administrative application to start without a UAC prompt on logon.
    """
    if sys.platform != 'win32':
        return False

    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    if enable:
        exe, args = get_target_executable_and_args()
        cmd_str = f'"{exe}" {args}'

        # 1. Register in Windows Task Scheduler (Elevated - Highest Privileges)
        try:
            ps_script = f"""
            $action = New-ScheduledTaskAction -Execute '{exe}' -Argument '{args}'
            $trigger = New-ScheduledTaskTrigger -AtLogOn
            $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
            Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], creationflags=flags, timeout=8)
        except Exception:
            try:
                subprocess.run(
                    ["schtasks", "/create", "/tn", TASK_NAME, "/tr", cmd_str, "/sc", "onlogon", "/rl", "highest", "/f"],
                    creationflags=flags,
                    timeout=5
                )
            except Exception:
                pass

        # 2. Also write to HKCU Run key as secondary fallback
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd_str)
        except Exception:
            pass

        return True
    else:
        # 1. Delete from Windows Task Scheduler
        try:
            subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], creationflags=flags, timeout=5)
        except Exception:
            pass

        # 2. Delete from Windows Registry Run key
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, APP_NAME)
        except OSError:
            pass

        return True

def ensure_default_autostart():
    """Ensures autostart is active by default on user system with proper elevated task scheduler integration."""
    if not is_autostart_enabled():
        set_autostart(True)
    else:
        # Verify Task Scheduler exists; if only registry exists, upgrade to elevated task
        try:
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            res = subprocess.run(
                ["schtasks", "/query", "/tn", TASK_NAME],
                capture_output=True,
                creationflags=flags,
                timeout=4
            )
            if res.returncode != 0:
                set_autostart(True)
        except Exception:
            pass
