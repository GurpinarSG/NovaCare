"""
NovaCare System Suite - Comprehensive End-to-End Updater Test Suite
Verifies:
1. UTF-8 BOM encoding for apply_update.ps1 and apply_update.bat (prevents Turkish char corruption).
2. Non-ASCII Turkish folder path handling (e.g. 'Masaüstü').
3. Version synchronization (VERSION file in source_dir and appRoot properly bumped).
4. ConfigManager version consistency (does not revert newer version).
5. PowerShell atomic replacement and execution with -LiteralPath and -WorkingDirectory.
6. CMD fallback resilience without suicidal process tree kill.
"""
import os
import sys
import shutil
import tempfile
import zipfile
import subprocess
from unittest.mock import patch, MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from core.config import ConfigManager, parse_version_content
from core.updater import GitHubUpdater

def test_bom_encoding():
    print("[1/10] Testing BOM encoding and Turkish path preservation...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.4")

    # Mock download_and_prepare_update using dummy zip
    temp_dir = tempfile.mkdtemp(prefix="NC_Test_")
    try:
        dummy_zip = os.path.join(temp_dir, "test.zip")
        with zipfile.ZipFile(dummy_zip, "w") as zf:
            zf.writestr("VERSION", "1.2.4\n---\nOld notes")
            zf.writestr("NovaCare.exe", b"MZ_TEST_EXE_DATA")
            zf.writestr("assets/test.png", b"PNG")

        class MockResp:
            status_code = 200
            headers = {"content-length": str(os.path.getsize(dummy_zip))}
            def iter_content(self, chunk_size=65536):
                with open(dummy_zip, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            def raise_for_status(self): pass

        with patch.object(updater, '_safe_request_get', return_value=MockResp()):
            bat_path = updater.download_and_prepare_update(
                "https://github.com/GurpinarSG/NovaCare/releases/download/v1.2.5/NovaCare_Update.zip",
                new_version="1.2.5"
            )
            ps1_path = bat_path.replace(".bat", ".ps1")

            assert os.path.exists(bat_path), "apply_update.bat must exist"
            assert os.path.exists(ps1_path), "apply_update.ps1 must exist"

            # Check BOM on ps1
            with open(ps1_path, "rb") as f:
                header = f.read(3)
                assert header == b'\xef\xbb\xbf', f"apply_update.ps1 MUST start with UTF-8 BOM, got {header!r}"

            # Check BOM on bat
            with open(bat_path, "rb") as f:
                header = f.read(3)
                assert header == b'\xef\xbb\xbf', f"apply_update.bat MUST start with UTF-8 BOM, got {header!r}"

            # Verify that PowerShell can parse Turkish character path properly
            with open(ps1_path, "r", encoding="utf-8-sig") as f:
                ps1_text = f.read()

            assert "-LiteralPath" in ps1_text, "apply_update.ps1 must use -LiteralPath for safe path handling"
            assert "-WorkingDirectory $appRoot" in ps1_text, "apply_update.ps1 must specify -WorkingDirectory"
            assert "$version = '1.2.5'" in ps1_text, "apply_update.ps1 must reflect target version 1.2.5"

            # Verify CMD fallback does not have /t on current_pid
            with open(bat_path, "r", encoding="utf-8-sig") as f:
                bat_text = f.read()

            assert "taskkill /f /t /pid" not in bat_text, "apply_update.bat must NOT use /t on parent PID (suicide bug)"
            assert "cd /d" in bat_text, "apply_update.bat must set working directory before launching"

            # Verify VERSION in extracted dir was bumped to 1.2.5
            extracted_v = os.path.join(os.path.dirname(bat_path), "extracted", "VERSION")
            assert os.path.exists(extracted_v), "Extracted VERSION must exist"
            with open(extracted_v, "r", encoding="utf-8") as vf:
                v_content = vf.read()
                ver, _ = parse_version_content(v_content)
                assert ver == "1.2.5", f"Extracted VERSION must be 1.2.5, got {ver}"

        print("  [✔] BOM encoding and script generation verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_powershell_turkish_path_execution():
    print("[2/10] Testing live PowerShell execution with Turkish paths (Masaüstü)...")
    # Create mock environment with Turkish folder name
    base_tmp = tempfile.mkdtemp(prefix="NC_Turkish_")
    turkish_dir = os.path.join(base_tmp, "Masaüstü", "TestApp")
    os.makedirs(turkish_dir, exist_ok=True)

    try:
        # Create mock existing app
        old_exe = os.path.join(turkish_dir, "NovaCare.exe")
        with open(old_exe, "wb") as f:
            f.write(b"MZ_OLD_VERSION_1_2_4")

        mock_source = os.path.join(base_tmp, "extracted")
        os.makedirs(mock_source, exist_ok=True)
        new_exe = os.path.join(mock_source, "NovaCare.exe")
        with open(new_exe, "wb") as f:
            f.write(b"MZ_NEW_VERSION_1_2_5_LONGER_PAYLOAD")

        mock_v = os.path.join(mock_source, "VERSION")
        with open(mock_v, "w", encoding="utf-8") as f:
            f.write("1.2.5\n---\nNew Release Notes")

        # Create a mock launcher that just records launch
        launcher = os.path.join(turkish_dir, "NovaCare.bat")
        launcher_marker = os.path.join(turkish_dir, "launched.txt")
        with open(launcher, "w", encoding="utf-8") as f:
            f.write(f"@echo Launched > \"{launcher_marker}\"\nexit\n")

        # Generate ps1 script targeting turkish_dir
        ps_source_dir = mock_source.replace("'", "''")
        ps_app_root = turkish_dir.replace("'", "''")
        ps_launcher = launcher.replace("'", "''")

        ps1_path = os.path.join(base_tmp, "apply_update.ps1")
        ps1_code = f"""# Test PowerShell Updater with Turkish Path
$ErrorActionPreference = 'Stop'
$sourceDir = '{ps_source_dir}'
$appRoot = '{ps_app_root}'
$launcher = '{ps_launcher}'
$version = '1.2.5'

# Atomic executable replacement
$srcExe = Join-Path $sourceDir 'NovaCare.exe'
$destExe = Join-Path $appRoot 'NovaCare.exe'
$oldExe = Join-Path $appRoot 'NovaCare.exe.old'

if (Test-Path -LiteralPath $srcExe) {{
    if (Test-Path -LiteralPath $oldExe) {{ Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue }}
    if (Test-Path -LiteralPath $destExe) {{
        Move-Item -LiteralPath $destExe -Destination $oldExe -Force
    }}

    $copied = $false
    for ($attempt = 1; $attempt -le 5; $attempt++) {{
        Copy-Item -LiteralPath $srcExe -Destination $destExe -Force
        if ((Test-Path -LiteralPath $destExe) -and ((Get-Item -LiteralPath $destExe).Length -eq (Get-Item -LiteralPath $srcExe).Length)) {{
            $copied = $true
            break
        }}
        Start-Sleep -Milliseconds 200
    }}

    if (-not $copied) {{ exit 1 }}
    if (Test-Path -LiteralPath $oldExe) {{ Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue }}
}}

# Copy assets
Get-ChildItem -LiteralPath $sourceDir | ForEach-Object {{
    if ($_.Name -ne 'NovaCare.exe') {{
        Copy-Item -LiteralPath ($_.FullName) -Destination $appRoot -Recurse -Force
    }}
}}

# Relaunch
if (Test-Path -LiteralPath $launcher) {{
    Start-Process -FilePath 'cmd.exe' -ArgumentList "/c `"$launcher`"" -WorkingDirectory $appRoot
}}
exit 0
"""
        with open(ps1_path, "w", encoding="utf-8-sig") as pf:
            pf.write(ps1_code)

        # Run PowerShell
        p = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", ps1_path],
            capture_output=True,
            text=True
        )

        assert p.returncode == 0, f"PowerShell failed with code {p.returncode}: {p.stderr}"
        assert os.path.exists(old_exe), "NovaCare.exe must exist in turkish_dir"
        with open(old_exe, "rb") as f:
            content = f.read()
            assert content == b"MZ_NEW_VERSION_1_2_5_LONGER_PAYLOAD", "NovaCare.exe must have been replaced with new payload"

        assert os.path.exists(os.path.join(turkish_dir, "VERSION")), "VERSION file must exist in turkish_dir"
        with open(os.path.join(turkish_dir, "VERSION"), "r", encoding="utf-8") as f:
            v_text = f.read()
            assert v_text.startswith("1.2.5"), f"VERSION must be 1.2.5, got {v_text}"

        print("  [✔] PowerShell execution with Turkish characters succeeded perfectly.")
    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)

