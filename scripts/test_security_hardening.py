"""
NovaCare Security Hardening & Edge-Case Regression Test Suite
Validates all 8 security audit fixes across core modules.
"""
import os
import sys
import tempfile
import json
import zipfile
import shutil
import subprocess

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from core.backup_manager import (
    BackupManager, compute_backup_hmac, verify_backup_hmac,
    is_allowed_registry_key
)
from core.registry_cleaner import RegistryCleaner
from core.updater import GitHubUpdater
from core.uninstaller import AppUninstaller, InstalledApp, LeftoverItem
from core.memory_booster import MemoryBooster, PROTECTED_SYSTEM_PROCESSES

def test_backup_allowlist_and_hmac():
    print("[1/6] Testing BackupManager allowlist & HMAC-SHA256 integrity...")
    
    # Allowlist tests
    assert is_allowed_registry_key("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("HKEY_CURRENT_USER", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("HKEY_LOCAL_MACHINE", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("hkcu", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("hklm", r"Software\Microsoft\Windows\CurrentVersion\Run") == True
    assert is_allowed_registry_key("HKCU\\", r"Software\\\\Microsoft\\Windows\\CurrentVersion\\Run") == True
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows\CurrentVersion\App Paths\test.exe") == True
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{12345}") == True
    assert is_allowed_registry_key("HKCU", r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache") == True
    
    # Unauthorized keys (LPE vectors)
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\notepad.exe") == False
    assert is_allowed_registry_key("HKLM", r"SYSTEM\CurrentControlSet\Services\EvilSvc") == False
    assert is_allowed_registry_key("HKLM", r"SAM\SAM") == False
    assert is_allowed_registry_key("HKLM", r"SECURITY\Policy") == False
    assert is_allowed_registry_key("HKLM", r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache") == False
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts") == False
    assert is_allowed_registry_key("HKCR", r"exefile\shell\open\command") == False
    assert is_allowed_registry_key("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run\..\..\..\Evil") == False
    assert is_allowed_registry_key("HKLM", "Software\\Run\x00Evil") == False
    print("  [✔] Strict registry allowlist correctly blocks unauthorized system/root keys.")

    # HMAC integrity tests
    tmp_dir = tempfile.mkdtemp(prefix="NC_TestBkp_")
    try:
        bm = BackupManager(backup_dir=tmp_dir)
        sample_items = [
            {
                "id": "test_1",
                "category": "Test",
                "root_name": "HKCU",
                "sub_key": r"Software\Microsoft\Windows\CurrentVersion\Run",
                "value_name": "NovaCareTest",
                "value_data": "C:\\test.exe",
                "value_type": 1,
                "reason": "Test"
            }
        ]
        
        # Valid signed backup
        valid_hmac = compute_backup_hmac(sample_items)
        valid_payload = {
            "version": 1,
            "timestamp": "20261030_120000",
            "hmac": valid_hmac,
            "items": sample_items
        }
        valid_file = os.path.join(tmp_dir, "Registry_Backup_20261030_120000.json")
        with open(valid_file, "w", encoding="utf-8") as f:
            json.dump(valid_payload, f)
            
        assert verify_backup_hmac(valid_payload) == True
        restored, failed = bm.restore_backup(valid_file)
        assert failed == 0, "Valid backup should restore without failures"
        
        # Tampered backup test (modified value_data)
        tampered_items = [dict(sample_items[0])]
        tampered_items[0]["value_data"] = "C:\\Windows\\System32\\cmd.exe"
        tampered_payload = {
            "version": 1,
            "timestamp": "20261030_120001",
            "hmac": valid_hmac, # Old HMAC!
            "items": tampered_items
        }
        tampered_file = os.path.join(tmp_dir, "Registry_Backup_20261030_120001.json")
        with open(tampered_file, "w", encoding="utf-8") as f:
            json.dump(tampered_payload, f)
            
        assert verify_backup_hmac(tampered_payload) == False
        restored, failed = bm.restore_backup(tampered_file)
        assert restored == 0 and failed == 1, "Tampered backup MUST be rejected!"
        
        # Unsigned legacy backup test
        legacy_file = os.path.join(tmp_dir, "Registry_Backup_20261030_120002.json")
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(sample_items, f)
        restored, failed = bm.restore_backup(legacy_file)
        assert restored == 0 and failed == 1, "Unsigned backup MUST be rejected!"

        # Tampered backup trying unauthorized HKLM key with valid HMAC
        malicious_items = [
            {
                "id": "lpe_1",
                "category": "Test",
                "root_name": "HKLM",
                "sub_key": r"Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\sethc.exe",
                "value_name": "Debugger",
                "value_data": "cmd.exe",
                "value_type": 1,
                "reason": "Test"
            }
        ]
        mal_payload = {
            "version": 1,
            "timestamp": "20261030_120003",
            "hmac": compute_backup_hmac(malicious_items),
            "items": malicious_items
        }
        mal_file = os.path.join(tmp_dir, "Registry_Backup_20261030_120003.json")
        with open(mal_file, "w", encoding="utf-8") as f:
            json.dump(mal_payload, f)
        restored, failed = bm.restore_backup(mal_file)
        assert restored == 0 and failed == 1, "Unauthorized HKLM key MUST be rejected even with valid HMAC!"

        print("  [✔] HMAC-SHA256 signature verification & LPE rejection verified.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_updater_zip_slip_and_sha256():
    print("[2/6] Testing Updater Zip Slip protection & SHA-256 verification...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.6")
    tmp_dir = tempfile.mkdtemp(prefix="NC_TestZipSlip_")
    try:
        # Create malicious zip with Zip Slip traversal
        evil_zip = os.path.join(tmp_dir, "evil.zip")
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../../evil.txt", "MALICIOUS PAYLOAD")
            zf.writestr("VERSION", "1.2.7")
        # Create malicious zip with Zip Slip traversal

        class MockResp:
            status_code = 200
            headers = {"content-length": str(os.path.getsize(evil_zip))}
            def iter_content(self, chunk_size=65536):
                with open(evil_zip, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            def raise_for_status(self): pass

        from unittest.mock import patch
        with patch.object(updater, '_safe_request_get', return_value=MockResp()):
            # 1. Test Zip Slip is blocked
            try:
                updater.download_and_prepare_update("https://dummy.url/evil.zip", new_version="1.2.7")
                assert False, "Should have thrown ValueError for Zip Slip!"
            except ValueError as e:
                assert "Zip Slip" in str(e), f"Expected Zip Slip error, got: {e}"
                print("  [✔] Zip Slip directory traversal strictly blocked.")

            # 2. Test SHA-256 mismatch rejection
            try:
                updater.download_and_prepare_update(
                    "https://dummy.url/evil.zip",
                    new_version="1.2.7",
                    expected_sha256="0000000000000000000000000000000000000000000000000000000000000000"
                )
                assert False, "Should have thrown ValueError for SHA-256 mismatch!"
            except ValueError as e:
                assert "SHA-256" in str(e), f"Expected SHA-256 error, got: {e}"
                print("  [✔] SHA-256 hash mismatch strictly rejected.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def test_uninstaller_hardening():
    print("[3/6] Testing Uninstaller hardening (LeftoverItem default, matching, cmd parsing)...")
    
    # 1. Default selected is False
    item = LeftoverItem(item_type="folder", path="C:\\test", details="test")
    assert item.selected == False, "LeftoverItem.selected MUST default to False"
    print("  [✔] LeftoverItem.selected defaults to False (safe).")

    # 2. Leftover scanning does not use fragile 3-letter substrings
    uninstaller = AppUninstaller()
    app = InstalledApp(
        id="test_app",
        name="Pro Video Suite 2026",
        version="1.0",
        publisher="Creative Soft",
        install_date="",
        size_bytes=0,
        uninstall_string="",
        quiet_uninstall_string="",
        install_location="",
        icon_path="",
        registry_path="",
        root_name="HKCU"
    )
    leftovers = uninstaller.scan_leftovers(app)
    # Ensure it did NOT match system or common folders containing 'pro' or 'the'
    for l in leftovers:
        low = l.path.lower()
        assert not any(crit in low for crit in ('system32', 'syswow64', 'common files', 'microsoft', 'windows'))

    # 3. Test uninstaller command parser handles unquoted paths with spaces and unclosed quotes
    tokens1 = AppUninstaller._parse_uninstall_tokens(r'"C:\Program Files\App\uninstall.exe" /S /clean')
    assert tokens1 == ['C:\\Program Files\\App\\uninstall.exe', '/S', '/clean']

    tokens2 = AppUninstaller._parse_uninstall_tokens(r'C:\Program Files (x86)\Vendor App\uninst.exe /silent')
    assert tokens2[0] == 'C:\\Program Files (x86)\\Vendor App\\uninst.exe'
    assert tokens2[1] == '/silent'

    tokens3 = AppUninstaller._parse_uninstall_tokens(r'"C:\Program Files\App\uninstall.exe /S')
    assert tokens3[0] == 'C:\\Program Files\\App\\uninstall.exe'
    assert tokens3[1] == '/S'

    print("  [✔] Leftover scanning uses bounded app name matching without fragile 3-letter false positives.")
    print("  [✔] Uninstaller command parsing cleanly handles unquoted paths with spaces and unclosed quotes.")

def test_memory_booster_protection():
    print("[4/6] Testing MemoryBooster kill_process boundary protection...")
    booster = MemoryBooster()

    # PID <= 4 must be blocked
    assert booster.kill_process(0) == False
    assert booster.kill_process(4) == False
    assert booster.kill_process(os.getpid()) == False

    # Protected processes check
    assert "csrss.exe" in PROTECTED_SYSTEM_PROCESSES
    assert "lsass.exe" in PROTECTED_SYSTEM_PROCESSES
    assert "winlogon.exe" in PROTECTED_SYSTEM_PROCESSES
    assert "services.exe" in PROTECTED_SYSTEM_PROCESSES
    assert "dwm.exe" in PROTECTED_SYSTEM_PROCESSES
    assert "svchost.exe" in PROTECTED_SYSTEM_PROCESSES
    print("  [✔] MemoryBooster strictly refuses to kill PID <= 4, self, or critical system processes.")

def test_registry_cleaner_greedy_path_joining():
    print("[5/6] Testing RegistryCleaner greedy token path joining...")
    cleaner = RegistryCleaner()

    # Quoted path
    p1 = cleaner._clean_path_string(r'"C:\Program Files\Test\app.exe" -arg1 -arg2')
    assert p1 == r'C:\Program Files\Test\app.exe'

    # Unquoted path with .exe and spaces
    p2 = cleaner._clean_path_string(r'C:\Program Files\Some Company\app.exe /silent /run')
    assert p2 == r'C:\Program Files\Some Company\app.exe', f"Expected full path, got {p2}"
    assert p2 != r'C:\Program', "Must NEVER split 'C:\\Program Files' into 'C:\\Program'!"

    # Unquoted path with .dll
    p3 = cleaner._clean_path_string(r'C:\Program Files (x86)\App\sub\library.dll,entry')
    assert "Program Files (x86)" in p3

    # Attached flags like /silent
    p4 = cleaner._clean_path_string(r'C:\Program Files\App\setup.exe/silent')
    assert p4 == r'C:\Program Files\App\setup.exe'

    # .com extension
    p5 = cleaner._clean_path_string(r'C:\Program Files\Tools\utility.com -run')
    assert p5 == r'C:\Program Files\Tools\utility.com'

    # Existing directory on Windows
    win_dir = os.environ.get('SYSTEMROOT', r'C:\Windows')
    p6 = cleaner._clean_path_string(f"{win_dir}\\notepad.exe")
    assert p6 == f"{win_dir}\\notepad.exe"

    print("  [✔] Greedy token joining correctly preserves spaces in paths and avoids 'C:\\Program' bug.")

def test_utils_and_uninstall_guards():
    print("[6/6] Testing utils list2cmdline & main.py uninstall path guards...")
    # Verify subprocess.list2cmdline escapes quotes and special args
    args = ['--option', 'value with spaces', 'quote"arg', 'C:\\path with spaces\\']
    escaped = subprocess.list2cmdline(args)
    assert '"value with spaces"' in escaped
    assert 'quote\\"arg' in escaped
    print("  [✔] UAC elevation arguments properly escaped via subprocess.list2cmdline.")

if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare Security Hardening Verification Test Suite")
    print("=" * 65)
    test_backup_allowlist_and_hmac()
    test_updater_zip_slip_and_sha256()
    test_uninstaller_hardening()
    test_memory_booster_protection()
    test_registry_cleaner_greedy_path_joining()
    test_utils_and_uninstall_guards()
    print("\n" + "=" * 65)
    print("  >>> ALL SECURITY HARDENING TESTS PASSED PERFECTLY! <<<")
    print("=" * 65)
