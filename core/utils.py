"""
NovaCare System Suite - Utility Functions and Windows Helpers
"""
import os
import sys
import ctypes
import shutil
import subprocess

def is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

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

def safe_remove_file(file_path: str) -> bool:
    """Safely remove a file, attempting to clear read-only flag if needed."""
    try:
        if not os.path.exists(file_path):
            return True
        try:
            os.chmod(file_path, 0o777)
        except Exception:
            pass
        os.remove(file_path)
        return True
    except Exception:
        return False

def safe_remove_directory(dir_path: str) -> bool:
    """Safely remove an empty or non-empty directory."""
    try:
        if not os.path.exists(dir_path):
            return True
        shutil.rmtree(dir_path, ignore_errors=True)
        return not os.path.exists(dir_path)
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

def empty_recycle_bin() -> bool:
    """Empty Windows Recycle Bin silently."""
    try:
        SHERB_NOCONFIRMATION = 0x00000001
        SHERB_NOPROGRESSUI   = 0x00000002
        SHERB_NOSOUND        = 0x00000004
        flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        return res == 0
    except Exception:
        return False
