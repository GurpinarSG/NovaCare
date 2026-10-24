"""
NovaCare System Suite 2026 - Windows Native Installer & Setup Wizard
Delivers an elegant, modern setup experience inspired by Inno Setup and NSIS.
Features:
- Beautiful PyQt5 high-DPI modern wizard UI with visual sidebar banner
- Full visual artwork with high-resolution brand logo and step indicator
- Destination folder selection with disk space check
- Desktop and Start Menu shortcut creation
- Windows Add/Remove Programs (Registry) registration
- Clean uninstaller script generation & integrated CLI uninstaller
- 100% standalone single-file distribution
"""
import os
import sys
import shutil
import winreg
import subprocess
import time
import json

from PyQt5.QtWidgets import (
    QApplication, QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QCheckBox, QProgressBar, QFileDialog, QFrame,
    QStackedWidget, QMessageBox, QDialogButtonBox, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QPainter

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_app_version():
    try:
        from core.config import load_base_version
        return load_base_version()
    except Exception:
        pass
    try:
        base = get_base_dir()
        v_file = os.path.join(base, "VERSION")
        if os.path.exists(v_file):
            with open(v_file, "r", encoding="utf-8") as f:
                return f.readline().strip().lstrip("vV")
    except Exception:
        pass
    return "1.2.1"

# Version & Product Info
APP_NAME = "NovaCare"
APP_DISPLAY_NAME = "NovaCare System Care Suite 2026"
APP_VERSION = _load_app_version()
APP_PUBLISHER = "Gurpinar Software Group"
APP_DESCRIPTION = "Gelişmiş Windows Sistem Bakım, Hızlandırma ve Optimizasyon Paketi"

def get_default_install_dir():
    local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    return os.path.join(local_app, 'Programs', 'NovaCare')

def get_disk_free_gb(path):
    try:
        drive = os.path.splitdrive(path)[0] or 'C:'
        total, used, free = shutil.disk_usage(drive)
        return round(free / (1024 ** 3), 1)
    except Exception:
        return 50.0

# ==============================================================================
# Worker Thread for Installation
# ==============================================================================

class InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, target_dir: str, create_desktop_lnk: bool, create_start_lnk: bool, autostart: bool, autostart_widget: bool = False):
        super().__init__()
        self.target_dir = target_dir
        self.create_desktop_lnk = create_desktop_lnk
        self.create_start_lnk = create_start_lnk
        self.autostart = autostart
        self.autostart_widget = autostart_widget

    def run(self):
        try:
            base_dir = get_base_dir()
            self.progress.emit(10, "Hedef dizin hazırlanıyor...")
            os.makedirs(self.target_dir, exist_ok=True)
            time.sleep(0.3)

            # 1. Close running instances if any
            try:
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
                subprocess.run(
                    ["taskkill", "/f", "/im", "NovaCare.exe"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=flags, timeout=5
                )
                time.sleep(0.5)
            except Exception:
                pass

            # 2. Copy NovaCare.exe
            self.progress.emit(25, "Uygulama çekirdek dosyaları kopyalanıyor...")
            src_exe = os.path.join(base_dir, "NovaCare.exe")
            if not os.path.exists(src_exe):
                src_exe = os.path.join(base_dir, "dist", "NovaCare.exe")
            dest_exe = os.path.join(self.target_dir, "NovaCare.exe")
            if os.path.exists(src_exe):
                shutil.copy2(src_exe, dest_exe)

            # 3. Copy Assets
            self.progress.emit(45, "Grafik ve görsel bileşenler aktarılıyor...")
            src_assets = os.path.join(base_dir, "assets")
            dest_assets = os.path.join(self.target_dir, "assets")
            if os.path.exists(src_assets):
                if os.path.exists(dest_assets):
                    shutil.rmtree(dest_assets, ignore_errors=True)
                shutil.copytree(src_assets, dest_assets)

            # 4. Copy VERSION, manifest and CHANGELOG
            self.progress.emit(60, "Sistem ve yapılandırma dosyaları yerleştiriliyor...")
            for fname in ["VERSION", "app.manifest", "CHANGELOG.md"]:
                src_f = os.path.join(base_dir, fname)
                if os.path.exists(src_f):
                    shutil.copy2(src_f, os.path.join(self.target_dir, fname))

            # 5. Generate Uninstaller
            self.progress.emit(75, "Program kaldırıcı (Uninstaller) oluşturuluyor...")
            self._generate_uninstaller()

            # 6. Create Shortcuts
            self.progress.emit(85, "Kısayollar yapılandırılıyor...")
            self._create_shortcuts(dest_exe)

            # 7. Windows Registry Add/Remove Programs
            self.progress.emit(95, "Windows Denetim Masası kayıtları tamamlanıyor...")
            self._register_uninstaller(dest_exe)

            # 8. Autostart and Desktop Widget preference
            if self.autostart:
                self._register_autostart(dest_exe)

            # 9. Save user initial preferences
            self._save_initial_preferences()

            time.sleep(0.4)
            self.progress.emit(100, "Kurulum tamamlandı!")
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _save_initial_preferences(self):
        try:
            local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            cfg_dir = os.path.join(local_app, 'NovaCare')
            os.makedirs(cfg_dir, exist_ok=True)
            cfg_file = os.path.join(cfg_dir, 'settings.json')
            data = {}
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data["autostart_on_boot"] = bool(self.autostart)
            data["autostart_widget_on_boot"] = bool(self.autostart_widget)
            data["widget_autostart_prompted"] = True
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _generate_uninstaller(self):
        uninst_bat = os.path.join(self.target_dir, "uninstall.bat")
        content = r'''@echo off
chcp 65001 > nul
title NovaCare Kaldırma Sihirbazı
echo ====================================================================
echo   NovaCare System Care Suite 2026 - Kaldırma Sihirbazı
echo ====================================================================
echo.
echo NovaCare uygulaması bilgisayarınızdan kaldırılıyor, lütfen bekleyin...
echo.

taskkill /f /im NovaCare.exe > nul 2>&1
schtasks /delete /tn "NovaCare_Autostart" /f > nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "NovaCare" /f > nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare" /f > nul 2>&1
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare" /f > nul 2>&1

powershell -NoProfile -ExecutionPolicy Bypass -Command "Remove-Item -Path '$([Environment]::GetFolderPath(''Desktop''))\NovaCare.lnk' -Force -ErrorAction SilentlyContinue; Remove-Item -Path '$([Environment]::GetFolderPath(''Programs''))\NovaCare' -Recurse -Force -ErrorAction SilentlyContinue" > nul 2>&1

set "TARGET_DIR=%~dp0"
if "%TARGET_DIR:~-1%"=="\" set "TARGET_DIR=%TARGET_DIR:~0,-1%"

cd /d "%TEMP%"
start /b "" cmd /c "timeout /t 2 /nobreak > nul & rmdir /s /q \"%TARGET_DIR%\""

echo [OK] NovaCare başarıyla bilgisayarınızdan kaldırıldı!
echo Bu pencere birkaç saniye içinde otomatik olarak kapanacaktır.
timeout /t 3 > nul
exit
'''
        with open(uninst_bat, "w", encoding="utf-8") as f:
            f.write(content)

    def _create_shortcuts(self, dest_exe: str):
        icon_path = os.path.join(self.target_dir, "assets", "icon.ico")
        ps_commands = []

        if self.create_desktop_lnk:
            ps_commands.append(f"""
            $desktop = [Environment]::GetFolderPath('Desktop')
            $s = $wsh.CreateShortcut((Join-Path $desktop 'NovaCare.lnk'))
            $s.TargetPath = '{dest_exe}'
            $s.WorkingDirectory = '{self.target_dir}'
            $s.Arguments = ''
            $s.IconLocation = '{icon_path},0'
            $s.Description = '{APP_DISPLAY_NAME}'
            $s.Save()
            """)

        if self.create_start_lnk:
            ps_commands.append(f"""
            $programs = [Environment]::GetFolderPath('Programs')
            $folder = Join-Path $programs 'NovaCare'
            if (-not (Test-Path $folder)) {{ New-Item -ItemType Directory -Path $folder -Force | Out-Null }}
            $s1 = $wsh.CreateShortcut((Join-Path $folder 'NovaCare.lnk'))
            $s1.TargetPath = '{dest_exe}'
            $s1.WorkingDirectory = '{self.target_dir}'
            $s1.Arguments = ''
            $s1.IconLocation = '{icon_path},0'
            $s1.Description = '{APP_DISPLAY_NAME}'
            $s1.Save()

            $s2 = $wsh.CreateShortcut((Join-Path $folder 'NovaCare Kaldır.lnk'))
            $s2.TargetPath = '{dest_exe}'
            $s2.Arguments = '--uninstall'
            $s2.WorkingDirectory = '{self.target_dir}'
            $s2.IconLocation = 'shell32.dll,31'
            $s2.Description = 'NovaCare Uygulamasını Kaldır'
            $s2.Save()
            """)

        if ps_commands:
            script = "$wsh = New-Object -ComObject WScript.Shell\n" + "\n".join(ps_commands)
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            subprocess.run(["powershell", "-NoProfile", "-Command", script], creationflags=flags)

    def _register_uninstaller(self, dest_exe: str):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\NovaCare"

        # 1. Clean up any existing duplicate entry in HKCU to prevent shadowing
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        except Exception:
            pass

        # 2. Register into HKLM so Windows Control Panel natively prompts UAC elevation (RunAs).
        # When an application requiring Administrator rights is registered in HKLM,
        # Control Panel (appwiz.cpl) displays the UAC shield icon and elevates execution.
        try:
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f"{dest_exe},0")
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, self.target_dir)
                winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{dest_exe}" --uninstall')
                winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{dest_exe}" --uninstall --silent')
                winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 42000)
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        except Exception:
            # Fallback to HKCU if HKLM write fails (e.g. non-admin environment),
            # using an elevated wrapper in UninstallString to prevent Error 740
            try:
                elevated_uninstall = f'powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath \'{dest_exe}\' -ArgumentList \'--uninstall\' -Verb RunAs"'
                elevated_quiet = f'powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath \'{dest_exe}\' -ArgumentList \'--uninstall --silent\' -Verb RunAs"'
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
                    winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
                    winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
                    winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f"{dest_exe},0")
                    winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, self.target_dir)
                    winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, elevated_uninstall)
                    winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, elevated_quiet)
                    winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 42000)
                    winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            except Exception:
                pass

    def _register_autostart(self, dest_exe: str):
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        try:
            ps_script = f"""
            $action = New-ScheduledTaskAction -Execute '{dest_exe}' -Argument '--autostart'
            $trigger = New-ScheduledTaskTrigger -AtLogOn
            $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)
            Register-ScheduledTask -TaskName 'NovaCare_Autostart' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], creationflags=flags, timeout=8)
        except Exception:
            try:
                cmd_str = f'"{dest_exe}" --autostart'
                subprocess.run(
                    ["schtasks", "/create", "/tn", "NovaCare_Autostart", "/tr", cmd_str, "/sc", "onlogon", "/rl", "highest", "/f"],
                    creationflags=flags,
                    timeout=5
                )
            except Exception:
                pass

        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "NovaCare", 0, winreg.REG_SZ, f'"{dest_exe}" --autostart')
        except Exception:
            pass

# ==============================================================================
# Modern Setup Wizard UI with Visual Sidebar Banner
# ==============================================================================

qss = """
    QDialog, QWidget {
        background-color: #0A0F1D;
        color: #F8FAFC;
        font-family: 'Segoe UI', 'Segoe UI Emoji', sans-serif;
    }
    QFrame#SidebarBanner {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #060D1A, stop:0.5 #0B1528, stop:1 #0F1E36);
        border-right: 1px solid #1E293B;
    }
    QFrame#SetupCard {
        background-color: #0E1626;
        border: 1px solid #1E293B;
        border-radius: 8px;
    }
    QFrame#SetupCard QLabel {
        background: transparent;
        border: none;
        color: #CBD5E1;
        font-size: 13px;
    }
    QLabel {
        background: transparent;
        border: none;
        color: #E2E8F0;
        font-size: 13px;
    }
    QLabel#PageTitle {
        font-size: 20px;
        font-weight: 800;
        color: #00D2FF;
    }
    QLabel#PageSubtitle {
        font-size: 13px;
        color: #94A3B8;
    }
    QLineEdit {
        background-color: #111827;
        border: 1px solid #1E293B;
        border-radius: 6px;
        padding: 8px 12px;
        color: #FFFFFF;
        font-size: 13px;
    }
    QLineEdit:focus {
        border: 1px solid #00D2FF;
    }
    QPushButton {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 7px 20px;
        color: #F8FAFC;
        font-weight: 600;
        font-size: 12px;
        min-width: 75px;
    }
    QPushButton:hover {
        background-color: #334155;
        border-color: #475569;
    }
    QPushButton:pressed {
        background-color: #0F172A;
    }
    QPushButton#PrimaryBtn {
        background-color: #00D2FF;
        border: 1px solid #00D2FF;
        color: #050B14;
        font-weight: 700;
    }
    QPushButton#PrimaryBtn:hover {
        background-color: #38BDF8;
        border-color: #38BDF8;
    }
    QCheckBox {
        font-size: 13px;
        color: #F1F5F9;
        spacing: 10px;
        background: transparent;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid #334155;
        background-color: #111827;
    }
    QCheckBox::indicator:hover {
        border-color: #00D2FF;
    }
    QCheckBox::indicator:checked {
        background-color: #00D2FF;
        border-color: #00D2FF;
    }
    QProgressBar {
        background-color: #111827;
        border: 1px solid #1E293B;
        border-radius: 6px;
        text-align: center;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 12px;
        height: 24px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00D2FF, stop:1 #10B981);
        border-radius: 5px;
    }
