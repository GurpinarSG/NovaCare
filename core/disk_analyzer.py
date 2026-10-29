"""
NovaCare System Suite - Disk Space Analyzer & Large Files Finder
Visualizes partition usage and finds the largest space-consuming files.
"""
import os
import psutil
from dataclasses import dataclass
from typing import Callable, Optional
import heapq
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

# Precomputed flat dictionary for O(1) extension category lookup
_EXT_TO_CATEGORY: dict[str, str] = {
    # Video
    '.mp4': "🎬 Video", '.mkv': "🎬 Video", '.avi': "🎬 Video", '.mov': "🎬 Video",
    '.wmv': "🎬 Video", '.flv': "🎬 Video", '.webm': "🎬 Video", '.m4v': "🎬 Video",
    # Archive
    '.zip': "📦 Arşiv / İmaj", '.rar': "📦 Arşiv / İmaj", '.7z': "📦 Arşiv / İmaj",
    '.tar': "📦 Arşiv / İmaj", '.gz': "📦 Arşiv / İmaj", '.iso': "📦 Arşiv / İmaj",
    '.vmdk': "📦 Arşiv / İmaj", '.vhd': "📦 Arşiv / İmaj", '.vhdx': "📦 Arşiv / İmaj",
    # Executable
    '.exe': "⚙️ Yürütülebilir", '.msi': "⚙️ Yürütülebilir", '.dll': "⚙️ Yürütülebilir",
    '.sys': "⚙️ Yürütülebilir", '.cab': "⚙️ Yürütülebilir",
    # Audio
    '.mp3': "🎵 Ses", '.wav': "🎵 Ses", '.flac': "🎵 Ses", '.aac': "🎵 Ses",
    '.ogg': "🎵 Ses", '.m4a': "🎵 Ses",
    # Document / Data
    '.pdf': "📄 Belge / Veri", '.docx': "📄 Belge / Veri", '.xlsx': "📄 Belge / Veri",
    '.pptx': "📄 Belge / Veri", '.doc': "📄 Belge / Veri", '.xls': "📄 Belge / Veri",
    '.txt': "📄 Belge / Veri", '.csv': "📄 Belge / Veri", '.sql': "📄 Belge / Veri",
    '.db': "📄 Belge / Veri"
}

class DiskAnalyzer:
    CATEGORY_MAP = {
        'video': ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v'),
        'archive': ('.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.vmdk', '.vhd', '.vhdx'),
        'executable': ('.exe', '.msi', '.dll', '.sys', '.cab'),
        'audio': ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'),
        'document': ('.pdf', '.docx', '.xlsx', '.pptx', '.doc', '.xls', '.txt', '.csv', '.sql', '.db')
    }

    @staticmethod
    def _is_symlink(p: str) -> bool:
        """Fast, static symlink check to prevent loop closures inside directory walk."""
        try:
            return os.path.islink(p)
        except Exception:
            return True

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
        """O(1) dictionary lookup for file extension category."""
        return _EXT_TO_CATEGORY.get(ext.lower(), "📁 Diğer")

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
        Returns top sorted list up to limit using heap selection for optimal memory usage.
        """
        min_bytes = min_size_mb * 1024 * 1024
        found: list[LargeFileInfo] = []
        scanned_count = 0

        if not target_dir or not os.path.exists(target_dir):
            return found

        for root, dirs, files in os.walk(target_dir, onerror=lambda _: None):
            if cancel_check and cancel_check():
                break
            # Prune directory symlinks/junctions to prevent infinite loops or redundant scans
            dirs[:] = [d for d in dirs if not self._is_symlink(os.path.join(root, d))]
            for fname in files:
                if cancel_check and cancel_check():
                    break
                scanned_count += 1
                if scanned_count % 500 == 0 and progress_callback:
                    progress_callback(root, scanned_count)

                fpath = os.path.join(root, fname)
                try:
                    # Ignore symbolic links to avoid loops
                    st = os.stat(fpath, follow_symlinks=False)
                    sz = st.st_size
                    if sz >= min_bytes:
                        _, ext = os.path.splitext(fname)
                        cat = self._determine_category(ext)
                        found.append(LargeFileInfo(
                            path=fpath,
                            name=fname,
                            size_bytes=sz,
                            size_str=format_bytes(sz),
                            category=cat,
                            extension=ext.lower()
                        ))
                except (PermissionError, FileNotFoundError, OSError):
                    continue

        if len(found) > limit:
            return heapq.nlargest(limit, found, key=lambda x: x.size_bytes)
        found.sort(key=lambda x: x.size_bytes, reverse=True)
        return found

    def delete_file(self, file_path: str) -> bool:
        """Safely delete a large file."""
        return safe_remove_file(file_path)
