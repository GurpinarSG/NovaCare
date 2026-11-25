"""
NovaCare System Suite - 6th-Pass Deep Security, Threading, UI & Logic Audit Verification Suite
Tests all fixes from the comprehensive audit:
1. Uninstaller PowerShell UAC ArgumentList escaping without \" corruption.
2. Updater web-fallback integrity/TLS, require_integrity fail-closed, and batch metacharacter guards.
3. Isolated temp directories/files in BatteryReporter & main.py self-uninstall.
4. BackupManager secret key non-clobbering and non-predictable fallback.
5. Truthful status returns in PrivacyTweaker, StartupManager, GameBooster, RegistryCompactor, NetworkOptimizer.
6. HardwareMonitor NVML lock & cleanup.
7. CookieShield graceful-first close & mid-batch cancel; AutoCleaner invalid target_day guard.
8. DuplicateFinder non-substring protected path matching & JunkCleaner non-username blocking.
9. PyQt5 UI QSS double-brace check, worker isRunning guards, DiskView cancel race, GameProfilesDialog cleanup.
10. Installer wizard & app.manifest version sync.
"""
import ast
import base64
import glob
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def test_01_uninstaller_uac_argument_escaping():
    print("[1/10] Testing AppUninstaller UAC ArgumentList escaping cleanly preserves spaces & quotes...")
    from core.uninstaller import AppUninstaller, InstalledApp

    uninst = AppUninstaller()
    tmp_dir = tempfile.mkdtemp(prefix="NovaCare_UninstTest_")
    try:
        uninst_exe = os.path.join(tmp_dir, "uninstall.exe")
        with open(uninst_exe, "w", encoding="utf-8") as f:
            f.write("stub")

        app_mock = InstalledApp(
            id="test_app",
            name="TestApp",
            version="1.0",
            publisher="Tester",
            install_date="",
            size_bytes=100,
            uninstall_string='uninstall.exe /S "/D=C:\\Program Files\\My App"',
            quiet_uninstall_string="",
            install_location=tmp_dir,
            icon_path="",
            registry_path="",
            root_name=""
        )

        with patch("subprocess.Popen") as mock_popen:
            err = OSError("elevation required")
            err.winerror = 740
            mock_proc = MagicMock()
            mock_popen.side_effect = [err, mock_proc]

            res = uninst.launch_uninstaller(app_mock)
            assert res is mock_proc
            ps_tokens = mock_popen.call_args[0][0]
            b64 = ps_tokens[ps_tokens.index("-EncodedCommand") + 1]
            decoded_ps = base64.b64decode(b64).decode("utf-16le")

            assert r'\"' not in decoded_ps, f"Corrupt \\\" escape found in PowerShell script: {decoded_ps}"
            assert '"/D=C:\\Program Files\\My App"' in decoded_ps

        # Live roundtrip with real PowerShell Start-Process (non-elevated) verifying CommandLineToArgvW
        out_json = os.path.join(tmp_dir, "argv.json")
        child_code = f'import sys, json; open({out_json!r}, "w").write(json.dumps(sys.argv[1:]))'
        args = ["-c", child_code, "/S", r"/D=C:\Program Files\My App", 'KEY="Val Space"']
        ps_cmd = subprocess.list2cmdline(args).replace("'", "''")
        ps_exe = sys.executable.replace("'", "''")
        ps_script = f"Start-Process -FilePath '{ps_exe}' -ArgumentList '{ps_cmd}' -Wait -NoNewWindow"
        enc = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc],
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with open(out_json, "r", encoding="utf-8") as f:
            got = json.load(f)
        assert got == ["/S", r"/D=C:\Program Files\My App", 'KEY="Val Space"'], f"Unexpected argv: {got}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("  [PASS] UAC PowerShell ArgumentList roundtrip verified.")


