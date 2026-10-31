"""
NovaCare System Suite - 4th-Pass Security, Data Integrity & Reliability Verification Suite
Verifies all 8 audit findings:
1. Autostart persistence bug: ensure_default_autostart guards with autostart_on_boot config.
2. Recycle bin data protection: excluded from 1-click care & auto-cleaner by default.
3. Updater fail-closed integrity: sha256sums_url errors strictly raise ValueError.
4. Registry cleaner accuracy & subkey deletion: failed issues preserved in self.issues; delete_registry_key_tree used.
5. In-use file lock elimination: uninstall.bat creates %TEMP% self-deleting cleanup script.
6. Binary search order / path hijacking defense: get_system32_path resolves absolute System32 & PowerShell paths.
7. Headless subprocess pause reliability: timeout /t replaced with ping 127.0.0.1 -n.
8. DPAPI memory leak prevention: CryptProtectData/CryptUnprotectData memory strictly freed via LocalFree in try...finally.
"""
import os
import sys
import inspect
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from core.utils import get_system32_path
from core.config import ConfigManager


def test_1_autostart_persistence_guard():
    print("[1/8] Testing Autostart persistence bug fix (autostart_on_boot config guard)...")
    from core.autostart import ensure_default_autostart
    
    cfg = ConfigManager()
    orig_val = cfg.get("autostart_on_boot", True)

    try:
        # 1. When autostart_on_boot is False, ensure_default_autostart must not register
        cfg.set("autostart_on_boot", False)
        with patch("core.autostart.set_autostart") as mock_set:
            with patch("subprocess.run") as mock_sub:
                ensure_default_autostart()
                assert not mock_set.called, "set_autostart must NOT be called when autostart_on_boot is False!"
                assert not mock_sub.called, "subprocess.run must NOT be called when autostart_on_boot is False!"

        # 2. Verify main.py source code checks autostart_on_boot before ensure_default_autostart
        with open(os.path.join(ROOT_DIR, "main.py"), "r", encoding="utf-8") as f:
            main_src = f.read()
        assert 'if ConfigManager().get("autostart_on_boot", True):' in main_src, "main.py must check autostart_on_boot"

        print("  [✔] Autostart persistence properly guarded: disabled autostart is never re-registered.")
    finally:
        cfg.set("autostart_on_boot", orig_val)


def test_2_recycle_bin_data_loss_protection():
    print("[2/8] Testing Recycle Bin data loss protection (1-click care & auto-cleaner opt-in)...")
    from core.auto_cleaner import AutoCleaner
    from core.junk_cleaner import CleanerCategory
    from ui.views.dashboard_view import DashboardFixWorker

    cfg = ConfigManager()
    orig_opt = cfg.get("auto_clean_recycle_bin", False)

    try:
        # Setup mock junk categories
        mock_cats = [
            CleanerCategory(id="temp", name="Geçici Dosyalar", description="Temp", icon="", paths=[], size=1024, file_count=5),
            CleanerCategory(id="recycle_bin", name="Geri Dönüşüm Kutusu", description="Recycle", icon="", paths=[], size=2048, file_count=2, is_recycle_bin=True),
            CleanerCategory(id="logs", name="Sistem Günlükleri", description="Logs", icon="", paths=[], size=512, file_count=1)
        ]

        # 1. AutoCleaner with auto_clean_recycle_bin = False (default)
        cfg.set("auto_clean_recycle_bin", False)
        cleaner = AutoCleaner()
        cleaner.junk_cleaner = MagicMock()
        cleaner.junk_cleaner.scan_all.return_value = mock_cats
        cleaner.junk_cleaner.clean_categories.return_value = (1536, 6, 0)
        cleaner.memory_booster = MagicMock()
        cleaner.memory_booster.optimize_ram.return_value = (0, 0)

        cleaner.execute_cleanup()
        assert cleaner.junk_cleaner.clean_categories.called
        called_cats = cleaner.junk_cleaner.clean_categories.call_args[0][0]
        assert "recycle_bin" not in called_cats, "recycle_bin must NOT be cleaned when auto_clean_recycle_bin is False!"
        assert "temp" in called_cats
        assert "logs" in called_cats

        # 2. AutoCleaner with auto_clean_recycle_bin = True (explicit opt-in)
        cfg.set("auto_clean_recycle_bin", True)
        cleaner.execute_cleanup()
        called_cats = cleaner.junk_cleaner.clean_categories.call_args[0][0]
        assert "recycle_bin" in called_cats, "recycle_bin should be cleaned when auto_clean_recycle_bin is True!"

        # 3. DashboardFixWorker source check
        dash_src = inspect.getsource(DashboardFixWorker.run)
        assert 'auto_clean_recycle_bin' in dash_src, "DashboardFixWorker must check auto_clean_recycle_bin setting"
        assert 'recycle_bin' in dash_src, "DashboardFixWorker must filter recycle_bin"

        print("  [✔] Windows Recycle Bin is safely excluded from 1-click care and background auto-cleaning by default.")
    finally:
        cfg.set("auto_clean_recycle_bin", orig_opt)


