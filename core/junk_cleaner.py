"""
NovaCare System Suite - Comprehensive Junk & Cache Cleaner
Scans and cleans temporary files, browser caches, logs, crash dumps, and recycle bin.
"""
import os
import sys
import glob
from dataclasses import dataclass, field
from typing import Callable, Optional
from core.utils import (
    format_bytes,
    get_folder_size,
    safe_remove_file,
    safe_remove_directory,
    query_recycle_bin,
    empty_recycle_bin
)

@dataclass
class CleanerCategory:
    id: str
    name: str
    description: str
    icon: str
    paths: list[str] = field(default_factory=list)
    is_recycle_bin: bool = False
    size: int = 0
    file_count: int = 0
    selected: bool = True
    found_files: list[str] = field(default_factory=list)

class JunkCleaner:
    def __init__(self):
        self.categories: list[CleanerCategory] = self._init_categories()

    def _init_categories(self) -> list[CleanerCategory]:
        local_app = os.environ.get('LOCALAPPDATA', '')
        app_data = os.environ.get('APPDATA', '')
        win_dir = os.environ.get('SYSTEMROOT', r'C:\Windows')
        temp_dir = os.environ.get('TEMP', '')

        cats = [
            CleanerCategory(
                id="user_temp",
                name="Kullanıcı Geçici Dosyaları (Temp)",
                description="Uygulamaların geride bıraktığı geçici çalışma dosyaları",
                icon="🗑️",
                paths=[temp_dir] if temp_dir else []
            ),
            CleanerCategory(
                id="system_temp",
                name="Sistem Geçici Dosyaları",
                description="Windows sistem ve servislerinin oluşturduğu geçici dosyalar",
                icon="⚙️",
                paths=[os.path.join(win_dir, 'Temp')]
            ),
            CleanerCategory(
                id="recycle_bin",
                name="Geri Dönüşüm Kutusu",
                description="Silinmiş ve çöp kutusunda bekleyen dosyalar",
                icon="♻️",
                is_recycle_bin=True
            ),
            CleanerCategory(
                id="win_update_cache",
                name="Windows Update İndirme Önbelleği",
                description="Başarıyla yüklenmiş güncelleme kurulum paketleri",
                icon="🔄",
                paths=[os.path.join(win_dir, 'SoftwareDistribution', 'Download')]
            ),
            CleanerCategory(
                id="crash_dumps",
                name="Çökme Raporları ve Hata Dökümleri",
                description="Uygulama çökmelerinde oluşturulan Minidump ve hata günlükleri",
                icon="⚠️",
                paths=[
                    os.path.join(local_app, 'CrashDumps'),
                    os.path.join(local_app, 'Microsoft', 'Windows', 'WER'),
                    os.path.join(win_dir, 'Minidump')
                ]
            ),
            CleanerCategory(
                id="thumbnails",
                name="Küçük Resim Önbelleği (Thumbnails)",
                description="Dosya Gezgini tarafından oluşturulan küçük resim önbellek dosyaları",
                icon="🖼️",
                paths=[os.path.join(local_app, 'Microsoft', 'Windows', 'Explorer')]
            ),
            CleanerCategory(
                id="system_logs",
                name="Sistem Günlükleri ve Loglar",
                description="Eski olay kayıtları, CBS logları ve kurulum günlükleri",
                icon="📋",
                paths=[
                    os.path.join(win_dir, 'Logs'),
                    os.path.join(win_dir, 'Panther'),
                    os.path.join(local_app, 'Microsoft', 'Windows', 'Logs')
                ]
            ),
            CleanerCategory(
                id="browser_chrome",
                name="Google Chrome Önbelleği",
                description="Web gezinti verileri, GPU önbelleği ve kod önbellekleri",
                icon="🌐",
                paths=[
                    os.path.join(local_app, 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
                    os.path.join(local_app, 'Google', 'Chrome', 'User Data', 'Default', 'Code Cache'),
                    os.path.join(local_app, 'Google', 'Chrome', 'User Data', 'Default', 'GPUCache')
                ]
            ),
            CleanerCategory(
                id="browser_edge",
                name="Microsoft Edge Önbelleği",
                description="Edge tarayıcısı web sayfaları ve medya önbellekleri",
                icon="🌐",
                paths=[
                    os.path.join(local_app, 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
                    os.path.join(local_app, 'Microsoft', 'Edge', 'User Data', 'Default', 'Code Cache'),
                    os.path.join(local_app, 'Microsoft', 'Edge', 'User Data', 'Default', 'GPUCache')
                ]
            ),
            CleanerCategory(
                id="browser_brave",
                name="Brave Tarayıcı Önbelleği",
                description="Brave Browser geçici internet dosyaları ve önbellekleri",
                icon="🦁",
                paths=[
                    os.path.join(local_app, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Cache'),
                    os.path.join(local_app, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Code Cache')
                ]
            ),
            CleanerCategory(
                id="browser_firefox",
                name="Mozilla Firefox Önbelleği",
                description="Firefox profil önbellekleri",
                icon="🦊",
                paths=glob.glob(os.path.join(local_app, 'Mozilla', 'Firefox', 'Profiles', '*', 'cache2'))
            ),
            CleanerCategory(
                id="apps_cache",
                name="Geliştirici & Uygulama Önbellekleri",
                description="Discord, Spotify, Pip ve Npm geçici paket önbellekleri",
                icon="📦",
                paths=[
                    os.path.join(local_app, 'pip', 'cache'),
                    os.path.join(app_data, 'npm-cache'),
                    os.path.join(app_data, 'discord', 'Cache'),
                    os.path.join(app_data, 'discord', 'Code Cache'),
                    os.path.join(local_app, 'Spotify', 'Storage')
                ]
            )
        ]
        return cats

    def scan_all(self, progress_callback: Optional[Callable[[str, int, int], None]] = None) -> list[CleanerCategory]:
        """
        Scan all categories.
        progress_callback(current_cat_name, current_index, total_categories)
        """
        total = len(self.categories)
        for idx, cat in enumerate(self.categories):
            if progress_callback:
                progress_callback(cat.name, idx + 1, total)

            cat.size = 0
            cat.file_count = 0
            cat.found_files.clear()

            if cat.is_recycle_bin:
                sz, count = query_recycle_bin()
                cat.size = sz
                cat.file_count = count
                continue

            for p in cat.paths:
                if not os.path.exists(p):
                    continue

                if cat.id == "thumbnails":
                    # Only match thumbcache_*.db
                    try:
                        for entry in os.scandir(p):
                            if entry.is_file() and entry.name.lower().startswith('thumbcache_'):
                                try:
                                    st = entry.stat()
                                    cat.size += st.st_size
                                    cat.file_count += 1
                                    cat.found_files.append(entry.path)
                                except OSError:
                                    pass
                    except OSError:
                        pass
                    continue

                # Normal directories
                self._scan_folder_recursive(p, cat)

        return self.categories

    def _scan_folder_recursive(self, path: str, cat: CleanerCategory, depth: int = 0):
        if depth > 10:  # Prevent cyclic or extreme folder structures
            return

        # CRITICAL SAFETY: Never scan running PyInstaller bundle or NovaCare directories
        norm_path = os.path.normpath(path).lower()
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass and norm_path.startswith(os.path.normpath(meipass).lower()):
            return
        base_name = os.path.basename(norm_path)
        if base_name.startswith('_mei') or 'novacare' in base_name:
            return

        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        e_name = entry.name.lower()
                        # Strict exclusion of active PyInstaller runtime directories
                        if e_name.startswith('_mei') or 'novacare' in e_name:
                            continue

                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            cat.size += sz
                            cat.file_count += 1
                            cat.found_files.append(entry.path)
                        elif entry.is_dir(follow_symlinks=False):
                            self._scan_folder_recursive(entry.path, cat, depth + 1)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        except (PermissionError, FileNotFoundError, OSError):
            pass

    def clean_categories(
        self,
        category_ids: set[str],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> tuple[int, int, int]:
        """
        Cleans selected categories.
        Returns: (freed_bytes, cleaned_files_count, failed_files_count)
        """
        total_freed = 0
        cleaned_count = 0
        failed_count = 0

        target_cats = [c for c in self.categories if c.id in category_ids]
        total_ops = len(target_cats)

        meipass = getattr(sys, '_MEIPASS', None)
        meipass_norm = os.path.normpath(meipass).lower() if meipass else None

        for idx, cat in enumerate(target_cats):
            if progress_callback:
                progress_callback(cat.name, idx + 1, total_ops)

            if cat.is_recycle_bin:
                # Query before empty
                sz, count = query_recycle_bin()
                if empty_recycle_bin():
                    total_freed += sz
                    cleaned_count += count
                cat.size = 0
                cat.file_count = 0
                continue

            for f_path in cat.found_files:
                try:
                    norm_fp = os.path.normpath(f_path).lower()
                    if meipass_norm and norm_fp.startswith(meipass_norm):
                        continue
                    if '\\_mei' in norm_fp or '/_mei' in norm_fp or 'novacare' in norm_fp:
                        continue

                    if os.path.isfile(f_path):
                        sz = os.path.getsize(f_path)
                        if safe_remove_file(f_path):
                            total_freed += sz
                            cleaned_count += 1
                        else:
                            failed_count += 1
                except Exception:
                    failed_count += 1

            # Remove empty subdirectories in cleaned paths
            for p in cat.paths:
                if os.path.exists(p) and cat.id not in ("system_temp", "user_temp"):
                    try:
                        for root, dirs, files in os.walk(p, topdown=False, followlinks=False, onerror=lambda _: None):
                            for d in dirs:
                                dir_to_check = os.path.join(root, d)
                                try:
                                    if not os.listdir(dir_to_check):
                                        os.rmdir(dir_to_check)
                                except OSError:
                                    pass
                    except Exception:
                        pass

            # Reset counts after cleanup
            cat.size = 0
            cat.file_count = 0
            cat.found_files.clear()

        return total_freed, cleaned_count, failed_count