def test_02_updater_integrity_and_batch_guards():
    print("[2/10] Testing GitHubUpdater web fallback integrity, require_integrity & batch guards...")
    from core.updater import GitHubUpdater

    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.3.0")

    # 1. Web redirect fallback passes TLS verify=self._get_verify() and attaches sha256sums_url
    rate_limit_resp = MagicMock(status_code=403, text="API rate limit exceeded")
    redirect_resp = MagicMock(status_code=302, headers={"Location": "https://github.com/GurpinarSG/NovaCare/releases/tag/v1.3.2"})
    with patch.object(updater, "_safe_request_get", return_value=rate_limit_resp), \
         patch("core.updater.requests.get", return_value=redirect_resp) as mock_req_get:
        info = updater._check_releases(allow_fallback=False)
        assert info.available is True
        assert info.sha256sums_url.endswith("/v1.3.2/SHA256SUMS.txt")
        mock_req_get.assert_called_once()
        assert mock_req_get.call_args[1].get("allow_redirects") is False
        assert "verify" in mock_req_get.call_args[1]

    # 2. require_integrity=True fails closed when hashes are missing & batch metacharacters are rejected
    tmp_dir = tempfile.mkdtemp(prefix="NovaCare_UpdAudit6_")
    try:
        zip_path = os.path.join(tmp_dir, "pkg.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("VERSION", "1.3.2\n")
        with open(zip_path, "rb") as f:
            zdata = f.read()

        mock_dl = MagicMock(status_code=200, headers={"content-length": str(len(zdata))})
        mock_dl.iter_content = lambda chunk_size=65536: [zdata]
        mock_dl.raise_for_status = lambda: None

        with patch.object(updater, "_safe_request_get", return_value=mock_dl):
            try:
                updater.download_and_prepare_update(
                    "https://github.com/GurpinarSG/NovaCare/releases/download/v1.3.2/NovaCare_Update.zip",
                    new_version="1.3.2",
                    custom_temp_dir=os.path.join(tmp_dir, "t1"),
                    require_integrity=True,
                )
                assert False, "Expected ValueError when require_integrity=True and no hash provided"
            except ValueError as exc:
                assert "SHA-256" in str(exc)

            try:
                updater.download_and_prepare_update(
                    "https://github.com/GurpinarSG/NovaCare/releases/download/v1.3.2/NovaCare_Update.zip",
                    new_version="1.3.2",
                    target_app_root=r"C:\Test\%TEMP%Evil",
                    custom_temp_dir=os.path.join(tmp_dir, "t2"),
                )
                assert False, "Expected ValueError on batch metacharacters in target_app_root"
            except ValueError as exc:
                assert "batch" in str(exc).lower()

            bat_path = updater.download_and_prepare_update(
                "https://github.com/GurpinarSG/NovaCare/releases/download/v1.3.2/NovaCare_Update.zip",
                new_version="1.3.2",
                target_app_root=os.path.join(tmp_dir, "app"),
                custom_temp_dir=os.path.join(tmp_dir, "t3"),
            )
            with open(bat_path, "r", encoding="utf-8-sig") as bf:
                bat_text = bf.read()
            assert "setlocal DisableDelayedExpansion" in bat_text
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print("  [PASS] GitHubUpdater integrity & batch safety verified.")


def test_03_temp_file_isolation():
    print("[3/10] Testing temp file isolation in BatteryReporter & main.py...")
    import main as main_mod
    from core.battery_reporter import BatteryReporter

    src_main = inspect.getsource(main_mod.perform_self_uninstall)
    assert "novacare_uninstall_{os.getpid()}" not in src_main
    assert "tempfile.mkstemp(" in src_main

    src_batt = inspect.getsource(BatteryReporter.fetch_hardware_details)
    assert "novacare_batt_{os.getpid()}" not in src_batt
    assert 'tempfile.mkdtemp(prefix="novacare_batt_")' in src_batt

    tmp_local = tempfile.mkdtemp(prefix="NovaCare_LocalApp_")
    try:
        br = BatteryReporter()
        with patch.dict(os.environ, {"LOCALAPPDATA": tmp_local}), patch("subprocess.run") as mock_run:
            def _fake_powercfg(cmd, **_kw):
                out_idx = cmd.index("/output") + 1
                with open(cmd[out_idx], "w", encoding="utf-8") as rf:
                    rf.write("<html>ok</html>")
                return MagicMock(returncode=0)

            mock_run.side_effect = _fake_powercfg
            report_path = br.generate_html_report()
            assert report_path.startswith(os.path.join(tmp_local, "NovaCare", "Reports"))
            assert os.path.exists(report_path)
    finally:
        shutil.rmtree(tmp_local, ignore_errors=True)
    print("  [PASS] Temp file isolation verified.")


def test_04_backup_secret_non_clobbering():
    print("[4/10] Testing BackupManager secret non-clobbering & ephemeral CSPRNG fallback...")
    import core.backup_manager as bm

    tmp_local = tempfile.mkdtemp(prefix="NovaCare_BkpSec_")
    try:
        sec_dir = os.path.join(tmp_local, "NovaCare")
        os.makedirs(sec_dir, exist_ok=True)
        sec_file = os.path.join(sec_dir, ".backup_secret")
        corrupt_marker = "CORRUPT_UNREADABLE_CIPHER_BLOB_DO_NOT_OVERWRITE"
        with open(sec_file, "w", encoding="utf-8") as f:
            f.write(corrupt_marker)

        with patch.dict(os.environ, {"LOCALAPPDATA": tmp_local}), patch("core.backup_manager.decrypt_string", return_value=""):
            bm._EPHEMERAL_BACKUP_KEY = None
            k1 = bm.get_backup_hmac_key()
            k2 = bm.get_backup_hmac_key()
            assert len(k1) == 32 and k1 == k2
            with open(sec_file, "r", encoding="utf-8") as f:
                assert f.read() == corrupt_marker, "Existing secret file must not be clobbered!"
    finally:
        bm._EPHEMERAL_BACKUP_KEY = None
        shutil.rmtree(tmp_local, ignore_errors=True)
    print("  [PASS] Backup secret key protection verified.")


def test_05_truthful_status_returns():
    print("[5/10] Testing truthful status returns across PrivacyTweaker, StartupManager, GameBooster, RegistryCompactor, NetworkOptimizer...")
    from core.privacy_tweaker import PrivacyTweaker
    from core.startup_manager import StartupManager, StartupItem
    from core.game_booster import GameBooster
    from core.registry_compactor import RegistryCompactor
    from core.network_optimizer import NetworkOptimizer

    # PrivacyTweaker: sc failure (returncode 5) must NOT add to stopped_services
    pt = PrivacyTweaker()
    with patch.object(pt, "apply_tweak", return_value=True), patch("subprocess.run", return_value=MagicMock(returncode=5)):
        _, failed, svcs = pt.apply_all_anti_spy(enable=True)
        assert failed == 2 and svcs == [], f"Expected 2 failures and empty svcs, got failed={failed}, svcs={svcs}"

    # StartupManager: re-enable fallback when StartupApproved fails must return False
    sm = StartupManager()
    item = StartupItem(
        id="test", name="TestApp", command="C:\\test.exe",
        location="HKCU Run", location_type="registry",
        source_key_or_path=r"Software\Microsoft\Windows\CurrentVersion\Run",
        root_name="HKCU", enabled=False, publisher="Tester", boot_impact="Düşük"
    )
    with patch("winreg.CreateKeyEx", side_effect=PermissionError("denied")):
        assert sm.toggle_item(item) is False

    # GameBooster: non-zero net stop / net start must not claim stopped/restored
    gb = GameBooster()
    gb.state_file = os.path.join(tempfile.gettempdir(), f"nc_gb_test_{os.getpid()}.json")
    try:
        fake_svc = MagicMock()
        fake_svc.status.return_value = "running"
        with patch("psutil.win_service_get", return_value=fake_svc), \
             patch("subprocess.run", return_value=MagicMock(returncode=2)), \
             patch.object(gb, "ensure_ultimate_power_plan", return_value=""), \
             patch.object(gb, "get_current_power_scheme", return_value=("", "Balanced")):
            st = gb.activate()
            assert st["stopped_services"] == []
        with open(gb.state_file, "w", encoding="utf-8") as sf:
            json.dump({"stopped_services": ["WSearch"]}, sf)
        with patch("subprocess.run", return_value=MagicMock(returncode=5)):
            deact = gb.deactivate()
            assert deact["restored_services"] == 0
    finally:
        if os.path.exists(gb.state_file):
            os.remove(gb.state_file)

    # RegistryCompactor: return False if all RegFlushKey calls fail
    rc = RegistryCompactor()
    with patch.object(rc, "analyze_hives", return_value=[]), patch("ctypes.windll.advapi32.RegFlushKey", return_value=5):
        ok, reclaimed, _ = rc.compact_and_optimize()
        assert ok is False and reclaimed == 0

    # NetworkOptimizer: reject invalid adapter in get_current_dns & check secondary DNS failure
    no = NetworkOptimizer()
    res = no.get_current_dns('Ethernet"\r\n')
    assert res["servers"] == []
    with patch("subprocess.run", side_effect=[MagicMock(returncode=0), MagicMock(returncode=1, stderr="Bad IP", stdout="")]):
        ok_dns, msg_dns = no.set_dns("Ethernet", "1.1.1.1", "8.8.8.8")
        assert ok_dns is False and "İkincil" in msg_dns
    print("  [PASS] Truthful status returns verified.")


def test_06_hardware_monitor_lock_and_stop():
    print("[6/10] Testing HardwareMonitor NVML lock and clean stop()...")
    from core.hardware_monitor import HardwareMonitor
    src = inspect.getsource(HardwareMonitor.cleanup)
    assert "_nvml_lock" in src
    src_stop = inspect.getsource(HardwareMonitor.stop)
    assert "join(" in src_stop
    hm = HardwareMonitor()
    assert hasattr(hm, "_nvml_lock")
    print("  [PASS] HardwareMonitor NVML lock & cleanup verified.")


def test_07_cookie_shield_and_auto_cleaner():
    print("[7/10] Testing CookieShield graceful close / cancel & AutoCleaner target_day guard...")
    from core.cookie_shield import CookieShield
    from core.auto_cleaner import AutoCleaner
    from datetime import datetime

    cs = CookieShield()
    calls = []
    with patch.object(cs, "is_browser_running", return_value=True), \
         patch("time.sleep"), \
         patch("subprocess.run", side_effect=lambda cmd, **_kw: calls.append(cmd) or MagicMock(returncode=0)):
        assert cs.close_browser("chrome.exe") is True
        assert len(calls) == 2
        assert "/F" not in calls[0] and "/IM" in calls[0]
        assert "/F" in calls[1]

    ac = AutoCleaner()
    now = datetime.now()
    for bad_day in (99, float(now.weekday())):
        with patch.object(ac.config, "get", side_effect=lambda k, d=None, bd=bad_day: {
            "auto_clean_enabled": True,
            "auto_clean_schedule": "scheduled_time",
            "auto_clean_target_day": bd,
            "auto_clean_target_hour": now.hour,
            "last_auto_clean_time": "",
        }.get(k, d)):
            should, _ = ac.should_trigger()
            assert should is False
    print("  [PASS] CookieShield & AutoCleaner guards verified.")


def test_08_duplicate_finder_and_junk_cleaner_paths():
    print("[8/10] Testing DuplicateFinder non-substring guards & JunkCleaner NovaCare username handling...")
    from core.duplicate_finder import DuplicateFinder
    from core.junk_cleaner import JunkCleaner

    assert DuplicateFinder.is_protected_path(r"D:\Backups\WindowsWallpapers\photo.jpg") is False
    assert DuplicateFinder.is_protected_path(r"D:\MyProgram Files Backups\doc.pdf") is False
    assert DuplicateFinder.is_protected_path(r"C:\Windows\System32\cmd.exe") is True
    assert DuplicateFinder.is_protected_path(r"C:\Program Files\App\bin.exe") is True

    tmp_root = tempfile.mkdtemp(prefix="User_NovaCare_Profile_")
    try:
        user_tmp = os.path.join(tmp_root, "AppData", "Local", "Temp")
        os.makedirs(user_tmp, exist_ok=True)
        user_junk = os.path.join(user_tmp, "old_cache.tmp")
        nc_temp = os.path.join(user_tmp, "novacare_batt_123.xml")
        with open(user_junk, "wb") as f:
            f.write(b"123456")
        with open(nc_temp, "wb") as f:
            f.write(b"keepme")

        jc = JunkCleaner()
        temp_cat = next(c for c in jc.categories if c.id == "user_temp")
        temp_cat.paths = [user_tmp]
        jc.scan_all()
        freed, cleaned, _ = jc.clean_categories({"user_temp"})
        assert cleaned == 1 and freed == 6
        assert not os.path.exists(user_junk), "User junk under NovaCare username path must be cleaned"
        assert os.path.exists(nc_temp), "NovaCare runtime temp artifact must stay protected"
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print("  [PASS] Path matching & username preservation verified.")


def test_09_ui_qss_workers_and_dialogs():
    print("[9/10] Testing QSS syntax, DiskView cancel, GameProfilesDialog lifecycle & UI worker guards...")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. AST QSS {{ }} check across all UI files
    ui_files = glob.glob(os.path.join(ROOT_DIR, "ui", "**", "*.py"), recursive=True)
    for path in ui_files:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "setStyleSheet":
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    val = node.args[0].value
                    assert "{{" not in val and "}}" not in val, f"Invalid double-brace QSS in {path}:{node.lineno}"

    # 2. DiskView stop_scan calls cancel() and prevents finished signal after interrupt
    from ui.views.disk_view import DiskView, LargeFileScanThread, DuplicateScanThread
    with patch.object(DiskView, "refresh_drives"):
        dv = DiskView()
        fake_scan = MagicMock()
        fake_scan.isRunning.return_value = True
        fake_dup = MagicMock()
        fake_dup.isRunning.return_value = True
        dv.scan_thread = fake_scan
        dv.dup_thread = fake_dup
        dv.stop_scan()
        fake_scan.cancel.assert_called_once()
        fake_dup.cancel.assert_called_once()

        t_lf = LargeFileScanThread(dv.analyzer, ROOT_DIR, 10, 5)
        emitted = []
        t_lf.finished.connect(emitted.append)
        with patch.object(dv.analyzer, "scan_largest_files", side_effect=lambda *a, **kw: (t_lf.cancel(), [])[1]):
            t_lf.run()
        assert emitted == [], "Cancelled LargeFileScanThread must not emit finished"

        t_dup = DuplicateScanThread(dv.duplicate_finder, [ROOT_DIR], 100)
        emitted_d = []
        t_dup.finished.connect(emitted_d.append)
        with patch.object(dv.duplicate_finder, "scan_duplicates", side_effect=lambda *a, **kw: (t_dup.cancel(), [])[1]):
            t_dup.run()
        assert emitted_d == [], "Cancelled DuplicateScanThread must not emit finished"
        dv.deleteLater()

    # 3. GameProfilesDialog cleanup stops timer & cancels worker on accept()
    from ui.game_profiles_dialog import GameProfilesDialog
    dlg = GameProfilesDialog()
    fake_sw = MagicMock()
    fake_sw.isRunning.return_value = True
    dlg.scan_worker = fake_sw
    assert dlg.status_timer.isActive()
    dlg.accept()
    assert not dlg.status_timer.isActive()
    fake_sw.cancel.assert_called_once()
    dlg.deleteLater()

    # 4. PrivacyView _close_locked_browsers(rescan=False) skips rescan; NetworkView/JunkView/RegistryView/SettingsView guards
    from ui.views.privacy_view import PrivacyView
    with patch.object(PrivacyView, "_refresh_traces"), patch.object(PrivacyView, "_scan_bloatware"), patch.object(PrivacyView, "_scan_cookies"):
        pv = PrivacyView()
        pv.cookie_data = {"locked_browsers": ["Chrome"]}
        with patch.object(pv.cookie_shield, "get_browser_targets", return_value=[{"browser": "Chrome", "exe": "chrome.exe"}]), \
             patch.object(pv.cookie_shield, "close_browser", return_value=True), \
             patch.object(pv, "_scan_cookies") as mock_rescan:
            pv._close_locked_browsers(rescan=False)
            assert mock_rescan.call_count == 0
        pv.deleteLater()

    from ui.views.settings_view import SettingsView
    sv = SettingsView()
    sv.combo_schedule.setCurrentIndex(sv.combo_schedule.findData("daily"))
    sv._update_scheduler_details_ui()
    assert not sv.frame_sch_time.isVisibleTo(sv)
    sv.deleteLater()
    app.processEvents()
    print("  [PASS] UI QSS & worker/lifecycle guards verified.")


def test_10_version_sync():
    print("[10/10] Testing installer_wizard.py & app.manifest version synchronization...")
    with open(os.path.join(ROOT_DIR, "VERSION"), "r", encoding="utf-8") as f:
        ver = f.readline().strip().lstrip("vV")

    with open(os.path.join(ROOT_DIR, "scripts", "installer_wizard.py"), "r", encoding="utf-8") as f:
        wiz_src = f.read()
    assert "v1.0.1" not in wiz_src, "Stale v1.0.1 hardcoded string remains in installer_wizard.py"

    with open(os.path.join(ROOT_DIR, "app.manifest"), "r", encoding="utf-8") as f:
        manifest_src = f.read()
    assert f'version="{ver}.0"' in manifest_src, f"app.manifest must contain version=\"{ver}.0\""
    print("  [PASS] Version synchronization verified.")


if __name__ == "__main__":
    print("=" * 68)
    print("  NovaCare 6th-Pass Deep Security, Threading & UI Audit Suite")
    print("=" * 68)
    test_01_uninstaller_uac_argument_escaping()
    test_02_updater_integrity_and_batch_guards()
    test_03_temp_file_isolation()
    test_04_backup_secret_non_clobbering()
    test_05_truthful_status_returns()
    test_06_hardware_monitor_lock_and_stop()
    test_07_cookie_shield_and_auto_cleaner()
    test_08_duplicate_finder_and_junk_cleaner_paths()
    test_09_ui_qss_workers_and_dialogs()
    test_10_version_sync()
    print("=" * 68)
    print("  ALL 10 AUDIT FIX TEST SUITES PASSED!")
    print("=" * 68)
