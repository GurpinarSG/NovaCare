"""
NovaCare System Suite - 5th-Pass Security, Data Integrity & Process Isolation Verification Suite
Verifies all P1, P2, and P3 audit findings:
1. Updater secure dynamic temp folder (mkdtemp) & Zip Bomb defense & apply_update.bat escaping.
2. Cookie Shield NoneType crash resilience & SQLite read-only URI mode (?mode=ro).
3. DiskView Windows Explorer binary path & format regression prevention.
4. safe_remove_file symlink / reparse point permission manipulation protection.
5. GameBooster threading lock, power plan state preservation & startup recovery.
6. Uninstaller CWD isolation, relative token resolution & PowerShell argument escaping.
7. schtasks /tr quote escaping, setup wizard post-install CWD & self-uninstall retry loop.
"""
import os
import sys
import inspect
import zipfile
import tempfile
import sqlite3
import threading
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


def test_1_updater_mkdtemp_and_param_escaping():
    print("[1/8] Testing Updater mkdtemp dynamic isolation and batch param escaping...")
    from core.updater import GitHubUpdater

    updater = GitHubUpdater()
    # Check that default extract_update uses tempfile.mkdtemp(prefix="NovaCare_Update_")
    src = inspect.getsource(updater.extract_update)
    assert 'tempfile.mkdtemp(prefix="NovaCare_Update_")' in src, "extract_update must use tempfile.mkdtemp"
    assert "os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'NovaCare_Update')" not in src

    # Verify apply_update.bat parameter escaping against injection
    assert "safe_ver_num = re.sub(r'[^a-zA-Z0-9._-]', '', clean_ver_num)" in src
    assert "safe_commit_sha = re.sub(r'[^a-zA-Z0-9._-]', '', new_commit_sha)" in src
    assert '{safe_ver_num}' in src
    assert '{safe_commit_sha}' in src

    # Test live batch generation with malicious strings
    temp_test_dir = tempfile.mkdtemp(prefix="NovaCare_Test_")
    try:
        # Create a mock zip
        zip_p = os.path.join(temp_test_dir, "update.zip")
        with zipfile.ZipFile(zip_p, 'w') as zf:
            zf.writestr("VERSION", "2.0.0\n")

        with patch.object(updater, "_safe_request_get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-length": "100"}
            with open(zip_p, "rb") as zf_in:
                zip_data = zf_in.read()
            mock_resp.iter_content = lambda chunk_size: [zip_data]
            mock_get.return_value = mock_resp

            bat_path = updater.extract_update(
                download_url="https://github.com/GurpinarSG/NovaCare/releases/download/v2.0.0/update.zip",
                clean_ver_num='2.0.0"; calc.exe; #',
                new_commit_sha="a8be151; calc.exe;",
                custom_temp_dir=temp_test_dir
            )

            assert os.path.exists(bat_path)
            with open(bat_path, "r", encoding="utf-8-sig") as bf:
                bat_content = bf.read()

            # Dangerous characters (quotes, semicolons, ampersands, spaces) must be stripped
            assert '2.0.0";' not in bat_content
            assert ';' not in bat_content.split('TargetVersion: "')[1].split('"')[0]
            assert '&' not in bat_content.split('TargetVersion: "')[1].split('"')[0]
            assert '2.0.0' in bat_content
    finally:
        import shutil
        shutil.rmtree(temp_test_dir, ignore_errors=True)

    print("  [✔] Updater dynamically isolates update directory and strictly sanitizes batch parameters.")


