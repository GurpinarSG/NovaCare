"""
NovaCare System Suite - Disk Space Analyzer & Large Files Finder
Visualizes partition usage and finds the largest space-consuming files.
"""
import os
import sys
import psutil
from dataclasses import dataclass
from typing import Callable, Optional
import heapq
from core.utils import format_bytes, safe_remove_file, is_reparse_point, to_long_path

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
        """Fast check to prevent loop closures inside directory walk for symlinks and NTFS junctions."""
        return is_reparse_point(p)

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
        if not target_dir or not os.path.exists(target_dir) or limit <= 0:
            return []

        scanned_count = 0
        heap: list[tuple[int, int, LargeFileInfo]] = []
        counter = 0

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
                    # Ignore symbolic links and reparse points to avoid loops
                    if is_reparse_point(fpath):
                        continue
                    st = os.stat(fpath, follow_symlinks=False)
                    sz = st.st_size
                    if sz >= min_bytes:
                        _, ext = os.path.splitext(fname)
                        cat = self._determine_category(ext)
                        item = LargeFileInfo(
                            path=fpath,
                            name=fname,
                            size_bytes=sz,
                            size_str=format_bytes(sz),
                            category=cat,
                            extension=ext.lower()
                        )
                        if len(heap) < limit:
                            heapq.heappush(heap, (sz, counter, item))
                            counter += 1
                        elif sz > heap[0][0]:
                            heapq.heappushpop(heap, (sz, counter, item))
                            counter += 1
                except (PermissionError, FileNotFoundError, OSError):
                    continue

        return [entry[2] for entry in sorted(heap, key=lambda x: x[0], reverse=True)]

    def delete_file_safely(self, file_path: str) -> tuple[bool, str]:
        """Safely delete a large file, preventing deletion of critical system or app files."""
        if not file_path or not isinstance(file_path, str):
            return False, "Geçersiz dosya yolu."
        long_target = to_long_path(file_path)
        if not os.path.isfile(long_target):
            return False, "Dosya bulunamadı veya bir dizin."
        if is_critical_system_file(file_path):
            return False, "Kritik sistem veya uygulama dosyaları güvenlik nedeniyle silinemez."
        try:
            if safe_remove_file(file_path):
                return True, "Dosya başarıyla silindi."
            return False, "Dosya silinirken hata oluştu veya dosya başka bir işlem tarafından kilitlenmiş."
        except Exception as e:
            return False, f"Silme hatası: {e}"

    def delete_file(self, file_path: str) -> bool:
        """Safely delete a large file, preventing deletion of critical system or app files."""
        ok, _ = self.delete_file_safely(file_path)
        return ok


CRITICAL_SYSTEM_FILES = frozenset({
    'pagefile.sys', 'hiberfil.sys', 'swapfile.sys', 'dumpstack.log'
})

PROTECTED_FOLDER_NAMES = frozenset({
    '$recycle.bin', 'system volume information', 'program files',
    'program files (x86)', 'programdata', 'windows'
})

def is_critical_system_file(path: str) -> bool:
    """
    Determines if a given path is a protected Windows system file or NovaCare core file
    that must never be deleted via Disk Analyzer.
    Checks both direct path and canonical resolved realpath to protect against symlinks.
    Protects Windows system root, Program Files, ProgramData, Recycle Bin, and NovaCare directories.
    Handles long-path prefixes (\\\\?\\ and \\\\?\\UNC\\) safely.
    """
    if not path or not isinstance(path, str):
        return True
    try:
        clean_path = path
        if clean_path.startswith('\\\\?\\UNC\\'):
            clean_path = '\\\\' + clean_path[8:]
        elif clean_path.startswith('\\\\?\\'):
            clean_path = clean_path[4:]

        norm_path = os.path.normcase(os.path.abspath(clean_path))
        try:
            norm_real = os.path.normcase(os.path.realpath(clean_path))
        except Exception:
            norm_real = norm_path

        candidates = {norm_path, norm_real}

        sys_root = os.environ.get('SystemRoot', r'C:\Windows')
        norm_sys_root = os.path.normcase(os.path.abspath(sys_root))

        prog_files = os.environ.get('ProgramFiles', r'C:\Program Files')
        norm_prog_files = os.path.normcase(os.path.abspath(prog_files))

        prog_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
        norm_prog_files_x86 = os.path.normcase(os.path.abspath(prog_files_x86))

        prog_w6432 = os.environ.get('ProgramW6432', '')
        norm_prog_w6432 = os.path.normcase(os.path.abspath(prog_w6432)) if prog_w6432 else None

        prog_data = os.environ.get('ProgramData', os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData'))
        norm_prog_data = os.path.normcase(os.path.abspath(prog_data))

        app_dir = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

        exe_dir = None
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.normcase(os.path.abspath(os.path.dirname(sys.executable)))

        novacare_data = None
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        if local_appdata:
            novacare_data = os.path.normcase(os.path.abspath(os.path.join(local_appdata, 'NovaCare')))

        protected_trees = [
            norm_sys_root, norm_prog_files, norm_prog_files_x86, norm_prog_data, app_dir
        ]
        if norm_prog_w6432:
            protected_trees.append(norm_prog_w6432)
        if exe_dir:
            protected_trees.append(exe_dir)
        if novacare_data:
            protected_trees.append(novacare_data)

        for candidate in candidates:
            fname = os.path.basename(candidate)
            # 1. Prohibited root system files
            if fname in CRITICAL_SYSTEM_FILES:
                return True

            # 2. Directory segment check (protects $Recycle.Bin, System Volume Information, Program Files, etc. across any drive)
            parts = [seg.strip() for seg in candidate.replace('/', '\\').split('\\') if seg.strip()]
            for part in parts:
                if part in PROTECTED_FOLDER_NAMES:
                    return True

            # 3. Explicit base protected directory trees (SystemRoot, Program Files, ProgramData, App Dir, etc.)
            for tree in protected_trees:
                try:
                    if os.path.commonpath([candidate, tree]) == tree:
                        return True
                except ValueError:
                    pass

        return False
    except Exception:
        return True

# Compatibility alias
is_protected_system_file = is_critical_system_file