def test_3_updater_fail_closed_integrity():
    print("[3/8] Testing Updater fail-closed checksum verification...")
    from core.updater import GitHubUpdater
    import requests
    import io
    import zipfile

    updater = GitHubUpdater()

    # Create in-memory minimal zip
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as z:
        z.writestr("test.txt", "hello")
    dummy_bytes = zip_buf.getvalue()

    def make_zip_resp():
        resp = MagicMock(status_code=200)
        resp.headers = {"Content-Length": str(len(dummy_bytes))}
        resp.iter_content = MagicMock(return_value=[dummy_bytes])
        return resp

    dl_url = "https://github.com/test/releases/download/v1.0.0/dummy_update.zip"
    sums_url = "https://github.com/test/releases/download/v1.0.0/SHA256SUMS.txt"

    # 1. Test network failure fetching sha256sums_url MUST raise ValueError
    def fake_get_net_err(url, **kwargs):
        if url == dl_url:
            return make_zip_resp()
        raise requests.RequestException("Connection error")

    with patch.object(updater, "_safe_request_get", side_effect=fake_get_net_err):
        try:
            updater.download_and_prepare_update(download_url=dl_url, sha256sums_url=sums_url)
            assert False, "Must raise ValueError on sha256sums_url network failure!"
        except ValueError as e:
            assert "indirilemedi" in str(e) or "SHA-256" in str(e)

    # 2. Test HTTP 404 response MUST raise ValueError
    def fake_get_404(url, **kwargs):
        if url == dl_url:
            return make_zip_resp()
        return MagicMock(status_code=404, text="Not Found")

    with patch.object(updater, "_safe_request_get", side_effect=fake_get_404):
        try:
            updater.download_and_prepare_update(download_url=dl_url, sha256sums_url=sums_url)
            assert False, "Must raise ValueError on HTTP 404 sha256sums_url!"
        except ValueError as e:
            assert "alınamadı" in str(e) or "HTTP 404" in str(e)

    # 3. Test missing hash in SHA256SUMS.txt MUST raise ValueError
    def fake_get_nomatch(url, **kwargs):
        if url == dl_url:
            return make_zip_resp()
        return MagicMock(status_code=200, text="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 other_file.tar.gz")

    with patch.object(updater, "_safe_request_get", side_effect=fake_get_nomatch):
        try:
            updater.download_and_prepare_update(download_url=dl_url, sha256sums_url=sums_url)
            assert False, "Must raise ValueError when target file hash is missing from sums file!"
        except ValueError as e:
            assert "özeti bulunamadı" in str(e)

    # 4. Test checksum mismatch MUST raise ValueError
    def fake_get_mismatch(url, **kwargs):
        if url == dl_url:
            return make_zip_resp()
        return MagicMock(status_code=200, text="0000000000000000000000000000000000000000000000000000000000000000 dummy_update.zip")

    with patch.object(updater, "_safe_request_get", side_effect=fake_get_mismatch):
        try:
            updater.download_and_prepare_update(download_url=dl_url, sha256sums_url=sums_url)
            assert False, "Must raise ValueError on checksum mismatch!"
        except ValueError as e:
            assert "bütünlük doğrulaması başarısız" in str(e)

    print("  [✔] GitHubUpdater fail-closed: unverified, unreachable, or mismatched updates strictly rejected.")


