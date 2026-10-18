"""
NovaCare System Suite - Utility Functions and Windows Helpers
"""
import os
import sys
import ctypes
import shutil
import subprocess
from typing import Optional

def is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def restart_as_admin() -> bool:
    """Relaunches the current application with elevated administrator rights via Windows UAC."""
    if sys.platform != 'win32':
        return False
    try:
        if getattr(sys, 'frozen', False):
            executable = sys.executable
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        else:
            executable = sys.executable
            script = os.path.abspath(sys.argv[0])
            params = f'"{script}" ' + " ".join([f'"{arg}"' for arg in sys.argv[1:]])

        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        if ret > 32:
            sys.exit(0)
            return True
    except Exception:
        pass
    return False

def elevate_if_needed():
    """If not running as administrator on Windows, triggers UAC prompt to elevate privileges if configured."""
    if sys.platform == 'win32' and not is_admin():
        try:
            from core.config import ConfigManager
            config = ConfigManager()
            if config.get("always_run_as_admin", True):
                restart_as_admin()
        except Exception:
            pass

def format_bytes(bytes_count: int | float) -> str:
    """Convert bytes count to human-readable string (KB, MB, GB, etc.)."""
    if bytes_count <= 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    val = float(bytes_count)
    while val >= 1024.0 and unit_index < len(units) - 1:
        val /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(val)} {units[unit_index]}"
    return f"{val:.2f} {units[unit_index]}"

def get_folder_size(path: str) -> tuple[int, int]:
    """Calculate total size in bytes and number of files in folder, ignoring errors."""
    total_size = 0
    total_files = 0
    if not os.path.exists(path):
        return 0, 0

    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                        total_files += 1
                    elif entry.is_dir(follow_symlinks=False):
                        s, f = get_folder_size(entry.path)
                        total_size += s
                        total_files += f
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, FileNotFoundError, OSError):
        pass

    return total_size, total_files

def to_long_path(path: str) -> str:
    """Prepends \\?\ prefix to Windows absolute paths exceeding MAX_PATH (240+ chars)."""
    if os.name == 'nt' and path and not path.startswith('\\\\?\\') and len(path) >= 240 and os.path.isabs(path):
        return '\\\\?\\' + os.path.normpath(path)
    return path

def safe_remove_file(file_path: str) -> bool:
    """
    Safely and rapidly remove a file.
    Directly attempts removal first for maximum I/O performance.
    Clears read-only attributes only when PermissionError is encountered.
    """
    try:
        target = to_long_path(file_path)
        try:
            os.remove(target)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            try:
                os.chmod(target, 0o777)
                os.remove(target)
                return True
            except Exception:
                return False
        except OSError:
            return False
    except Exception:
        return False

def _remove_readonly_cb(func, path, exc_info):
    """Callback for shutil.rmtree to clear read-only flag on stubborn files."""
    try:
        os.chmod(path, 0o777)
        func(path)
    except Exception:
        pass

def safe_remove_directory(dir_path: str) -> bool:
    """Safely remove a directory, clearing read-only flags inside if needed."""
    try:
        target = to_long_path(dir_path)
        if not os.path.exists(target):
            return True
        shutil.rmtree(target, onerror=_remove_readonly_cb)
        return not os.path.exists(target)
    except Exception:
        return False

def query_recycle_bin() -> tuple[int, int]:
    """Return (size_bytes, item_count) in Windows Recycle Bin."""
    try:
        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ('cbSize', ctypes.c_ulong),
                ('i64Size', ctypes.c_int64),
                ('i64NumItems', ctypes.c_int64)
            ]
        rb = SHQUERYRBINFO()
        rb.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(rb))
        if res == 0:
            return rb.i64Size, rb.i64NumItems
    except Exception:
        pass
    return 0, 0

