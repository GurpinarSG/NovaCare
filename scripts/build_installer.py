"""
NovaCare System Suite 2026 - Installer Builder
Compiles installer_wizard.py and the core NovaCare application payload into
a standalone setup file: dist/NovaCare_Setup_v1.0.1.exe
"""
import os
import sys
import shutil
import subprocess

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from core.utils import get_system32_path

def build_installer():
    print("=" * 65)
    print("  NovaCare System Care Suite 2026 - Kurulum Dosyası (Setup) Derleyici")
    print("=" * 65)

    # 1. Ensure NovaCare.exe is compiled and up to date
    exe_path = os.path.join(ROOT_DIR, "NovaCare.exe")
    dist_exe = os.path.join(ROOT_DIR, "dist", "NovaCare.exe")
    if not os.path.exists(exe_path) and not os.path.exists(dist_exe):
        print("[*] NovaCare.exe bulunamadı, önce ana uygulama derleniyor...")
        from scripts.build_exe import build_executable
        build_executable(onefile=True)

    chosen_exe = exe_path if os.path.exists(exe_path) else dist_exe

    # 2. Setup paths
    ico_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
    assets_dir = os.path.join(ROOT_DIR, "assets")
    v_path = os.path.join(ROOT_DIR, "VERSION")
    manifest_path = os.path.join(ROOT_DIR, "app.manifest")
    wizard_py = os.path.join(ROOT_DIR, "scripts", "installer_wizard.py")

    from core.config import load_base_version
    version = load_base_version()

    setup_name = f"NovaCare_Setup_v{version}"
    temp_build = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "NovaCare_Setup_Build")
    os.makedirs(temp_build, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name={setup_name}",
        "--windowed",
        "--onefile",
        "--noconfirm",
        "--clean",
        f"--manifest={manifest_path}",
        f"--icon={ico_path}",
        f"--add-data={chosen_exe};.",
        f"--add-data={assets_dir};assets",
        f"--add-data={v_path};.",
        f"--add-data={manifest_path};.",
        f"--add-data={os.path.join(ROOT_DIR, 'CHANGELOG.md')};.",
        f"--workpath={temp_build}",
        f"--specpath={temp_build}",
        wizard_py
    ]

    print(f"\n[*] Kurulum Sihirbazı Paketleniyor: {setup_name}.exe")
    print("[*] Gömülen Çekirdek: NovaCare.exe (~41 MB)")
    print("[*] Lütfen bekleyin...\n")

    try:
        subprocess.run(cmd, cwd=ROOT_DIR, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[X] Kurulum dosyası derlenirken hata oluştu: {e}")
        return False

    dist_setup = os.path.join(ROOT_DIR, "dist", f"{setup_name}.exe")
    root_setup = os.path.join(ROOT_DIR, "NovaCare_Setup.exe")

    if os.path.exists(dist_setup):
        # Copy to root as friendly NovaCare_Setup.exe with lock retry
        copied = False
        for attempt in range(5):
            try:
                shutil.copy2(dist_setup, root_setup)
                copied = True
                break
            except PermissionError:
                subprocess.run([get_system32_path("taskkill"), "/f", "/im", "NovaCare_Setup.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                import time
                time.sleep(1.2)
        if not copied:
            print(f"[!] Uyarı: {root_setup} kullanımda olduğu için güncellenemedi, ancak {dist_setup} hazır.")

        size_mb = os.path.getsize(dist_setup) / (1024 * 1024)

        print("\n" + "=" * 65)
        print("  [✔] TEBRİKLER! Güncel Kurulum Dosyası (Setup) Başarıyla Oluşturuldu:")
        print(f"  Konum 1: {root_setup}")
        print(f"  Konum 2: {dist_setup}")
        print(f"  Dosya Boyutu: {size_mb:.1f} MB")
        print("=" * 65)
        print("Bu kurulum dosyasını istediğiniz herhangi bir Windows 10/11")
        print("bilgisayara gönderip çalıştırabilirsiniz.")
        print("Çift tıklandığında modern kurulum sihirbazı açılır, programı")
        print("sisteme kurar, masaüstü/başlat menüsü kısayollarını ekler ve")
        print("Denetim Masası / Program Ekle-Kaldır kaydını otomatik yapar!")
        print("=" * 65)
        return True

    return False

if __name__ == "__main__":
    build_installer()