"""

class NovaCareSetupWizard(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NovaCare System Care Suite 2026 - Kurulum Sihirbazı")
        self.setFixedSize(760, 530)
        self.setStyleSheet(qss)

        base_dir = get_base_dir()
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.worker = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Left Sidebar Banner
        self.sidebar = QFrame()
        self.sidebar.setObjectName("SidebarBanner")
        self.sidebar.setFixedWidth(225)
        s_lay = QVBoxLayout(self.sidebar)
        s_lay.setContentsMargins(20, 26, 20, 20)
        s_lay.setSpacing(14)

        logo_lbl = QLabel()
        png_path = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(png_path):
            pix = QPixmap(png_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        logo_lbl.setAlignment(Qt.AlignCenter)
        s_lay.addWidget(logo_lbl)

        b_title = QLabel("NovaCare")
        b_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #FFFFFF;")
        b_title.setAlignment(Qt.AlignCenter)
        s_lay.addWidget(b_title)

        b_sub = QLabel("SYSTEM CARE 2026")
        b_sub.setStyleSheet("font-size: 10px; font-weight: 700; color: #00D2FF; letter-spacing: 1px;")
        b_sub.setAlignment(Qt.AlignCenter)
        s_lay.addWidget(b_sub)

        pill = QLabel("v1.0.1 Kararlı")
        pill.setStyleSheet("""
            background-color: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10B981;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 10px;
        """)
        pill.setAlignment(Qt.AlignCenter)
        s_lay.addWidget(pill)

        s_lay.addSpacing(14)

        self.step_labels = []
        steps = [
            ("1. Hoş Geldiniz", 0),
            ("2. Kurulum Konumu", 1),
            ("3. Ek Tercihler", 2),
            ("4. Dosya Yükleme", 3),
            ("5. Tamamlandı", 4)
        ]
        for name, idx in steps:
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600; padding: 4px 8px;")
            s_lay.addWidget(lbl)
            self.step_labels.append(lbl)

        s_lay.addStretch()

        pub = QLabel("Gurpinar Software Group")
        pub.setStyleSheet("color: #475569; font-size: 10px;")
        pub.setAlignment(Qt.AlignCenter)
        s_lay.addWidget(pub)

        root.addWidget(self.sidebar)

        # 2. Right Main Content Area
        right_panel = QWidget()
        r_lay = QVBoxLayout(right_panel)
        r_lay.setContentsMargins(28, 24, 28, 20)
        r_lay.setSpacing(14)

        self.stack = QStackedWidget()
        r_lay.addWidget(self.stack, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #1E293B; height: 1px; border: none;")
        r_lay.addWidget(sep)

        btn_row = QHBoxLayout()
        self.btn_back = QPushButton("< Geri")
        self.btn_next = QPushButton("İleri >")
        self.btn_next.setObjectName("PrimaryBtn")
        self.btn_cancel = QPushButton("İptal")

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_back)
        btn_row.addWidget(self.btn_next)
        btn_row.addWidget(self.btn_cancel)
        r_lay.addLayout(btn_row)

        root.addWidget(right_panel, 1)

        self._build_all_pages()
        self._update_ui_state()

    def _update_ui_state(self):
        cur = self.stack.currentIndex()
        for idx, lbl in enumerate(self.step_labels):
            if idx == cur:
                lbl.setStyleSheet("font-size: 12px; color: #00D2FF; font-weight: 700; background: rgba(0, 210, 255, 0.1); border-radius: 4px; padding: 4px 8px;")
            elif idx < cur:
                lbl.setStyleSheet("font-size: 12px; color: #10B981; font-weight: 600; padding: 4px 8px;")
            else:
                lbl.setStyleSheet("font-size: 12px; color: #64748B; font-weight: 600; padding: 4px 8px;")

        self.btn_back.setEnabled(cur > 0 and cur != 3 and cur != 4)
        if cur == 3: # Installing
            self.btn_next.setEnabled(False)
            self.btn_cancel.setEnabled(False)
        elif cur == 4: # Finished
            self.btn_next.setText("Bitir")
            self.btn_next.setEnabled(True)
            self.btn_cancel.setVisible(False)
        else:
            self.btn_next.setText("İleri >")
            self.btn_next.setEnabled(True)
            self.btn_cancel.setVisible(True)

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 4: # Finish
            self._on_finish()
            return
        elif cur == 2: # Start Install
            self.stack.setCurrentIndex(3)
            self._update_ui_state()
            self._start_installation()
            return
        self.stack.setCurrentIndex(cur + 1)
        self._update_ui_state()

    def _go_back(self):
        cur = self.stack.currentIndex()
        if cur > 0 and cur != 3:
            self.stack.setCurrentIndex(cur - 1)
            self._update_ui_state()

    def _start_installation(self):
        target_dir = self.line_dir.text()
        desktop = self.chk_desktop.isChecked()
        start = self.chk_startmenu.isChecked()
        autostart = self.chk_autostart.isChecked()
        autostart_widget = self.chk_autostart_widget.isChecked()

        self.worker = InstallWorker(target_dir, desktop, start, autostart, autostart_widget)
        self.worker.progress.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_progress(self, val: int, msg: str):
        self.pbar.setValue(val)
        self.lbl_detail.setText(msg)

    def _on_install_finished(self, success: bool, err: str):
        if success:
            self.stack.setCurrentIndex(4)
            self._update_ui_state()
        else:
            QMessageBox.critical(self, "Kurulum Hatası", f"Kurulum sırasında bir hata oluştu:\n\n{err}")
            self.btn_cancel.setEnabled(True)

    def _on_finish(self):
        target_dir = self.line_dir.text()
        if self.chk_view_notes.isChecked():
            cl_path = os.path.join(target_dir, "CHANGELOG.md")
            if os.path.exists(cl_path):
                try:
                    os.startfile(cl_path)
                except Exception:
                    pass
        if self.chk_launch.isChecked():
            target_exe = os.path.join(target_dir, "NovaCare.exe")
            if os.path.exists(target_exe):
                flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                subprocess.Popen([target_exe], creationflags=flags)
        self.accept()

    def _show_changelog_dialog(self):
        d = QDialog(self)
        d.setWindowTitle("NovaCare - Sürüm Güncelleme Notları")
        d.resize(640, 460)
        d.setStyleSheet("""
            QDialog { background-color: #0A0F1D; }
            QTextBrowser {
                background-color: #111827;
                border: 1px solid #1E293B;
                border-radius: 8px;
                color: #CBD5E1;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 20px;
                color: #F8FAFC;
                font-size: 12px;
            }
        """)
        lay = QVBoxLayout(d)
        lbl = QLabel("📜  NovaCare Sürüm Güncelleme Notları")
        lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #00D2FF;")
        lay.addWidget(lbl)

        txt = QTextBrowser()
        base_dir = get_base_dir()
        cl_path = os.path.join(base_dir, "CHANGELOG.md")
        content = ""
        if os.path.exists(cl_path):
            try:
                with open(cl_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                pass
        if not content:
            content = (
                "# 📋 NovaCare Sürüm Güncelleme Notları\n\n"
                "## 🚀 [v1.0.1] - 2026-10-16 (Güncel Sürüm)\n"
                "• Pencere Boyutu & Düzen: Ekrana duyarlı dinamik geometri; 768p ve yüksek DPI ekranlarda tam uyum.\n"
                "• Metin Kaydırma: Tüm sekmelerde alt başlıklara kelime kaydırma (word-wrap) eklendi; taşmalar önlendi.\n"
                "• Denetim Masası Kaldırma: Yerel uninstaller motoru (--uninstall) entegre edildi; sorunsuz kaldırma.\n"
                "• Kurulum Sihirbazı: Koyu tema, düzeltilen yazı ve kontrast sorunları, görsel yan panel ve modern tasarım.\n"
                "• Yönetici Ayrıcalığı: Ayarlar ekranında yönetici olarak başlatma seçeneği ve derin temizlik vurgusu.\n"
                "• Güvenlik: GitHub API belirteçleri Windows DPAPI ile şifrelendi.\n"
                "• Performans: Çoklu iş parçacığı ve bellek yönetimi iyileştirmeleri.\n\n"
                "## 📦 [v1.0.0] - 2026-10-15\n"
                "• İlk kararlı sürüm yayınlandı."
            )
        txt.setPlainText(content)
        lay.addWidget(txt)

        btn_b = QDialogButtonBox(QDialogButtonBox.Close)
        btn_c = btn_b.button(QDialogButtonBox.Close)
        if btn_c:
            btn_c.setText("Kapat")
        btn_b.rejected.connect(d.reject)
        lay.addWidget(btn_b)
        d.exec_()

    def _build_all_pages(self):
        # Page 0: Welcome
        p0 = QWidget()
        l0 = QVBoxLayout(p0)
        l0.setContentsMargins(0, 0, 0, 0)
        l0.setSpacing(12)
        t0 = QLabel("Kurulum Sihirbazına Hoş Geldiniz")
        t0.setObjectName("PageTitle")
        sub0 = QLabel("NovaCare System Care Suite 2026 bilgisayarınıza kurulacak.")
        sub0.setObjectName("PageSubtitle")
        l0.addWidget(t0)
        l0.addWidget(sub0)

        card0 = QFrame()
        card0.setObjectName("SetupCard")
        c0_lay = QVBoxLayout(card0)
        c0_lay.setContentsMargins(16, 14, 16, 14)
        c0_lay.setSpacing(10)
        feats = [
            "⚡  <b>Tek Tıkla Sistem Bakımı:</b> Çöp dosyaları ve geçici verileri temizler.",
            "🧠  <b>Akıllı RAM Boşaltıcı:</b> Bellek kullanımını optimize ederek donmaları önler.",
            "🎮  <b>Oyun Modu:</b> Arka plan servislerini kapatıp en yüksek performansı verir.",
            "🌐  <b>Ağ ve DNS Optimize Edici:</b> İnternet bağlantısını ve DNS gecikmesini düşürür.",
            "📊  <b>Donanım Takibi:</b> CPU, GPU ve disk durumunu gerçek zamanlı izler."
        ]
        for f in feats:
            lbl = QLabel(f)
            lbl.setWordWrap(True)
            c0_lay.addWidget(lbl)
        l0.addWidget(card0)

        info_row = QHBoxLayout()
        hint = QLabel("Devam etmek için <b>İleri</b> butonuna tıklayın.")
        hint.setStyleSheet("color: #64748B; font-size: 12px;")
        btn_notes = QPushButton("📜  Güncelleme Notları")
        btn_notes.setStyleSheet("font-size: 11px; padding: 4px 12px;")
        btn_notes.clicked.connect(self._show_changelog_dialog)
        info_row.addWidget(hint)
        info_row.addStretch()
        info_row.addWidget(btn_notes)
        l0.addLayout(info_row)
        l0.addStretch()
        self.stack.addWidget(p0)

        # Page 1: Directory
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setContentsMargins(0, 0, 0, 0)
        l1.setSpacing(14)
        t1 = QLabel("Hedef Klasörü Seçin")
        t1.setObjectName("PageTitle")
        sub1 = QLabel("NovaCare uygulamasının kurulacağı dizini belirleyin.")
        sub1.setObjectName("PageSubtitle")
        l1.addWidget(t1)
        l1.addWidget(sub1)

        desc1 = QLabel("NovaCare aşağıdaki klasöre kurulacak. Farklı bir klasör seçmek isterseniz 'Gözat' butonuna tıklayabilirsiniz:")
        desc1.setWordWrap(True)
        l1.addWidget(desc1)

        row1 = QHBoxLayout()
        self.line_dir = QLineEdit(get_default_install_dir())
        btn_b1 = QPushButton("Gözat...")
        btn_b1.clicked.connect(self._browse)
        row1.addWidget(self.line_dir)
        row1.addWidget(btn_b1)
        l1.addLayout(row1)

        card1 = QFrame()
        card1.setObjectName("SetupCard")
        c1_lay = QHBoxLayout(card1)
        c1_lay.setContentsMargins(16, 12, 16, 12)
        free_gb = get_disk_free_gb(self.line_dir.text())
        self.lbl_space = QLabel(f"💾  Gereken Disk Alanı: ~45.0 MB   |   Kullanılabilir Boş Alan: {free_gb} GB")
        self.lbl_space.setStyleSheet("color: #10B981; font-weight: 600;")
        c1_lay.addWidget(self.lbl_space)
        l1.addWidget(card1)
        l1.addStretch()
        self.stack.addWidget(p1)

        # Page 2: Options
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.setContentsMargins(0, 0, 0, 0)
        l2.setSpacing(14)
        t2 = QLabel("Ek Görevler")
        t2.setObjectName("PageTitle")
        sub2 = QLabel("Kurulum sırasında yapılmasını istediğiniz ek tercihleri seçin.")
        sub2.setObjectName("PageSubtitle")
        l2.addWidget(t2)
        l2.addWidget(sub2)

        card2 = QFrame()
        card2.setObjectName("SetupCard")
        c2_lay = QVBoxLayout(card2)
        c2_lay.setContentsMargins(18, 16, 18, 16)
        c2_lay.setSpacing(14)
        self.chk_desktop = QCheckBox("Masaüstüne NovaCare kısayolu oluştur")
        self.chk_desktop.setChecked(True)
        self.chk_startmenu = QCheckBox("Başlat Menüsü klasörüne NovaCare kısayolu ekle")
        self.chk_startmenu.setChecked(True)
        self.chk_autostart = QCheckBox("Windows açıldığında NovaCare'i arka planda otomatik başlat (Önerilen)")
        self.chk_autostart.setChecked(True)
        self.chk_autostart_widget = QCheckBox("📌  Windows açıldığında Masaüstü Donanım Widget'ını (Monitör) da otomatik başlat")
        self.chk_autostart_widget.setChecked(False)
        self.chk_autostart.stateChanged.connect(lambda s: self.chk_autostart_widget.setEnabled(s == Qt.Checked))

        c2_lay.addWidget(self.chk_desktop)
        c2_lay.addWidget(self.chk_startmenu)
        c2_lay.addWidget(self.chk_autostart)
        c2_lay.addWidget(self.chk_autostart_widget)
        l2.addWidget(card2)
        l2.addStretch()
        self.stack.addWidget(p2)

        # Page 3: Install
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(14)
        t3 = QLabel("Kuruluyor...")
        t3.setObjectName("PageTitle")
        sub3 = QLabel("NovaCare bilgisayarınıza yükleniyor, lütfen bekleyin...")
        sub3.setObjectName("PageSubtitle")
        l3.addWidget(t3)
        l3.addWidget(sub3)

        self.pbar = QProgressBar()
        self.pbar.setValue(0)
        l3.addWidget(self.pbar)
        self.lbl_detail = QLabel("Hazırlanıyor...")
        self.lbl_detail.setStyleSheet("color: #94A3B8; font-size: 12px;")
        l3.addWidget(self.lbl_detail)
        l3.addStretch()
        self.stack.addWidget(p3)

        # Page 4: Finish
        p4 = QWidget()
        l4 = QVBoxLayout(p4)
        l4.setContentsMargins(0, 0, 0, 0)
        l4.setSpacing(14)
        t4 = QLabel("🎉  Kurulum Başarıyla Tamamlandı!")
        t4.setObjectName("PageTitle")
        t4.setStyleSheet("color: #10B981; font-size: 20px; font-weight: 800;")
        sub4 = QLabel("NovaCare System Care Suite 2026 bilgisayarınıza başarıyla kuruldu.")
        sub4.setObjectName("PageSubtitle")
        l4.addWidget(t4)
        l4.addWidget(sub4)

        card4 = QFrame()
        card4.setObjectName("SetupCard")
        c4_lay = QVBoxLayout(card4)
        c4_lay.setContentsMargins(18, 16, 18, 16)
        c4_lay.setSpacing(12)
        info1 = QLabel("✅  Tüm program dosyaları ve kütüphaneler yerleştirildi.")
        info2 = QLabel("✅  Masaüstü ve Başlat Menüsü kısayolları hazırlandı.")
        info3 = QLabel("✅  Windows Denetim Masası / Program Ekle-Kaldır kaydı oluşturuldu.")
        for info in (info1, info2, info3):
            info.setWordWrap(True)
            c4_lay.addWidget(info)
        l4.addWidget(card4)

        self.chk_launch = QCheckBox("NovaCare uygulamasını şimdi başlat")
        self.chk_launch.setChecked(True)
        self.chk_launch.setStyleSheet("font-weight: 700; color: #00D2FF; font-size: 13px; margin-top: 6px;")
        l4.addWidget(self.chk_launch)

        self.chk_view_notes = QCheckBox("Sürüm güncelleme notlarını (Changelog) görüntüle")
        self.chk_view_notes.setChecked(False)
        self.chk_view_notes.setStyleSheet("color: #94A3B8; font-size: 12px; margin-top: 2px;")
        l4.addWidget(self.chk_view_notes)
        l4.addStretch()
        self.stack.addWidget(p4)

    def _browse(self):
        cur = self.line_dir.text()
        chosen = QFileDialog.getExistingDirectory(self, "Kurulum Klasörünü Seçin", cur)
        if chosen:
            target = os.path.join(chosen, "NovaCare") if not chosen.endswith("NovaCare") else chosen
            self.line_dir.setText(target)
            free_gb = get_disk_free_gb(target)
            self.lbl_space.setText(f"💾  Gereken Disk Alanı: ~45.0 MB   |   Kullanılabilir Boş Alan: {free_gb} GB")

def main():
    if sys.platform == 'win32':
        try:
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("NovaCare Setup")
    wizard = NovaCareSetupWizard()
    wizard.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