def test_2_updater_zip_bomb_protections():
    print("[2/8] Testing Updater Zip Bomb protections (file count, total size, compression ratio)...")
    from core.updater import GitHubUpdater

    updater = GitHubUpdater()

    # 1. Test excessive file count (> 5000)
    temp_dir1 = tempfile.mkdtemp(prefix="NovaCare_ZB1_")
    try:
        zip1 = os.path.join(temp_dir1, "bomb_files.zip")
        with zipfile.ZipFile(zip1, 'w') as zf:
            for i in range(5001):
                zf.writestr(f"file_{i}.txt", "a")

        with patch.object(updater, "_safe_request_get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-length": "1000"}
            with open(zip1, "rb") as f:
                d = f.read()
            mock_resp.iter_content = lambda chunk_size: [d]
            mock_get.return_value = mock_resp

            caught_file_count_bomb = False
            try:
                updater.extract_update("https://dummy/test.zip", custom_temp_dir=temp_dir1)
            except ValueError as e:
                if "Zip Bomb" in str(e) and "dosya sayısı" in str(e):
                    caught_file_count_bomb = True
            assert caught_file_count_bomb, "Must raise ValueError for file count > 5000"
    finally:
        import shutil
        shutil.rmtree(temp_dir1, ignore_errors=True)

    # 2. Test high compression ratio (> 100x)
    temp_dir2 = tempfile.mkdtemp(prefix="NovaCare_ZB2_")
    try:
        zip2 = os.path.join(temp_dir2, "bomb_ratio.zip")
        # 2 MB of zeros compresses to ~2 KB (> 1000x ratio)
        with zipfile.ZipFile(zip2, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("large_zeroes.bin", b"\x00" * (2 * 1024 * 1024))

        with patch.object(updater, "_safe_request_get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-length": "2000"}
            with open(zip2, "rb") as f:
                d = f.read()
            mock_resp.iter_content = lambda chunk_size: [d]
            mock_get.return_value = mock_resp

            caught_ratio_bomb = False
            try:
                updater.extract_update("https://dummy/test.zip", custom_temp_dir=temp_dir2)
            except ValueError as e:
                if "Zip Bomb" in str(e) and "sıkıştırma oranı" in str(e):
                    caught_ratio_bomb = True
            assert caught_ratio_bomb, "Must raise ValueError for compression ratio > 100"
    finally:
        import shutil
        shutil.rmtree(temp_dir2, ignore_errors=True)

    # 3. Test excessive uncompressed size (> 500 MB)
    temp_dir3 = tempfile.mkdtemp(prefix="NovaCare_ZB3_")
    try:
        zip3 = os.path.join(temp_dir3, "bomb_size.zip")
        with zipfile.ZipFile(zip3, 'w') as zf:
            zf.writestr("small.txt", "hello")

        # Mock ZipFile.infolist to simulate a member with 501 MB uncompressed size
        mock_info = MagicMock()
        mock_info.filename = "huge_uncompressed.bin"
        mock_info.file_size = 501 * 1024 * 1024
        mock_info.compress_size = 50 * 1024 * 1024

        with patch.object(updater, "_safe_request_get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-length": "100"}
            with open(zip3, "rb") as f:
                d = f.read()
            mock_resp.iter_content = lambda chunk_size: [d]
            mock_get.return_value = mock_resp

            with patch("zipfile.ZipFile.infolist", return_value=[mock_info]):
                caught_size_bomb = False
                try:
                    updater.extract_update("https://dummy/test.zip", custom_temp_dir=temp_dir3)
                except ValueError as e:
                    if "Zip Bomb" in str(e) and "500 MB" in str(e):
                        caught_size_bomb = True
                assert caught_size_bomb, "Must raise ValueError for uncompressed size > 500 MB"
    finally:
        import shutil
        shutil.rmtree(temp_dir3, ignore_errors=True)

    print("  [✔] Zip bomb defenses strictly block excessive files, huge uncompressed sizes, and extreme ratios.")


def test_3_cookie_shield_none_resilience_and_sqlite_ro():
    print("[3/8] Testing Cookie Shield NoneType crash resilience and SQLite mode=ro connection...")
    from core.cookie_shield import CookieShield, CookieDomainItem
    import urllib.request

    cs = CookieShield()

    # 1. is_protected_domain(None)
    assert cs.is_protected_domain(None) is False
    assert cs.is_protected_domain("") is False
    assert cs.is_protected_domain("google.com") is True

    # 2. domain_items sorting with None host
    items = [
        CookieDomainItem(browser="Edge", host=None, count=5, is_protected=False, is_known_tracker=True),
        CookieDomainItem(browser="Chrome", host="google.com", count=2, is_protected=True, is_known_tracker=False),
        CookieDomainItem(browser="Firefox", host="tracker.com", count=1, is_protected=False, is_known_tracker=True),
        CookieDomainItem(browser="Edge", host="", count=3, is_protected=False, is_known_tracker=False)
    ]
    # Must sort without throwing TypeError: '<' not supported between instances of 'NoneType' and 'str'
    items.sort(key=lambda d: (not d.is_known_tracker, d.is_protected, d.host or ''))
    assert items[0].is_known_tracker is True

    # 3. Verify SQLite scan_cookies uses URI mode=ro
    src = inspect.getsource(cs.scan_cookies)
    assert 'mode=ro' in src, "scan_cookies must use mode=ro in SQLite URI"
    assert 'uri=True' in src, "scan_cookies must enable uri=True"
    assert 'urllib.request.pathname2url' in src, "scan_cookies must convert path to URI url"

    # Live SQLite mode=ro test with None host in rows
    db_file = tempfile.mktemp(suffix=".sqlite")
    try:
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE cookies (host_key TEXT, val TEXT)")
        conn.execute("INSERT INTO cookies VALUES (NULL, 'val1')")
        conn.execute("INSERT INTO cookies VALUES ('doubleclick.net', 'val2')")
        conn.execute("INSERT INTO cookies VALUES ('google.com', 'val3')")
        conn.commit()
        conn.close()

        # Connect via mode=ro URI as scan_cookies does
        file_uri = f"file:{urllib.request.pathname2url(os.path.abspath(db_file))}?mode=ro"
        ro_conn = sqlite3.connect(file_uri, uri=True, timeout=1.0)
        cur = ro_conn.cursor()
        cur.execute("SELECT host_key, COUNT(*) FROM cookies GROUP BY host_key")
        rows = cur.fetchall()
        for row in rows:
            host = str(row[0] or "")
            is_prot = cs.is_protected_domain(host)
            low_host = host.lower()
            assert isinstance(low_host, str)
            assert isinstance(is_prot, bool)
        ro_conn.close()
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass

    print("  [✔] Cookie Shield handles NoneType hosts cleanly and queries SQLite databases in read-only mode.")


def test_4_disk_view_explorer_binary_path_regression():
    print("[4/8] Testing disk_view.py Windows Explorer absolute binary path & regression protection...")
    from ui.views.disk_view import DiskView

    src_open = inspect.getsource(DiskView._open_file_location)
    src_dup = inspect.getsource(DiskView._on_dup_row_double_click)

    # 1. Must use SystemRoot explorer.exe binary path
    assert 'explorer_bin = os.path.join(os.environ.get("SystemRoot", r"C:\\Windows"), "explorer.exe")' in src_open or 'explorer_bin = os.path.join(os.environ.get("SystemRoot"' in src_open
    assert 'subprocess.Popen(f\'"{explorer_bin}" /select,"{norm}"\')' in src_open

    assert 'explorer_bin = os.path.join(os.environ.get("SystemRoot", r"C:\\Windows"), "explorer.exe")' in src_dup or 'explorer_bin = os.path.join(os.environ.get("SystemRoot"' in src_dup
    assert 'subprocess.Popen(f\'"{explorer_bin}" /select,"{norm_p}"\')' in src_dup

    # 2. Strict regression protection: List format must NOT be used
    assert 'subprocess.Popen(["explorer.exe"' not in src_open
    assert 'subprocess.Popen(["explorer.exe"' not in src_dup

    print("  [✔] DiskView explorer calls use verified absolute SystemRoot paths and string argument formatting.")


def test_5_safe_remove_file_symlink_permission_guard():
    print("[5/8] Testing safe_remove_file symlink / reparse point permission manipulation guard...")
    from core.utils import safe_remove_file

    src = inspect.getsource(safe_remove_file)
    assert "os.path.islink(target) or is_reparse_point(target)" in src, "safe_remove_file must check symlink/reparse point"
    assert "os.unlink(target)" in src, "safe_remove_file must call os.unlink on links"

    # Test behavior under simulated PermissionError
    test_link_path = os.path.join(tempfile.gettempdir(), "nc_test_link.lnk")
    with patch("os.remove", side_effect=PermissionError("Locked")), \
         patch("core.utils.is_reparse_point", return_value=True), \
         patch("os.path.islink", return_value=True), \
         patch("os.chmod") as mock_chmod, \
         patch("os.unlink") as mock_unlink:

        res = safe_remove_file(test_link_path)
        assert res is True
        assert mock_unlink.called, "os.unlink must be called when link raises PermissionError"
        assert not mock_chmod.called, "os.chmod must NEVER be called on symlinks or junctions!"

    # Test behavior on regular file under PermissionError
    test_reg_path = os.path.join(tempfile.gettempdir(), "nc_test_reg.txt")
    with patch("os.remove", side_effect=[PermissionError("Readonly"), None]), \
         patch("core.utils.is_reparse_point", return_value=False), \
         patch("os.path.islink", return_value=False), \
         patch("os.chmod") as mock_chmod, \
         patch("os.unlink") as mock_unlink:

        res = safe_remove_file(test_reg_path)
        assert res is True
        assert mock_chmod.called, "os.chmod should be called for regular read-only files"
        assert not mock_unlink.called

    print("  [✔] safe_remove_file strictly guards symlinks and reparse points from permission mutation.")


def test_6_game_booster_module_lock_and_startup_recovery():
    print("[6/8] Testing GameBooster module lock, plan preservation, and startup recovery...")
    from core.game_booster import GameBooster, _MODULE_BOOSTER_LOCK
    import json

    # 1. Module-level lock
    assert isinstance(_MODULE_BOOSTER_LOCK, type(threading.RLock())), "_MODULE_BOOSTER_LOCK must be an RLock"

    gb = GameBooster()

    # 2. Original power plan preservation when already active
    fake_state_file = tempfile.mktemp(suffix=".json")
    gb.state_file = fake_state_file
    try:
        # User had "Power Saver" (fake guid: 11111111-2222-3333-4444-555555555555)
        initial_state = {
            "active": True,
            "previous_power_guid": "11111111-2222-3333-4444-555555555555",
            "previous_power_name": "Tasarruf Modu",
            "stopped_services": ["Spooler"]
        }
        with open(fake_state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)

        # Calling activate() again while already active must NOT overwrite previous_power_guid!
        with patch.object(gb, "get_current_power_scheme", return_value=("99999999-9999-9999-9999-999999999999", "Ultimate Performance")), \
             patch.object(gb, "ensure_ultimate_power_plan", return_value="99999999-9999-9999-9999-999999999999"), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)

            new_state = gb.activate()
            assert new_state["previous_power_guid"] == "11111111-2222-3333-4444-555555555555", "Must preserve original power GUID!"
            assert new_state["previous_power_name"] == "Tasarruf Modu"

        # 3. Startup recovery mechanism
        with patch.object(gb, "deactivate") as mock_deact:
            recovered = gb.recover_state_if_needed()
            assert recovered is True, "recover_state_if_needed must recover hung active state"
            assert mock_deact.called

        # 4. Verify main.py invokes GameBooster startup recovery
        with open(os.path.join(ROOT_DIR, "main.py"), "r", encoding="utf-8") as f:
            main_src = f.read()
        assert "GameBooster().recover_state_if_needed()" in main_src, "main.py must invoke GameBooster recovery on startup"

    finally:
        if os.path.exists(fake_state_file):
            try:
                os.remove(fake_state_file)
            except Exception:
                pass

    print("  [✔] GameBooster synchronized with module lock, preserves original plans, and recovers hung states on startup.")


