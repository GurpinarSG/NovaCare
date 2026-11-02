"""
NovaCare System Suite - Duplicate File Finder Engine
Rapidly identifies identical duplicate files (photos, videos, documents, music, binaries)
using a 3-tier indexing algorithm (Size grouping -> Partial 8KB Hash -> Full MD5 Hash)
with protected system path guards and safe cleanup.
"""
import os
import hashlib
from dataclasses import dataclass, field
from typing import Callable, Optional
from core.utils import log_debug, safe_remove_file, to_long_path, is_reparse_point
from core.disk_analyzer import is_critical_system_file

# Compatibility alias
is_protected_system_file = is_critical_system_file

@dataclass
class DuplicateFileItem:
    path: str
    size: int
    mtime: float
    is_original: bool = False
    selected: bool = False

@dataclass
class DuplicateGroup:
    file_hash: str
    file_size: int
    files: list[DuplicateFileItem] = field(default_factory=list)

    @property
    def wasted_size(self) -> int:
        """Wasted space is total size minus 1 original copy."""
        if len(self.files) <= 1:
            return 0
        return self.file_size * (len(self.files) - 1)

class DuplicateFinder:
    # Directories strictly forbidden from scanning/deleting duplicates
    PROTECTED_DIR_PATTERNS = frozenset([
        r"\windows",
        r"\program files",
        r"\program files (x86)",
        r"\programdata\microsoft",
        r"$recycle.bin",
        r"system volume information",
        r"appdata\local\microsoft\windows"
    ])

    def __init__(self):
        pass

    @classmethod
    def is_protected_path(cls, path: str) -> bool:
        """Guards against touching Windows system binaries or core OS trees."""
        if not path or not isinstance(path, str):
            return True
        try:
            if is_critical_system_file(path):
                return True
        except Exception:
            pass

        norm = os.path.normcase(os.path.abspath(path))
        for p in cls.PROTECTED_DIR_PATTERNS:
            if p in norm:
                return True
        return False

    @staticmethod
    def _calc_partial_hash(file_path: str, chunk_size: int = 8192) -> Optional[str]:
        """Calculates MD5 hash of first 8KB to quickly reject mismatches."""
        try:
            target = to_long_path(file_path)
            hasher = hashlib.md5()
            with open(target, "rb") as f:
                chunk = f.read(chunk_size)
                hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None

    @staticmethod
    def _calc_full_md5(file_path: str, chunk_size: int = 65536) -> Optional[str]:
        """Calculates complete MD5 hash of a file in 64KB streams."""
        try:
            target = to_long_path(file_path)
            hasher = hashlib.md5()
            with open(target, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None

    def scan_duplicates(
        self,
        target_dirs: list[str],
        min_size_bytes: int = 1024,
        extensions: Optional[set[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> list[DuplicateGroup]:
        """
        Scans given directories and returns groups of duplicate files.
        Tier 1: Filter by size (skip unique file sizes).
        Tier 2: Partial 8KB hash on remaining candidates.
        Tier 3: Full MD5 verification on matching partial hashes.
        """
        size_map: dict[int, list[str]] = {}
        total_scanned = 0

        # Stage 1: Traverse and group files by exact size
        for directory in target_dirs:
            if not os.path.exists(directory):
                continue
            for root, dirs, files in os.walk(directory):
                if cancel_check and cancel_check():
                    return []

                # Skip protected, hidden, or reparse point (junction) directories to prevent infinite loops
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith('.')
                    and not is_reparse_point(os.path.join(root, d))
                    and not self.is_protected_path(os.path.join(root, d))
                ]

                for fname in files:
                    total_scanned += 1
                    if progress_callback and total_scanned % 100 == 0:
                        progress_callback(fname, total_scanned, 0)

                    if extensions:
                        _, ext = os.path.splitext(fname)
                        if ext.lower() not in extensions:
                            continue

                    full_path = os.path.join(root, fname)
                    if is_reparse_point(full_path) or self.is_protected_path(full_path):
                        continue

                    try:
                        sz = os.path.getsize(to_long_path(full_path))
                        if sz >= min_size_bytes:
                            size_map.setdefault(sz, []).append(full_path)
                    except (OSError, PermissionError):
                        continue


        # Filter out unique file sizes
        candidate_sizes = {sz: paths for sz, paths in size_map.items() if len(paths) > 1}
        size_map.clear()

        # Stage 2 & 3: Partial and Full Hashing
        groups: list[DuplicateGroup] = []
        found_duplicates_count = 0

        for sz, paths in candidate_sizes.items():
            if cancel_check and cancel_check():
                return groups

            # Tier 2: Partial hash grouping
            partial_map: dict[str, list[str]] = {}
            for path in paths:
                p_hash = self._calc_partial_hash(path)
                if p_hash:
                    partial_map.setdefault(p_hash, []).append(path)

            for p_hash, p_paths in partial_map.items():
                if len(p_paths) <= 1:
                    continue

                # Tier 3: Full MD5 verification
                full_map: dict[str, list[str]] = {}
                for path in p_paths:
                    if cancel_check and cancel_check():
                        return groups
                    # Optimization: If file size <= 8192 bytes, partial hash read the entire file and is already the full hash!
                    if sz <= 8192:
                        f_hash = p_hash
                    else:
                        f_hash = self._calc_full_md5(path)
                    if f_hash:
                        full_map.setdefault(f_hash, []).append(path)

                for f_hash, f_paths in full_map.items():
                    if len(f_paths) > 1:
                        # Create duplicate group
                        items: list[DuplicateFileItem] = []
                        for idx, p in enumerate(f_paths):
                            try:
                                mtime = os.path.getmtime(to_long_path(p))
                            except OSError:
                                mtime = 0.0
                            # First file or oldest file is considered the original by default
                            items.append(DuplicateFileItem(
                                path=p,
                                size=sz,
                                mtime=mtime,
                                is_original=(idx == 0),
                                selected=(idx > 0) # Duplicates pre-selected for cleanup
                            ))
                        # Sort by mtime so earliest is original
                        items.sort(key=lambda x: x.mtime)
                        for idx, item in enumerate(items):
                            item.is_original = (idx == 0)
                            item.selected = (idx > 0)

                        groups.append(DuplicateGroup(
                            file_hash=f_hash,
                            file_size=sz,
                            files=items
                        ))
                        found_duplicates_count += (len(items) - 1)
                        if progress_callback:
                            progress_callback(items[0].path, total_scanned, found_duplicates_count)

        return groups

    @staticmethod
    def auto_mark_selection(groups: list[DuplicateGroup], keep_mode: str = "oldest"):
        """
        Marks duplicates according to policy:
        'oldest': Keeps the oldest file, marks all others for deletion.
        'newest': Keeps the newest file, marks all others for deletion.
        'shortest_path': Keeps the file with the shortest path name.
        """
        for grp in groups:
            if len(grp.files) <= 1:
                continue

            if keep_mode == "oldest":
                sorted_files = sorted(grp.files, key=lambda f: f.mtime)
            elif keep_mode == "newest":
                sorted_files = sorted(grp.files, key=lambda f: f.mtime, reverse=True)
            elif keep_mode == "shortest_path":
                sorted_files = sorted(grp.files, key=lambda f: len(f.path))
            else:
                sorted_files = grp.files

            for idx, item in enumerate(sorted_files):
                item.is_original = (idx == 0)
                item.selected = (idx > 0)

    def delete_selected(self, groups: list[DuplicateGroup]) -> tuple[int, int, list[str]]:
        """
        Safely removes selected duplicate files.
        Never removes the designated original.
        Returns (deleted_count, freed_bytes, errors).
        """
        deleted_count = 0
        freed_bytes = 0
        errors = []

        for grp in groups:
            for item in grp.files:
                if item.selected and not item.is_original:
                    if self.is_protected_path(item.path):
                        errors.append(f"Korumalı sistem dosyası silinemez: {item.path}")
                        continue
                    try:
                        sz = item.size
                        if safe_remove_file(item.path):
                            deleted_count += 1
                            freed_bytes += sz
                        else:
                            errors.append(f"Silinemedi: {item.path}")
                    except Exception as e:
                        errors.append(f"{item.path}: {e}")
                        log_debug(f"DuplicateFinder delete error: {e}")

        return deleted_count, freed_bytes, errors