def test_4_registry_cleaner_fix_accuracy_and_subkeys():
    print("[4/8] Testing RegistryCleaner fix tracking accuracy & subkey deletion...")
    from core.registry_cleaner import RegistryCleaner, RegistryIssue

    cleaner = RegistryCleaner()
    cleaner.create_backup = MagicMock(return_value="mock_backup.reg")

    issues = [
        RegistryIssue(id="issue_1", category="Startup", root_name="HKCU", sub_key=r"Software\Test", value_name="Item1", value_data="data", value_type=1, reason="bad"),
        RegistryIssue(id="issue_2", category="Startup", root_name="HKCU", sub_key=r"Software\Test", value_name="Item2", value_data="data", value_type=1, reason="bad"),
        RegistryIssue(id="issue_3", category="AppPath", root_name="HKCU", sub_key=r"Software\Test\SubKey", value_name="", value_data="data", value_type=1, reason="orphaned")
    ]
    cleaner.issues = list(issues)

    # Mock winreg.OpenKey so issue_1 succeeds, issue_2 raises exception (fails), issue_3 uses delete_registry_key_tree
    with patch("winreg.OpenKey"):
        with patch("winreg.DeleteValue") as mock_del_val:
            with patch("core.registry_cleaner.delete_registry_key_tree", return_value=True) as mock_tree:
                def fake_delete(key, val_name):
                    if val_name == "Item2":
                        raise PermissionError("Access denied")
                    elif val_name == "":
                        raise OSError("Cannot delete default value directly")
                mock_del_val.side_effect = fake_delete

                fixed, failed, _ = cleaner.fix_issues(issues)
                assert fixed == 2, f"Expected 2 fixed, got {fixed}"
                assert failed == 1, f"Expected 1 failed, got {failed}"

                # Verify issue_2 (which failed) remains in cleaner.issues!
                remaining_ids = {i.id for i in cleaner.issues}
                assert "issue_2" in remaining_ids, "Failed issue_2 MUST remain in cleaner.issues!"
                assert "issue_1" not in remaining_ids, "Fixed issue_1 must be removed from cleaner.issues"
                assert "issue_3" not in remaining_ids, "Fixed issue_3 must be removed from cleaner.issues"
                assert mock_tree.called, "delete_registry_key_tree must be called for orphaned container"

    # Verify when delete_registry_key_tree returns False, issue remains unfixed
    cleaner2 = RegistryCleaner()
    cleaner2.create_backup = MagicMock(return_value="mock_backup.reg")
    issue_orphaned = RegistryIssue(id="issue_orphaned", category="AppPath", root_name="HKCU", sub_key=r"Software\Protected", value_name="", value_data="data", value_type=1, reason="orphaned")
    cleaner2.issues = [issue_orphaned]
    with patch("winreg.OpenKey"):
        with patch("winreg.DeleteValue", side_effect=OSError("Default val error")):
            with patch("core.registry_cleaner.delete_registry_key_tree", return_value=False):
                f_count, fail_count, _ = cleaner2.fix_issues([issue_orphaned])
                assert f_count == 0, "Should have 0 fixed when tree deletion returns False"
                assert fail_count == 1, "Should have 1 failed when tree deletion returns False"
                assert any(i.id == "issue_orphaned" for i in cleaner2.issues), "Unfixed orphaned issue must remain in cleaner.issues"

        print("  [✔] RegistryCleaner tracks successfully_fixed_ids accurately and utilizes delete_registry_key_tree.")