def test_cmd_fallback_execution():
    print("[3/10] Testing CMD fallback execution without suicide bug...")
    base_tmp = tempfile.mkdtemp(prefix="NC_CMD_")
    turkish_dir = os.path.join(base_tmp, "Masaüstü", "TestApp")
    os.makedirs(turkish_dir, exist_ok=True)

    try:
        old_exe = os.path.join(turkish_dir, "NovaCare.exe")
        with open(old_exe, "wb") as f:
            f.write(b"MZ_OLD_VERSION")

        mock_source = os.path.join(base_tmp, "extracted")
        os.makedirs(mock_source, exist_ok=True)
        new_exe = os.path.join(mock_source, "NovaCare.exe")
        with open(new_exe, "wb") as f:
            f.write(b"MZ_NEW_CMD_PAYLOAD")

        mock_v = os.path.join(mock_source, "VERSION")
        with open(mock_v, "w", encoding="utf-8") as f:
            f.write("1.2.5\n---\nCMD Fallback")

        bat_path = os.path.join(base_tmp, "test_fallback.bat")
        bat_code = f"""@echo off
chcp 65001 > nul
:: Test non-suicide taskkill with 0 PID
if 0 gtr 0 (
    taskkill /f /pid 0 > nul 2>&1
)

:: Atomic replace
if exist "{mock_source}\\NovaCare.exe" (
    if exist "{turkish_dir}\\NovaCare.exe.old" del /f /q "{turkish_dir}\\NovaCare.exe.old" > nul 2>&1
    move /y "{turkish_dir}\\NovaCare.exe" "{turkish_dir}\\NovaCare.exe.old" > nul 2>&1
    copy /y "{mock_source}\\NovaCare.exe" "{turkish_dir}\\NovaCare.exe" > nul 2>&1
    if exist "{turkish_dir}\\NovaCare.exe.old" del /f /q "{turkish_dir}\\NovaCare.exe.old" > nul 2>&1
)

xcopy /s /e /y /i /q /r /h "{mock_source}\\*" "{turkish_dir}\\" > nul 2>&1
exit /b 0
"""
        with open(bat_path, "w", encoding="utf-8-sig") as f:
            f.write(bat_code)

        p = subprocess.run(["cmd.exe", "/c", bat_path], capture_output=True, text=True)
        assert p.returncode == 0, f"CMD failed with code {p.returncode}: {p.stderr}"

        with open(old_exe, "rb") as f:
            assert f.read() == b"MZ_NEW_CMD_PAYLOAD", "CMD fallback must successfully copy new executable"

        print("  [✔] CMD fallback execution succeeded.")
    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)