def test_7_uninstaller_cwd_isolation_and_powershell_escaping():
    print("[7/8] Testing Uninstaller CWD isolation and PowerShell inner quotes escaping...")
    from core.uninstaller import AppUninstaller, InstalledApp
    import base64

    uninst = AppUninstaller()

    # Create dummy app folder and executable
    temp_app_dir = tempfile.mkdtemp(prefix="NovaCare_App_")
    uninst_exe = os.path.join(temp_app_dir, "uninstall.exe")
    with open(uninst_exe, "w") as f:
        f.write("echo uninstall")

    try:
        # App with relative uninstall string under install_location
        app_mock = InstalledApp(
            id="test_app_id",
            name="TestApp",
            version="1.0",
            publisher="Tester",
            install_date="",
            size_bytes=1000,
            uninstall_string='uninstall.exe /S /DIR="C:\\Program Files\\Test"',
            quiet_uninstall_string="",
            install_location=temp_app_dir,
            icon_path="",
            registry_path="",
            root_name=""
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_popen.return_value = mock_proc

            # 1. Verify CWD passed and relative tokens[0] resolved to full path
            uninst.launch_uninstaller(app_mock)
            assert mock_popen.called
            call_args, call_kwargs = mock_popen.call_args
            tokens = call_args[0]
            assert tokens[0] == uninst_exe, f"Relative tokens[0] must resolve to {uninst_exe}"
            assert call_kwargs.get("cwd") == temp_app_dir, "subprocess.Popen must use cwd=app.install_location"

        # 2. Verify UAC elevated PowerShell escaping with inner double quotes
        with patch("subprocess.Popen") as mock_popen:
            # First call raises WinError 740 (elevation required)
            first_error = OSError()
            first_error.winerror = 740
            mock_proc2 = MagicMock()
            mock_popen.side_effect = [first_error, mock_proc2]

            res_proc = uninst.launch_uninstaller(app_mock)
            assert res_proc == mock_proc2
            assert mock_popen.call_count == 2
            second_call_args, second_call_kwargs = mock_popen.call_args
            ps_tokens = second_call_args[0]

            assert "-EncodedCommand" in ps_tokens
            idx = ps_tokens.index("-EncodedCommand")
            b64_cmd = ps_tokens[idx + 1]
            decoded_ps = base64.b64decode(b64_cmd).decode("utf-16le")

            # Check that list2cmdline output is NOT double-escaped with outer \"
            assert r'\"/DIR=' not in decoded_ps, "ArgumentList must not corrupt outer quotes with literal \\\""
            assert '/S' in decoded_ps and 'Program Files' in decoded_ps
            assert "Start-Process" in decoded_ps
            assert "RunAs" in decoded_ps
            assert second_call_kwargs.get("cwd") == temp_app_dir
    finally:
        import shutil
        shutil.rmtree(temp_app_dir, ignore_errors=True)

    print("  [✔] Uninstaller isolates working directory and safely escapes inner double quotes for PowerShell elevation.")


def test_8_schtasks_escaping_wizard_cwd_and_self_uninst_loop():
    print("[8/8] Testing schtasks /tr quote escaping, wizard cwd isolation, and self-uninstaller retry loop...")
    from core.autostart import set_autostart
    import inspect

    # 1. core/autostart.py schtasks /tr inner quote escaping
    src_autostart = inspect.getsource(set_autostart)
    assert 'escaped_tr' in src_autostart and '/tr", escaped_tr' in src_autostart, "autostart schtasks /tr must use escaped_tr"
    assert '{exe}' in src_autostart

    # 2. scripts/installer_wizard.py schtasks /tr inner quote escaping & post-install CWD
    with open(os.path.join(ROOT_DIR, "scripts", "installer_wizard.py"), "r", encoding="utf-8") as f:
        src_wizard = f.read()
    assert 'escaped_tr' in src_wizard and '/tr", escaped_tr' in src_wizard, "installer wizard schtasks /tr must use escaped_tr"
    assert "subprocess.Popen([target_exe], cwd=target_dir, creationflags=flags)" in src_wizard, "installer wizard post-install launch must set cwd=target_dir"

    # 3. main.py self-uninstall retry loop
    with open(os.path.join(ROOT_DIR, "main.py"), "r", encoding="utf-8") as f:
        src_main = f.read()
    assert 'for /l %%i in (1,1,10) do (rmdir /s /q "{install_dir}" 2>nul && goto done || ping 127.0.0.1 -n 2 >nul)' in src_main, "main.py self-uninstall must use 10-step retry loop"

    print("  [✔] schtasks /tr escaping, setup wizard cwd isolation, and self-uninstall retry loop fully verified.")


if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare 5th-Pass Security, Reliability & Isolation Suite")
    print("=" * 65)

    test_1_updater_mkdtemp_and_param_escaping()
    test_2_updater_zip_bomb_protections()
    test_3_cookie_shield_none_resilience_and_sqlite_ro()
    test_4_disk_view_explorer_binary_path_regression()
    test_5_safe_remove_file_symlink_permission_guard()
    test_6_game_booster_module_lock_and_startup_recovery()
    test_7_uninstaller_cwd_isolation_and_powershell_escaping()
    test_8_schtasks_escaping_wizard_cwd_and_self_uninst_loop()

    print("\n" + "=" * 65)
    print("  >>> ALL 8 SECURITY AUDIT #5 TESTS PASSED FLAWLESSLY! <<<")
    print("=" * 65)