def test_5_installer_wizard_cleanup_script_file_lock():
    print("[5/8] Testing Installer Wizard in-use file lock elimination (%TEMP% cleanup script)...")
    from scripts.installer_wizard import InstallWorker

    src = inspect.getsource(InstallWorker._generate_uninstaller)
    assert 'novacare_uninst_cleanup.bat' in src, "Must generate novacare_uninst_cleanup.bat in %TEMP%"
    assert '%TEMP%' in src, "Must target %TEMP% for cleanup script"
    assert 'rmdir /s /q "%TARGET_DIR%"' in src, "Cleanup script must delete TARGET_DIR"
    assert 'del /f /q "%~f0"' in src or 'del /f /q "%%~f0"' in src, "Cleanup script must self-delete"

    # 2. Functional End-to-End Execution Test of uninstall.bat & %TEMP% cleanup script
    import tempfile, subprocess, time, shutil
    temp_inst_dir = tempfile.mkdtemp()
    try:
        worker = InstallWorker(temp_inst_dir, False, False, False)
        worker._generate_uninstaller()

        uninst_path = os.path.join(temp_inst_dir, "uninstall.bat")
        assert os.path.exists(uninst_path), "uninstall.bat was not created"

        with open(os.path.join(temp_inst_dir, "dummy.txt"), "w") as f:
            f.write("NovaCare dummy test file")

        p = subprocess.Popen(["cmd.exe", "/c", uninst_path], cwd=temp_inst_dir)
        p.wait(timeout=15)

        t_start = time.time()
        dir_removed = False
        while time.time() - t_start < 8:
            if not os.path.exists(temp_inst_dir):
                dir_removed = True
                break
            time.sleep(0.5)

        assert dir_removed, f"Target directory was not deleted by novacare_uninst_cleanup.bat! Files left: {os.listdir(temp_inst_dir) if os.path.exists(temp_inst_dir) else []}"
    finally:
        shutil.rmtree(temp_inst_dir, ignore_errors=True)
        cleanup_file = os.path.join(tempfile.gettempdir(), "novacare_uninst_cleanup.bat")
        if os.path.exists(cleanup_file):
            try:
                os.remove(cleanup_file)
            except Exception:
                pass

    print("  [✔] uninstall.bat delegates directory deletion to self-deleting %TEMP% batch script, avoiding WinError 32.")


def test_6_binary_search_order_system32_path():
    print("[6/8] Testing get_system32_path and absolute administrative binary calls...")
    
    # 1. Test get_system32_path resolutions
    ps = get_system32_path("powershell")
    assert ps.lower().endswith(r"system32\windowspowershell\v1.0\powershell.exe"), f"Unexpected PowerShell path: {ps}"
    assert os.path.exists(ps), f"PowerShell executable does not exist at {ps}"

    ps_exe = get_system32_path("powershell.exe")
    assert ps_exe.lower() == ps.lower()

    netsh = get_system32_path("netsh")
    assert netsh.lower().endswith(r"system32\netsh.exe"), f"Unexpected netsh path: {netsh}"
    assert os.path.exists(netsh), f"netsh does not exist at {netsh}"

    ipconfig = get_system32_path("ipconfig")
    assert ipconfig.lower().endswith(r"system32\ipconfig.exe")
    assert os.path.exists(ipconfig)

    powercfg = get_system32_path("powercfg")
    assert powercfg.lower().endswith(r"system32\powercfg.exe")
    assert os.path.exists(powercfg)

    schtasks = get_system32_path("schtasks")
    assert schtasks.lower().endswith(r"system32\schtasks.exe")
    assert os.path.exists(schtasks)

    taskkill = get_system32_path("taskkill")
    assert taskkill.lower().endswith(r"system32\taskkill.exe")
    assert os.path.exists(taskkill)

    sc = get_system32_path("sc")
    assert sc.lower().endswith(r"system32\sc.exe")
    assert os.path.exists(sc)

    # 2. Verify callers import and use get_system32_path
    caller_modules = [
        "core/network_optimizer.py",
        "core/game_booster.py",
        "core/bloatware_cleaner.py",
        "core/backup_manager.py",
        "core/autostart.py",
        "core/cookie_shield.py",
        "core/smart_reporter.py",
        "core/hardware_monitor.py",
        "core/battery_reporter.py",
        "core/uninstaller.py",
        "main.py",
        "scripts/create_shortcut.py",
    ]
    for rel_path in caller_modules:
        full_p = os.path.join(ROOT_DIR, rel_path)
        with open(full_p, "r", encoding="utf-8") as f:
            code = f.read()
        assert "get_system32_path" in code, f"{rel_path} must import and utilize get_system32_path"

    print("  [✔] Administrative subprocesses strictly use absolute System32 & PowerShell paths against PATH hijacking.")


