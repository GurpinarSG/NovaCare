"""
NovaCare System Suite - Disk Space Analyzer & Large Files Finder
Visualizes partition usage and finds the largest space-consuming files.
"""
import os
import psutil
from dataclasses import dataclass
from typing import Callable, Optional
from core.utils import format_bytes, safe_remove_file

@dataclass
class PartitionInfo:
    device: str
    mountpoint: str
    fstype: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    total_str: str
    used_str: str
    free_str: str

@dataclass
class LargeFileInfo:
    path: str
    name: str
    size_bytes: int
    size_str: str
    category: str
    extension: str

class DiskAnalyzer:
    CATEGORY_MAP = {
        'video': ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'),
        'archive': ('.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.vmdk', '.vhd', '.vhdx'),
        'executable': ('.exe', '.msi', '.dll', '.sys', '.cab'),
        'audio': ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'),
        'document': ('.pdf', '.docx', '.xlsx', '.pptx', '.doc', '.xls', '.txt', '.csv', '.sql', '.db')
    }

    def get_partitions(self) -> list[PartitionInfo]:
        """Returns disk space usage for all connected fixed/removable drives."""
        results: list[PartitionInfo] = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                results.append(PartitionInfo(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                    percent=usage.percent,
                    total_str=format_bytes(usage.total),
                    used_str=format_bytes(usage.used),
                    free_str=format_bytes(usage.free)
                ))
            except (PermissionError, OSError):
                continue
        return results

    def _determine_category(self, ext: str) -> str:
        ext = ext.lower()
        for cat, exts in self.CATEGORY_MAP.items():
            if ext in exts:
                if cat == 'video':
                    return "🎬 Video"
                elif cat == 'archive':
                    return "📦 Arşiv / İmaj"
                elif cat == 'executable':
                    return "⚙️ Yürütülebilir"
                elif cat == 'audio':
                    return "🎵 Ses"
                elif cat == 'document':
                    return "📄 Belge / Veri"
        return "📁 Diğer"

    def scan_largest_files(
        self,
        target_dir: str,
        limit: int = 100,
        min_size_mb: int = 50,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> list[LargeFileInfo]:
        """
        Scans target_dir for the largest files exceeding min_size_mb.
        Returns top sorted list up to limit.
        """
        min_bytes = min_size_mb * 1024 * 1024
        found: list[LargeFileInfo] = []
        scanned_count = 0

        if not target_dir or not os.path.exists(target_dir):
            return found

        # ⚡ Bolt Optimization: Replace os.walk with iterative os.scandir stack.
        # This utilizes the cached entry.stat() on Windows, avoiding thousands of redundant os.stat() syscalls.
        stack = [target_dir]
        while stack:
            if cancel_check and cancel_check():
                break
            current_dir = stack.pop()
            try:
                with os.scandir(current_dir) as it:
                    for entry in it:
                        if cancel_check and cancel_check():
                            break
                        try:
                            # Ignore symbolic links to avoid loops
                            if entry.is_symlink():
                                continue

                            if entry.is_file(follow_symlinks=False):
                                scanned_count += 1
                                if scanned_count % 500 == 0 and progress_callback:
                                    progress_callback(current_dir, scanned_count)

                                st = entry.stat(follow_symlinks=False)
                                sz = st.st_size
                                if sz >= min_bytes:
                                    _, ext = os.path.splitext(entry.name)
                                    cat = self._determine_category(ext)
                                    found.append(LargeFileInfo(
                                        path=entry.path,
                                        name=entry.name,
                                        size_bytes=sz,
                                        size_str=format_bytes(sz),
                                        category=cat,
                                        extension=ext.lower()
                                    ))
                            elif entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, FileNotFoundError, OSError):
                continue

        # Sort descending by size
        found.sort(key=lambda x: x.size_bytes, reverse=True)
        return found[:limit]

    def delete_file(self, file_path: str) -> bool:
        """Safely delete a large file."""
        return safe_remove_file(file_path)