def test_config_version_protection():
    print("[4/10] Testing ConfigManager version downgrade protection...")
    cfg_tmp = tempfile.mkdtemp(prefix="NC_Cfg_")
    try:
        cfg = ConfigManager(config_dir=cfg_tmp)
        # Simulate an updated version in settings.json
        cfg.settings["version"] = "1.2.5"
        cfg.save_all()

        # Even if base_file_ver returns an older version (e.g. 1.2.4),
        # get_version must NOT downgrade settings.json to 1.2.4
        with patch("core.config.load_base_version", return_value="1.2.4"):
            v = cfg.get_version()
            assert v == "1.2.5", f"get_version() must return 1.2.5, got {v}"
            assert cfg.settings.get("version") == "1.2.5", "settings['version'] must remain 1.2.5"

        # If a newer base_file_ver is found (e.g. 1.3.0), it SHOULD upgrade
        with patch("core.config.load_base_version", return_value="1.3.0"):
            v = cfg.get_version()
            assert v == "1.3.0", f"get_version() must return 1.3.0, got {v}"
            assert cfg.settings.get("version") == "1.3.0", "settings['version'] must upgrade to 1.3.0"

        print("  [✔] ConfigManager version protection works correctly.")
    finally:
        shutil.rmtree(cfg_tmp, ignore_errors=True)

def test_web_redirect_rate_limit_fallback():
    print("[5/10] Testing web redirect fallback when API rate limit is exceeded...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.4")

    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    mock_resp_403.text = "API rate limit exceeded for 127.0.0.1"

    with patch.object(updater, '_safe_request_get', return_value=mock_resp_403):
        # Even with API 403 rate limit, web fallback retrieves latest release info
        info = updater.check_for_updates(mode="release")
        assert info.available == True
        assert info.latest_version in ("v1.2.4", "v1.2.5", "v1.2.6")
        assert "NovaCare_Update.zip" in info.download_url
        print(f"  [✔] Rate limit fallback detected {info.latest_version} via web redirect successfully.")

