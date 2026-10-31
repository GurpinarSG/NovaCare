"""
NovaCare System Care Suite 2026 - Main Entry Point
High-DPI enabled desktop optimization application inspired by CCleaner,
Glary Utilities, and Advanced SystemCare.
"""
import sys
import os
import ctypes
import argparse

# Strip PyInstaller onefile parent tracking variables to prevent
# "Security validation failure: invalid originating onefile parent process (PID not found)!"
for _pyi_var in ('_PYI_PARENT_PID', '_MEIPASS2', '_PYI_APPLICATION_HOME_DIR', '_PYI_ARCHIVE_FILE', '_PYI_SPLASH_IPC'):
    os.environ.pop(_pyi_var, None)

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

import time
import traceback

LOG_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'NovaCare')
os.makedirs(LOG_DIR, exist_ok=True)
STARTUP_LOG = os.path.join(LOG_DIR, 'startup.log')

def log_debug(msg: str):
    try:
        with open(STARTUP_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def global_excepthook(exctype, value, tb):
    err = "".join(traceback.format_exception(exctype, value, tb))
    log_debug("FATAL UNHANDLED EXCEPTION:\n" + err)
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = global_excepthook

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
from PyQt5.QtNetwork import QLocalSocket, QLocalServer
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from core.utils import format_bytes, ensure_ssl_ca_bundle
from core.memory_booster import MemoryBooster
from core.junk_cleaner import JunkCleaner

# Ensure reliable SSL/TLS root certificates across frozen executables and cleanup cycles
ensure_ssl_ca_bundle()

LOCAL_SERVER_NAME = "NovaCare_SingleInstance_App_Server_2026"

def force_activate_window(window):
    """Brings the application window to the foreground even from tray or minimized state."""
    try:
        log_debug("force_activate_window called")
        window.setWindowState((window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        window.show()
        window.showNormal()
        window.raise_()
        window.activateWindow()

        if sys.platform == 'win32':
            hwnd = int(window.winId())
            # SW_RESTORE = 9, SW_SHOW = 5
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        log_debug(f"force_activate_window error: {e}")

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
    from core.config import ConfigManager
    config = ConfigManager()
    repo = config.get("github_repo", "GurpinarSG/NovaCare")
    print("=" * 50)
    print("NovaCare Güncelleştirme Denetimi")
    print("=" * 50)
    print(f"Yüklü Sürüm: {config.get_display_version()}")
    print("Güncelleştirme sunucuları denetleniyor...")
    updater = GitHubUpdater(repo)
    try:
        info = updater.check_for_updates()
        if info.available:
            print(f"🟡 YENİ SÜRÜM MEVCUT: {info.latest_version}")
            print(f"Başlık: {info.release_title}")
            print(f"Yayın Tarihi: {info.published_at}")
            print("\nYenilikler:")
            print(info.changelog)
        else:
            print(f"🟢 Uygulamanız güncel! En son sürümü kullanıyorsunuz ({config.get_display_version()}).")
    except Exception as e:
        print(f"⚠️ Güncelleme denetlenemedi: {e}")

def perform_self_uninstall(silent: bool = False):
    """Uninstalls NovaCare Suite completely from the system."""
    import subprocess
    import winreg
    from PyQt5.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    if not silent:
        box = QMessageBox()
        box.setWindowTitle("NovaCare Kaldırma Sihirbazı")
        box.setText("<h3>NovaCare Uygulamasını Kaldır</h3>NovaCare System Care Suite 2026 uygulamasını ve tüm bileşenlerini bilgisayarınızdan kaldırmak istediğinizden emin misiniz?")
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setStyleSheet("""
            QMessageBox {
                background-color: #0A0F1D;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 18px;
                color: #F8FAFC;
                font-size: 12px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        btn_yes = box.button(QMessageBox.Yes)
        if btn_yes:
            btn_yes.setText("Evet, Kaldır")
        btn_no = box.button(QMessageBox.No)
        if btn_no:
            btn_no.setText("Vazgeç")

        if box.exec_() != QMessageBox.Yes:
            sys.exit(0)

    # 1. Terminate other running NovaCare processes
    my_pid = os.getpid()
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    from core.utils import get_system32_path
    try:
        subprocess.run(
            [get_system32_path("taskkill"), "/f", "/fi", f"PID ne {my_pid}", "/im", "NovaCare.exe"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, timeout=5
        )
    except Exception:
        pass

    # 2. Remove Task Scheduler and Registry Run entries
    try:
        subprocess.run(
            [get_system32_path("schtasks"), "/delete", "/tn", "NovaCare_Autostart", "/f"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, timeout=5
        )
    except Exception:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, "NovaCare")
    except Exception:
        pass

    # 3. Remove Control Panel Add/Remove Programs registry entry
    for root_hkey in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for access in (0, getattr(winreg, 'KEY_WOW64_64KEY', 0), getattr(winreg, 'KEY_WOW64_32KEY', 0)):
            try:
                if hasattr(winreg, 'DeleteKeyEx') and access:
                    winreg.DeleteKeyEx(root_hkey, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare", access)
                else:
                    winreg.DeleteKey(root_hkey, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare")
            except Exception:
                pass

    # 4. Remove shortcuts from Desktop and Start Menu
    ps_remove_shortcuts = """
    $desktop = [Environment]::GetFolderPath('Desktop')
    $programs = [Environment]::GetFolderPath('Programs')
    Remove-Item -Path (Join-Path $desktop 'NovaCare.lnk') -Force -ErrorAction SilentlyContinue
    Remove-Item -Path (Join-Path $programs 'NovaCare') -Recurse -Force -ErrorAction SilentlyContinue
    """
    try:
        import base64
        encoded_ps = base64.b64encode(ps_remove_shortcuts.encode('utf-16le')).decode('ascii')
        subprocess.run(
            [get_system32_path("powershell"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_ps],
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
    except Exception:
        pass

    if not silent:
        info_box = QMessageBox()
        info_box.setWindowTitle("Kaldırma Tamamlandı")
        info_box.setText("<h3>Başarılı</h3>NovaCare sisteminizden tamamen kaldırıldı.")
        info_box.setIcon(QMessageBox.Information)
        info_box.setStyleSheet("""
            QMessageBox { background-color: #0A0F1D; }
            QLabel { color: #FFFFFF; font-size: 13px; font-family: 'Segoe UI', sans-serif; }
            QPushButton { background-color: #1E293B; border: 1px solid #334155; border-radius: 6px; padding: 6px 18px; color: #F8FAFC; }
        """)
        info_box.exec_()

    # 5. Schedule directory deletion right before process exits
    if getattr(sys, 'frozen', False):
        install_dir = os.path.normpath(os.path.abspath(os.path.dirname(sys.executable)))
    else:
        install_dir = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))

    forbidden_roots = {
        os.path.normpath(os.environ.get('SYSTEMROOT', r'C:\Windows')).lower(),
        os.path.normpath(os.environ.get('ProgramFiles', r'C:\Program Files')).lower(),
        os.path.normpath(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')).lower(),
        os.path.normpath(os.environ.get('USERPROFILE', r'C:\Users')).lower(),
        os.path.normpath(os.environ.get('APPDATA', '')).lower(),
        os.path.normpath(os.environ.get('LOCALAPPDATA', '')).lower(),
        os.path.normpath(os.environ.get('ALLUSERSPROFILE', r'C:\ProgramData')).lower(),
        os.path.normpath(os.path.splitdrive(install_dir)[0] + "\\").lower()
    }

    base_name = os.path.basename(install_dir).lower()
    is_safe_novacare_dir = (
        base_name == "novacare"
        and install_dir.lower() not in forbidden_roots
        and os.path.dirname(install_dir) != install_dir
        and len(install_dir.split(os.sep)) >= 3
    )

    if is_safe_novacare_dir:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0x00000008)
        from core.utils import get_system32_path
        cmd_bin = get_system32_path("cmd.exe")
        local_cfg = os.path.normpath(os.path.abspath(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'NovaCare')))
        del_cmd = f'ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{install_dir}"'
        if (
            os.path.exists(local_cfg)
            and local_cfg.lower() != install_dir.lower()
            and os.path.basename(local_cfg).lower() == "novacare"
            and local_cfg.lower() not in forbidden_roots
        ):
            del_cmd += f' & rmdir /s /q "{local_cfg}"'
        try:
            subprocess.Popen([cmd_bin, "/c", del_cmd], shell=False, creationflags=flags)
        except Exception:
            pass

    sys.exit(0)

from core.autostart import ensure_default_autostart

def main():
    parser = argparse.ArgumentParser(description="NovaCare System Care Suite 2026")
    parser.add_argument("--boost-ram", action="store_true", help="Hızlı RAM temizliği yapar ve çıkar")
    parser.add_argument("--quick-scan", action="store_true", help="Sistem çöp dosyalarını tarar ve raporlar")
    parser.add_argument("--check-update", action="store_true", help="GitHub üzerinden güncellemeleri denetler")
    parser.add_argument("--autostart", action="store_true", help="Windows açılışında arka planda sessiz başlatır")
    parser.add_argument("--uninstall", action="store_true", help="NovaCare uygulamasını sistemden kaldırır")
    parser.add_argument("--silent", action="store_true", help="Kaldırma veya işlemi sessiz modda çalıştırır")
    args, _ = parser.parse_known_args()

    if args.uninstall:
        perform_self_uninstall(silent=args.silent)
        return

    if args.boost_ram:
        cli_boost_ram()
        return

    if args.quick_scan:
        cli_quick_scan()
        return

    if args.check_update:
        cli_check_update()
        return

    # Request administrator elevation for interactive GUI mode if needed
    if not args.autostart:
        from core.utils import elevate_if_needed
        elevate_if_needed()

    # Enable autostart by default on user system if configured
    try:
        from core.config import ConfigManager
        if ConfigManager().get("autostart_on_boot", True):
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

    from core.config import CURRENT_VERSION
    app = QApplication(sys.argv)
    app.setApplicationName("NovaCare System Care")
    app.setApplicationVersion(CURRENT_VERSION)
    app.setOrganizationName("NovaCare")

    # Enforce single instance: prevent duplicate processes
    log_debug(f"Starting NovaCare main() with argv: {sys.argv}")
    client_socket = QLocalSocket()
    client_socket.connectToServer(LOCAL_SERVER_NAME)
    if client_socket.waitForConnected(400):
        log_debug("Existing instance detected. Sending ACTIVATE_WINDOW...")
        if not args.autostart:
            client_socket.write(b"ACTIVATE_WINDOW\n")
            client_socket.waitForBytesWritten(1000)
            client_socket.flush()
        client_socket.disconnectFromServer()
        log_debug("Exiting duplicate instance.")
        sys.exit(0)

    # First instance: start local IPC server to listen for duplicate launch activations
    log_debug("Starting primary instance and IPC server...")
    server = QLocalServer()
    server.removeServer(LOCAL_SERVER_NAME)
    server.listen(LOCAL_SERVER_NAME)
    app._single_instance_server = server  # Keep alive

    log_debug("Creating MainWindow...")
    window = MainWindow()
    log_debug("MainWindow created.")

    def handle_incoming_activation():
        conn = server.nextPendingConnection()
        if not conn:
            return
        conn.setParent(server)

        def on_data_received():
            try:
                data = bytes(conn.readAll()).strip()
                log_debug(f"IPC Server received: {data}")
                if b"ACTIVATE_WINDOW" in data:
                    force_activate_window(window)
            except Exception as e:
                log_debug(f"IPC Error: {e}")

        conn.readyRead.connect(on_data_received)
        conn.disconnected.connect(conn.deleteLater)
        if conn.bytesAvailable() > 0:
            on_data_received()

    server.newConnection.connect(handle_incoming_activation)

    if args.autostart:
        # Started automatically on Windows boot: run quietly in System Tray
        log_debug("Running in autostart tray mode.")
        window.hide()
        if hasattr(window, 'tray_icon'):
            window.tray_icon.showMessage(
                "NovaCare",
                "NovaCare arka planda çalışıyor ve sistemi koruyor.",
                QSystemTrayIcon.Information,
                3000
            )
    else:
        log_debug("Showing MainWindow...")
        window.show()

    log_debug("Entering Qt app.exec_()...")
    exit_code = app.exec_()
    log_debug(f"app.exec_() returned with exit code: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
