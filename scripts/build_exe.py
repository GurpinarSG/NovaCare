"""
NovaCare - Standalone Windows Executable Builder (PyInstaller)
Compiles NovaCare into an autonomous .exe that runs on any Windows machine
without requiring Python, external libraries, or any third-party tools.
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

def build_executable(onefile: bool = True):
    print("=" * 60)
    print("  NovaCare System Care Suite 2026 - Windows EXE Derleyici")
    print("=" * 60)
    print(f"[*] Proje Dizini: {ROOT_DIR}")
    print(f"[*] Derleme Modu: {'Tek Bağımsız Dosya (--onefile)' if onefile else 'Taşınabilir Klasör (--onedir)'}")

    ico_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
    assets_dir = os.path.join(ROOT_DIR, "assets")
    v_path = os.path.join(ROOT_DIR, "VERSION")
    main_py = os.path.join(ROOT_DIR, "main.py")

    temp_build = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "NovaCare_Build")
    os.makedirs(temp_build, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=NovaCare",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={ico_path}",
        f"--add-data={assets_dir};assets",
        f"--add-data={v_path};.",
        f"--workpath={temp_build}",
        f"--specpath={temp_build}",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd.append(main_py)

    print("\n[*] PyInstaller çalıştırılıyor, lütfen bekleyin...")
    try:
        subprocess.run(cmd, cwd=ROOT_DIR, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[X] Derleme sırasında hata oluştu: {e}")
        return False

    dist_dir = os.path.join(ROOT_DIR, "dist")
    if onefile:
        target_exe = os.path.join(dist_dir, "NovaCare.exe")
        if os.path.exists(target_exe):
            size_mb = os.path.getsize(target_exe) / (1024 * 1024)
            print("\n" + "=" * 60)
            print(f"  [✔] Derleme Başarılı! Tek Dosya EXE Hazır:")
            print(f"  Konum: {target_exe}")
            print(f"  Boyut: {size_mb:.1f} MB")
            print("=" * 60)
            print("Bu 'NovaCare.exe' dosyasını herhangi bir Windows bilgisayara")
            print("gönderip doğrudan çift tıklayarak çalıştırabilirsiniz.")
            print("Karşı tarafta Python veya ek hiçbir yazılım gerekmez!")
            return True
    else:
        target_folder = os.path.join(dist_dir, "NovaCare")
        if os.path.exists(target_folder):
            print("\n" + "=" * 60)
            print(f"  [✔] Derleme Başarılı! Taşınabilir Klasör Hazır:")
            print(f"  Konum: {target_folder}")
            print("=" * 60)
            return True

    return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaCare EXE Builder")
    parser.add_argument("--onedir", action="store_true", help="Tek dosya yerine hızlı taşınabilir klasör olarak derle")
    args = parser.parse_args()

    build_executable(onefile=not args.onedir)