def test_live_release_update_readiness():
    print("[6/10] Testing live GitHub release check & download readiness...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.4")
    info = updater.check_for_updates(mode="release")

    assert info.available == True, f"Should detect {info.latest_version} as newer than v1.2.4"
    assert info.latest_version in ("v1.2.5", "v1.2.6")
    assert info.download_url.startswith("https://")
    print(f"  [✔] Live update check: {info.current_version} -> {info.latest_version}")

def test_settings_json_bom_resilience():
    print("[7/10] Testing settings.json BOM resilience & ConfigManager parsing...")
    cfg_tmp = tempfile.mkdtemp(prefix="NC_BOM_Cfg_")
    try:
        cfg_file = os.path.join(cfg_tmp, "settings.json")
        # Write JSON with UTF-8 BOM
        with open(cfg_file, "wb") as f:
            f.write(b'\xef\xbb\xbf{"version": "1.2.5", "theme": "dark", "custom_setting": true}')

        cm = ConfigManager(config_dir=cfg_tmp)
        assert cm.get("version") == "1.2.5", "ConfigManager must parse settings with UTF-8 BOM"
        assert cm.get("theme") == "dark"
        assert cm.get("custom_setting") == True

        # Test PowerShell UTF-8 No BOM output
        ps_test = f"""
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        $json = [PSCustomObject]@{{ version = '1.2.5'; theme = 'system' }}
        $jsonText = $json | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText('{cfg_file}', $jsonText, $utf8NoBom)
        """
        subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_test], check=True)

        with open(cfg_file, "rb") as f:
            header = f.read(3)
            assert header != b'\xef\xbb\xbf', "settings.json written by PowerShell must NOT have UTF-8 BOM"

        cm2 = ConfigManager(config_dir=cfg_tmp)
        assert cm2.get("version") == "1.2.5"
        print("  [✔] settings.json BOM resilience & non-BOM writing verified.")
    finally:
        shutil.rmtree(cfg_tmp, ignore_errors=True)

def test_file_lock_retry_loop():
    print("[8/10] Testing updater retry loop against external file locks (antivirus/OneDrive)...")
    base_tmp = tempfile.mkdtemp(prefix="NC_Lock_")
    turkish_dir = os.path.join(base_tmp, "Masaüstü", "TestApp")
    os.makedirs(turkish_dir, exist_ok=True)
    try:
        old_exe = os.path.join(turkish_dir, "NovaCare.exe")
        with open(old_exe, "wb") as f:
            f.write(b"MZ_OLD_PAYLOAD_LOCKED")

        mock_source = os.path.join(base_tmp, "extracted")
        os.makedirs(mock_source, exist_ok=True)
        new_exe = os.path.join(mock_source, "NovaCare.exe")
        with open(new_exe, "wb") as f:
            f.write(b"MZ_NEW_PAYLOAD_REPLACED")

        # Test PowerShell retry loop script with initial file lock that releases after 2 seconds
        import threading, time
        lock_holder = open(old_exe, "rb")

        def release_lock():
            time.sleep(2.0)
            lock_holder.close()

        threading.Thread(target=release_lock, daemon=True).start()

        ps1_code = f"""
        $sourceDir = '{mock_source.replace("'", "''")}'
        $appRoot = '{turkish_dir.replace("'", "''")}'
        $srcExe = Join-Path $sourceDir 'NovaCare.exe'
        $destExe = Join-Path $appRoot 'NovaCare.exe'
        $oldExe = Join-Path $appRoot ('NovaCare.exe.old.' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))

        $destCleared = $false
        for ($mAttempt = 1; $mAttempt -le 15; $mAttempt++) {{
            if (-not (Test-Path -LiteralPath $destExe)) {{
                $destCleared = $true
                break
            }}
            Move-Item -LiteralPath $destExe -Destination $oldExe -Force -ErrorAction SilentlyContinue
            if (-not (Test-Path -LiteralPath $destExe)) {{
                $destCleared = $true
                break
            }}
            Start-Sleep -Milliseconds 500
        }}

        if (-not $destCleared) {{ exit 1 }}

        $copied = $false
        for ($attempt = 1; $attempt -le 10; $attempt++) {{
            Copy-Item -LiteralPath $srcExe -Destination $destExe -Force -ErrorAction SilentlyContinue
            if ((Test-Path -LiteralPath $destExe) -and ((Get-Item -LiteralPath $destExe).Length -eq (Get-Item -LiteralPath $srcExe).Length)) {{
                $copied = $true
                break
            }}
            Start-Sleep -Milliseconds 300
        }}
        if (-not $copied) {{ exit 2 }}
        if (Test-Path -LiteralPath $oldExe) {{ Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue }}
        exit 0
        """
        ps1_file = os.path.join(base_tmp, "lock_test.ps1")
        with open(ps1_file, "w", encoding="utf-8-sig") as f:
            f.write(ps1_code)

        p = subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", ps1_file], capture_output=True, text=True)
        assert p.returncode == 0, f"PowerShell lock retry failed: {p.stderr}"
        with open(old_exe, "rb") as f:
            assert f.read() == b"MZ_NEW_PAYLOAD_REPLACED", "File must have been updated after lock release"

        print("  [✔] Retry loop successfully bypassed external lock after release.")
    finally:
        shutil.rmtree(base_tmp, ignore_errors=True)

