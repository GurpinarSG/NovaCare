"""
NovaCare System Care Suite 2026 - Main Entry Point
High-DPI enabled desktop optimization application inspired by CCleaner,
Glary Utilities, and Advanced SystemCare.
"""
import sys
import os
import ctypes
import argparse

# Configure UTF-8 for Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Ensure local imports work regardless of cwd
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from core.utils import format_bytes
from core.memory_booster import MemoryBooster
from core.junk_cleaner import JunkCleaner

def set_windows_app_id():
    """Set process AppUserModelID so Windows taskbar displays proper icon and name."""
    try:
        app_id = "NovaCare.SystemCare.Suite.2026"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

def cli_boost_ram():
    print("=" * 50)
    print("NovaCare RAM Booster (CLI Modu)")
    print("=" * 50)
    booster = MemoryBooster()
    freed, count = booster.optimize_ram()
    print(f"Optimize Edilen Süreç: {count} adet")
    print(f"Boşaltılan Bellek: {format_bytes(freed)}")
    print("İşlem tamamlandı!")

def cli_quick_scan():
    print("=" * 50)
    print("NovaCare Hızlı Sistem Taraması (CLI Modu)")
    print("=" * 50)
    cleaner = JunkCleaner()
    cats = cleaner.scan_all()
    total_sz = sum(c.size for c in cats)
    total_fl = sum(c.file_count for c in cats)
    print(f"Tespit Edilen Çöp Dosya Sayısı: {total_fl:,}")
    print(f"Temizlenebilir Toplam Alan: {format_bytes(total_sz)}")
    print("Detaylar:")
    for c in cats:
        if c.size > 0:
            print(f"  - {c.name}: {format_bytes(c.size)} ({c.file_count} dosya)")

def cli_check_update():
    from core.updater import GitHubUpdater
    from core.config import CURRENT_VERSION, ConfigManager
    config = ConfigManager()
    repo = config.get("github_repo", "Gurpi/antigravity")
    print("=" * 50)
    print("NovaCare Güncelleştirme Denetimi (CLI Modu)")
    print("=" * 50)
    print(f"Mevcut Sürüm: v{CURRENT_VERSION}")
    print(f"GitHub Deposu: {repo}")
    print("GitHub API sorgulanıyor...")
    updater = GitHubUpdater(repo)
    try:
        info = updater.check_for_updates()
        if info.available:
            print(f"🟡 YENİ SÜRÜM MEVCUT: v{info.latest_version}")
            print(f"Başlık: {info.release_title}")
            print(f"Yayın Tarihi: {info.published_at}")
            print(f"İndirme Bağlantısı: {info.download_url}")
            print("\nDeğişiklik Günlüğü:")
            print(info.changelog)
        else:
            print(f"🟢 Sürümünüz güncel! (v{CURRENT_VERSION})")
    except Exception as e:
        print(f"⚠️ Güncelleme denetlenemedi: {e}")

from core.autostart import ensure_default_autostart

def main():
    parser = argparse.ArgumentParser(description="NovaCare System Care Suite 2026")
    parser.add_argument("--boost-ram", action="store_true", help="Hızlı RAM temizliği yapar ve çıkar")
    parser.add_argument("--quick-scan", action="store_true", help="Sistem çöp dosyalarını tarar ve raporlar")
    parser.add_argument("--check-update", action="store_true", help="GitHub üzerinden güncellemeleri denetler")
    parser.add_argument("--autostart", action="store_true", help="Windows açılışında arka planda sessiz başlatır")
    args = parser.parse_args()

    if args.boost_ram:
        cli_boost_ram()
        return

    if args.quick_scan:
        cli_quick_scan()
        return

    if args.check_update:
        cli_check_update()
        return

    # Enable autostart by default on user system
    try:
        ensure_default_autostart()
    except Exception:
        pass

    # High-DPI attributes before QApplication
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("NovaCare System Care")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("NovaCare")

    window = MainWindow()
    if args.autostart:
        # Started automatically on Windows boot: run quietly in System Tray
        window.hide()
        if hasattr(window, 'tray_icon'):
            window.tray_icon.showMessage(
                "NovaCare",
                "NovaCare arka planda çalışıyor ve sistemi koruyor.",
                window.tray_icon.Information,
                3000
            )
    else:
        window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
