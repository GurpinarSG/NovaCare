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
from core.utils import log_debug, get_system32_path, get_console_encoding

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
    Uses ultra-fast Windows Registry TaskCache lookup (< 0.05ms) with CLI fallback.
    """
    # 1. Ultra-fast Task Scheduler check via Registry TaskCache
    try:
        task_tree_path = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree\{TASK_NAME}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, task_tree_path, 0, winreg.KEY_READ) as _:
            return True
    except Exception:
        pass

    # 2. Windows Task Scheduler CLI fallback
    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        res = subprocess.run(
            [get_system32_path("schtasks"), "/query", "/tn", TASK_NAME],
            capture_output=True,
            text=True,
            encoding=get_console_encoding(),
            errors="replace",
            creationflags=flags,
            timeout=3
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 3. Check Windows Registry Run key
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

        task_created = False
        # 1. Register in Windows Task Scheduler (Elevated - Highest Privileges)
        try:
            import base64
            ps_exe = exe.replace("'", "''")
            ps_args = args.replace("'", "''")
            ps_task = TASK_NAME.replace("'", "''")
            ps_script = f"""
            $action = New-ScheduledTaskAction -Execute '{ps_exe}' -Argument '{ps_args}'
            $trigger = New-ScheduledTaskTrigger -AtLogOn
            $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
            Register-ScheduledTask -TaskName '{ps_task}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
            """
            encoded_ps = base64.b64encode(ps_script.encode('utf-16le')).decode('ascii')
            r = subprocess.run([get_system32_path("powershell"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_ps], creationflags=flags, timeout=8)
            task_created = (r.returncode == 0)
        except Exception as e:
            log_debug(f"Autostart: PowerShell task creation failed: {e}")
            try:
                r = subprocess.run(
                    [get_system32_path("schtasks"), "/create", "/tn", TASK_NAME, "/tr", cmd_str, "/sc", "onlogon", "/rl", "highest", "/f"],
                    creationflags=flags,
                    timeout=5
                )
                task_created = (r.returncode == 0)
            except Exception as e2:
                log_debug(f"Autostart: schtasks creation fallback failed: {e2}")
                task_created = False

        if task_created:
            # Task scheduler is active and elevated; remove duplicate HKCU Run entry so Windows won't launch 2 instances
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
        else:
            # Fallback to HKCU Run key only if Task Scheduler could not be created
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd_str)
            except Exception as e:
                log_debug(f"Autostart: HKCU Run fallback failed: {e}")

        return True
    else:
        # 1. Delete from Windows Task Scheduler
        try:
            subprocess.run([get_system32_path("schtasks"), "/delete", "/tn", TASK_NAME, "/f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, timeout=5)
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
    try:
        from core.config import ConfigManager
        if not ConfigManager().get("autostart_on_boot", True):
            return
    except Exception:
        return

    # Fast check if elevated task scheduler exists in Registry TaskCache
    try:
        task_tree_path = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\TaskCache\Tree\{TASK_NAME}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, task_tree_path, 0, winreg.KEY_READ) as _:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
            return
    except Exception:
        pass

    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        res = subprocess.run(
            [get_system32_path("schtasks"), "/query", "/tn", TASK_NAME],
            capture_output=True,
            text=True,
            encoding=get_console_encoding(),
            errors="replace",
            creationflags=flags,
            timeout=3
        )
        if res.returncode == 0:
            # Elevated task exists! Clean up duplicate HKCU Run key if present
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
            return
    except Exception:
        pass

    set_autostart(True)