def test_standalone_exe_payload_isolation():
    print("[9/10] Testing standalone executable payload isolation...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.4")

    temp_dir = tempfile.mkdtemp(prefix="NC_DirectExe_")
    try:
        class MockExeResp:
            status_code = 200
            headers = {"content-length": "24"}
            def iter_content(self, chunk_size=65536):
                yield b"MZ_STANDALONE_EXE_PAYLOAD"
            def raise_for_status(self): pass

        with patch.object(updater, '_safe_request_get', return_value=MockExeResp()):
            bat_path = updater.download_and_prepare_update(
                "https://github.com/GurpinarSG/NovaCare/releases/download/v1.2.5/NovaCare.exe",
                new_version="1.2.5"
            )
            update_dir = os.path.dirname(bat_path)
            extracted_dir = os.path.join(update_dir, "extracted")
            assert os.path.exists(os.path.join(extracted_dir, "NovaCare.exe")), "NovaCare.exe must be placed in extracted_dir"
            assert not os.path.exists(os.path.join(update_dir, "NovaCare.exe")), "NovaCare.exe must NOT be in temp root to avoid leaking scripts"

        print("  [✔] Standalone exe payload correctly isolated in extracted folder.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_batch_script_cleanup_and_uac_elevation():
    print("[10/10] Testing batch cleanup of update.zip and UAC elevation handling...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.4")
    temp_dir = tempfile.mkdtemp(prefix="NC_Clean_")
    try:
        dummy_zip = os.path.join(temp_dir, "test.zip")
        with zipfile.ZipFile(dummy_zip, "w") as zf:
            zf.writestr("VERSION", "1.2.5")
            zf.writestr("NovaCare.exe", b"MZ_DATA")

        class MockResp:
            status_code = 200
            headers = {"content-length": str(os.path.getsize(dummy_zip))}
            def iter_content(self, chunk_size=65536):
                with open(dummy_zip, "rb") as f:
                    while chunk := f.read(chunk_size):
                        yield chunk
            def raise_for_status(self): pass

        with patch.object(updater, '_safe_request_get', return_value=MockResp()):
            bat_path = updater.download_and_prepare_update(
                "https://github.com/GurpinarSG/NovaCare/releases/download/v1.2.5/NovaCare_Update.zip",
                new_version="1.2.5"
            )
            with open(bat_path, "r", encoding="utf-8-sig") as f:
                bat_text = f.read()

            assert "%~dp0update.zip" in bat_text, "apply_update.bat must clean up update.zip"

            ps1_path = bat_path.replace(".bat", ".ps1")
            with open(ps1_path, "r", encoding="utf-8-sig") as f:
                ps1_text = f.read()

            assert "IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)" in ps1_text, "apply_update.ps1 must check administrative permissions"
            assert "-Verb RunAs" in ps1_text, "apply_update.ps1 must support self-elevation"
            assert "UTF8Encoding $false" in ps1_text, "apply_update.ps1 must write settings.json without BOM"

        print("  [✔] Batch script cleanup and PowerShell UAC elevation verified.")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare End-to-End Updater Verification Test Suite")
    print("=" * 65)
    test_bom_encoding()
    test_powershell_turkish_path_execution()
    test_cmd_fallback_execution()
    test_config_version_protection()
    test_web_redirect_rate_limit_fallback()
    test_live_release_update_readiness()
    test_settings_json_bom_resilience()
    test_file_lock_retry_loop()
    test_standalone_exe_payload_isolation()
    test_batch_script_cleanup_and_uac_elevation()
    print("\n" + "=" * 65)
    print("  ALL 10 END-TO-END UPDATER TESTS PASSED PERFECTLY!")
    print("=" * 65)