def test_7_headless_subprocess_ping_pauses():
    print("[7/8] Testing elimination of timeout /t in headless/detached batch scripts...")
    
    # Verify no 'timeout /t' in main.py, installer_wizard.py, updater.py
    checked_files = [
        "main.py",
        "scripts/installer_wizard.py",
        "core/updater.py"
    ]
    for rel_p in checked_files:
        full_p = os.path.join(ROOT_DIR, rel_p)
        with open(full_p, "r", encoding="utf-8") as f:
            content = f.read()
        assert "timeout /t" not in content, f"{rel_p} still contains 'timeout /t'!"
        assert "ping 127.0.0.1 -n" in content, f"{rel_p} must use 'ping 127.0.0.1 -n' for headless pauses"

    print("  [✔] All headless / non-interactive batch pauses utilize robust ping 127.0.0.1 -n (no stdin redirection errors).")


def test_8_dpapi_memory_leak_try_finally():
    print("[8/8] Testing DPAPI memory leak prevention (LocalFree in try...finally)...")
    from core.security import encrypt_string, decrypt_string
    import core.security as sec_mod

    # 1. Source verification of try...finally LocalFree
    src = inspect.getsource(sec_mod.encrypt_string)
    assert "finally:" in src and "LocalFree" in src, "encrypt_string must free memory in finally block"

    src_dec = inspect.getsource(sec_mod.decrypt_string)
    assert "finally:" in src_dec and "LocalFree" in src_dec, "decrypt_string must free memory in finally block"

    # Verify 64-bit ctypes argtypes and restype
    import ctypes
    assert getattr(ctypes.windll.kernel32.LocalFree, "argtypes", None) == [ctypes.c_void_p], "LocalFree.argtypes must be [c_void_p]"
    assert getattr(ctypes.windll.kernel32.LocalFree, "restype", None) == ctypes.c_void_p, "LocalFree.restype must be c_void_p"

    # 2. Functional round-trip verification
    secret = "Test-NovaCare-DPAPI-Secret-2026-SuperSecure!"
    enc = encrypt_string(secret)
    assert enc and enc != secret, "Encryption must produce non-empty ciphertext"
    dec = decrypt_string(enc)
    assert dec == secret, f"Decrypted text '{dec}' did not match original '{secret}'"

    # 3. Unicode and edge cases
    unicode_secret = "Türkçe karakterler: ğüşıöç ĞÜŞİÖÇ & 🚀 emoji test"
    enc_u = encrypt_string(unicode_secret)
    assert decrypt_string(enc_u) == unicode_secret

    assert encrypt_string("") == ""
    assert decrypt_string("") == ""
    assert decrypt_string("invalid_non_hex_string") == ""

    print("  [✔] DPAPI memory strictly freed via kernel32.LocalFree in try...finally under all conditions.")


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare 4th-Pass Security, Data Integrity & Reliability Suite")
    print("=" * 65)
    test_1_autostart_persistence_guard()
    test_2_recycle_bin_data_loss_protection()
    test_3_updater_fail_closed_integrity()
    test_4_registry_cleaner_fix_accuracy_and_subkeys()
    test_5_installer_wizard_cleanup_script_file_lock()
    test_6_binary_search_order_system32_path()
    test_7_headless_subprocess_ping_pauses()
    test_8_dpapi_memory_leak_try_finally()
    print("=" * 65)
    print("  >>> ALL 8 SECURITY AUDIT #4 TESTS PASSED FLAWLESSLY! <<<")
    print("=" * 65)
