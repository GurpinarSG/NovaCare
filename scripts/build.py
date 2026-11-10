"""
NovaCare System Suite 2026 - Master Unified Build Script
Builds both the standalone binary (NovaCare.exe) and the installer (NovaCare_Setup.exe).
"""
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from scripts.build_exe import build_executable
from scripts.build_installer import build_installer

def main():
    print("=" * 65)
    print("  NovaCare System Suite - Tam Derleme Başlatılıyor")
    print("=" * 65)

    print("\n[Adım 1/2] Ana Çalıştırılabilir Dosya Derleniyor (NovaCare.exe)...")
    exe_success = build_executable(onefile=True)
    if not exe_success:
        print("\n[X] HATA: NovaCare.exe derlenemedi!")
        sys.exit(1)

    print("\n[Adım 2/2] Kurulum Paketi Derleniyor (NovaCare_Setup.exe)...")
    installer_success = build_installer()
    if not installer_success:
        print("\n[X] HATA: NovaCare_Setup.exe derlenemedi!")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("  [✔] BÜTÜN DERLEMELER BAŞARIYLA TAMAMLANDI!")
    print(f"  • NovaCare.exe: {os.path.join(ROOT_DIR, 'NovaCare.exe')}")
    print(f"  • NovaCare_Setup.exe: {os.path.join(ROOT_DIR, 'NovaCare_Setup.exe')}")
    print("=" * 65)

if __name__ == "__main__":
    main()
