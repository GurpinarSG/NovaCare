"""
NovaCare System Suite - Disk Space Analyzer & Large Files Finder
Visualizes partition usage and finds the largest space-consuming files.
"""
import os
import sys
import stat
import time
import psutil
from functools import lru_cache
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

        stack = [target_dir]
        s_isreg = stat.S_ISREG
        s_isdir = stat.S_ISDIR

        while stack:
            if cancel_check and cancel_check():
                break
            current = stack.pop()
            try:
                scan_target = to_long_path(current) if len(current) >= 240 else current
                with os.scandir(scan_target) as it:
                    for entry in it:
                        if cancel_check and cancel_check():
                            break
                        try:
                            # Single stat(follow_symlinks=False) per entry avoids multiple OS calls
                            if entry.is_symlink():
                                continue
                            st = entry.stat(follow_symlinks=False)
                            if getattr(st, 'st_reparse_tag', 0) != 0:
                                continue
                            mode = st.st_mode
                            if s_isdir(mode):
                                stack.append(entry.path)
                            elif s_isreg(mode):
                                scanned_count += 1
                                if scanned_count % 500 == 0 and progress_callback:
                                    progress_callback(current, scanned_count)

                                sz = st.st_size
                                if sz >= min_bytes:
                                    fname = entry.name
                                    _, ext = os.path.splitext(fname)
                                    cat = self._determine_category(ext)
                                    item = LargeFileInfo(
                                        path=entry.path,
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

_APP_DIR_NORM = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@lru_cache(maxsize=8)
def _build_protected_tree_prefixes(
    sys_root: str,
    prog_files: str,
    prog_files_x86: str,
    prog_w6432: str,
    prog_data: str,
    local_appdata: str,
    frozen: bool,
    executable: str,
) -> tuple[tuple[str, str], ...]:
    """Cache normalized base tree exact/prefix pairs keyed on relevant env & runtime state."""
    trees = [
        os.path.normcase(os.path.abspath(sys_root)),
        os.path.normcase(os.path.abspath(prog_files)),
        os.path.normcase(os.path.abspath(prog_files_x86)),
        os.path.normcase(os.path.abspath(prog_data)),
        _APP_DIR_NORM,
    ]
    if prog_w6432:
        trees.append(os.path.normcase(os.path.abspath(prog_w6432)))
    if frozen and executable:
        trees.append(os.path.normcase(os.path.abspath(os.path.dirname(executable))))
    if local_appdata:
        trees.append(os.path.normcase(os.path.abspath(os.path.join(local_appdata, 'NovaCare'))))

    pairs = []
    seen = set()
    for t in trees:
        if t and t not in seen:
            seen.add(t)
            prefix = t if t.endswith(('\\', '/')) else (t + '\\')
            pairs.append((t, prefix))
    return tuple(pairs)

def _matches_protected_candidate(candidate: str, tree_pairs: tuple[tuple[str, str], ...]) -> bool:
    """Fast check of a single normalized candidate path against critical names, folders, and trees."""
    slash_idx = candidate.rfind('\\')
    fname = candidate[slash_idx + 1:] if slash_idx != -1 else candidate
    if fname in CRITICAL_SYSTEM_FILES:
        return True

    norm_slashes = candidate.replace('/', '\\') if '/' in candidate else candidate
    if not PROTECTED_FOLDER_NAMES.isdisjoint(norm_slashes.split('\\')):
        return True

    for tree, tree_prefix in tree_pairs:
        if norm_slashes == tree or norm_slashes.startswith(tree_prefix):
            return True
    return False

_PARENT_REALPATH_CACHE: dict[str, tuple[float, str]] = {}

def _resolve_parent_realpath(parent_dir: str) -> str:
    """Short-TTL (1.0s) cache of os.path.realpath(parent_dir) to avoid walking identical ancestors per file."""
    now = time.monotonic()
    cached = _PARENT_REALPATH_CACHE.get(parent_dir)
    if cached is not None and (now - cached[0]) < 1.0:
        return cached[1]
    try:
        resolved = os.path.normcase(os.path.realpath(parent_dir))
    except Exception:
        resolved = os.path.normcase(os.path.abspath(parent_dir))
    if len(_PARENT_REALPATH_CACHE) >= 2048:
        _PARENT_REALPATH_CACHE.clear()
    _PARENT_REALPATH_CACHE[parent_dir] = (now, resolved)
    return resolved

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

        tree_pairs = _build_protected_tree_prefixes(
            os.environ.get('SystemRoot', r'C:\Windows'),
            os.environ.get('ProgramFiles', r'C:\Program Files'),
            os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
            os.environ.get('ProgramW6432', ''),
            os.environ.get('ProgramData', os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData')),
            os.environ.get('LOCALAPPDATA', ''),
            bool(getattr(sys, 'frozen', False)),
            sys.executable or '',
        )

        abs_path = os.path.abspath(clean_path)
        norm_path = os.path.normcase(abs_path)
        if _matches_protected_candidate(norm_path, tree_pairs):
            return True

        # Fast leaf reparse check: only call full realpath(abs_path) if the leaf itself is a symlink/junction
        try:
            st_leaf = os.lstat(abs_path)
            leaf_is_link = stat.S_ISLNK(st_leaf.st_mode) or getattr(st_leaf, 'st_reparse_tag', 0) != 0
        except OSError:
            leaf_is_link = False

        if leaf_is_link:
            try:
                norm_real = os.path.normcase(os.path.realpath(abs_path))
            except Exception:
                norm_real = norm_path
        else:
            parent_dir, fname = os.path.split(abs_path)
            if not fname:
                norm_real = _resolve_parent_realpath(abs_path)
            else:
                norm_parent = _resolve_parent_realpath(parent_dir)
                norm_real = os.path.join(norm_parent, os.path.normcase(fname))

        if norm_real != norm_path and _matches_protected_candidate(norm_real, tree_pairs):
            return True

        return False
    except Exception:
        return True

# Compatibility alias
is_protected_system_file = is_critical_system_file