def empty_recycle_bin(timeout_sec: float = 5.0) -> bool:
    """
    Empty Windows Recycle Bin silently with a safety timeout.
    Prevents hangs on unresponsive drives or corrupt recycle bins.
    """
    import concurrent.futures

    def _do_empty():
        try:
            SHERB_NOCONFIRMATION = 0x00000001
            SHERB_NOPROGRESSUI   = 0x00000002
            SHERB_NOSOUND        = 0x00000004
            flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
            res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            return res == 0
        except Exception:
            return False

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_empty)
            return future.result(timeout=timeout_sec)
    except Exception:
        return False

def ensure_ssl_ca_bundle() -> Optional[str]:
    """
    Ensures that a valid TLS/SSL CA certificate bundle is always accessible,
    persisting cacert.pem into %LOCALAPPDATA%\\NovaCare\\cacert.pem.
    Sets REQUESTS_CA_BUNDLE and SSL_CERT_FILE environment variables.
    """
    app_data = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NovaCare')
    os.makedirs(app_data, exist_ok=True)
    permanent_ca = os.path.join(app_data, 'cacert.pem')

    candidates = []

    # 1. assets/cacert.pem relative to ROOT_DIR or sys._MEIPASS
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(root_dir, 'assets', 'cacert.pem'))
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(os.path.join(meipass, 'assets', 'cacert.pem'))
        candidates.append(os.path.join(meipass, 'certifi', 'cacert.pem'))

    # 2. certifi.where() if valid
    try:
        import certifi
        c_where = certifi.where()
        if c_where and os.path.exists(c_where):
            candidates.append(c_where)
    except Exception:
        pass

    # Copy candidate to permanent location if needed
    for cand in candidates:
        if cand and os.path.exists(cand) and os.path.isfile(cand):
            try:
                if not os.path.exists(permanent_ca) or os.path.getsize(permanent_ca) != os.path.getsize(cand):
                    shutil.copy2(cand, permanent_ca)
                break
            except Exception:
                pass

    chosen = permanent_ca if os.path.exists(permanent_ca) else None
    if not chosen:
        for cand in candidates:
            if cand and os.path.exists(cand):
                chosen = cand
                break

    if chosen and os.path.exists(chosen):
        os.environ['REQUESTS_CA_BUNDLE'] = chosen
        os.environ['SSL_CERT_FILE'] = chosen
        return chosen
    return None

def log_debug(msg: str):
    """Appends a debug message to %LOCALAPPDATA%/NovaCare/startup.log safely."""
    try:
        import time
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NovaCare')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'startup.log'), "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def delete_registry_key_tree(root_key, subkey_path: str) -> bool:
    """
    Recursively deletes a Windows registry key and all of its subkeys and values.
    Standard winreg.DeleteKey fails if subkeys exist.
    Uses SHDeleteKeyW with recursive winreg enumeration fallback.
    """
    if sys.platform != 'win32' or not subkey_path:
        return False

    # 1. Try SHDeleteKeyW from shlwapi.dll (fastest, atomic Win32 API)
    try:
        shlwapi = ctypes.windll.shlwapi
        shlwapi.SHDeleteKeyW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        shlwapi.SHDeleteKeyW.restype = ctypes.c_long
        hkey_val = int(root_key)
        res = shlwapi.SHDeleteKeyW(ctypes.c_void_p(hkey_val), subkey_path)
        if res == 0:
            return True
    except Exception:
        pass

    # 2. Recursive fallback via winreg
    try:
        import winreg
        def _delete_subkeys(key_handle):
            while True:
                try:
                    sub = winreg.EnumKey(key_handle, 0)
                    with winreg.OpenKey(key_handle, sub, 0, winreg.KEY_READ | winreg.KEY_WRITE) as child:
                        _delete_subkeys(child)
                    winreg.DeleteKey(key_handle, sub)
                except OSError:
                    break

        with winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            _delete_subkeys(key)
        winreg.DeleteKey(root_key, subkey_path)
        return True
    except Exception:
        return False



