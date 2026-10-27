"""
NovaCare System Suite - GitHub Automatic & Manual Updater
Supports two update modes:
1. Branch Tracking (Klasör/Dal Takibi - Önerilen): Checks GitHub commits on 'main'. Whenever you edit
   or upload files to the GitHub repository, it immediately detects it and updates automatically without
   requiring manual release tags.
2. Release Tracking: Tracks formal GitHub Release tags (v1.0.0, etc.).
"""
import os
import sys
import re
import json
import shutil
import zipfile
import subprocess
import requests
from dataclasses import dataclass
from typing import Optional, Callable
from core.config import CURRENT_VERSION, ConfigManager

@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    release_title: str
    changelog: str
    download_url: str
    download_size: int
    published_at: str
    is_prerelease: bool = False
    new_commit_sha: str = ""

def parse_version_tuple(v_str: str) -> tuple[int, ...]:
    cleaned = re.sub(r'^[vV]', '', v_str.strip())
    parts = re.findall(r'\d+', cleaned)
    if not parts:
        return (0, 0, 0)
    return tuple(int(p) for p in parts)

def is_newer_version(latest_str: str, current_str: str) -> bool:
    v_latest = parse_version_tuple(latest_str)
    v_curr = parse_version_tuple(current_str)
    max_len = max(len(v_latest), len(v_curr))
    v_latest_padded = v_latest + (0,) * (max_len - len(v_latest))
    v_curr_padded = v_curr + (0,) * (max_len - len(v_curr))
    return v_latest_padded > v_curr_padded

class GitHubUpdater:
    def __init__(
        self,
        repo: Optional[str] = None,
        token: Optional[str] = None,
        branch: Optional[str] = None,
        current_version: str = CURRENT_VERSION
    ):
        self.config = ConfigManager()
        self.repo = repo or self.config.get("github_repo", "GurpinarSG/NovaCare")
        self.token = token or self.config.get_secure_token()
        self.branch = branch or self.config.get("target_branch", "main")
        self.current_version = current_version

    def _get_verify(self):
        from core.utils import ensure_ssl_ca_bundle
        ca = ensure_ssl_ca_bundle()
        if ca and os.path.exists(ca):
            return ca
        return True

    def _safe_request_get(self, url: str, headers: dict, timeout: int = 12, stream: bool = False):
        verify = self._get_verify()
        try:
            return requests.get(url, headers=headers, timeout=timeout, stream=stream, verify=verify)
        except requests.exceptions.SSLError:
            # Re-ensure persistent CA bundle and retry
            from core.utils import ensure_ssl_ca_bundle
            fresh_ca = ensure_ssl_ca_bundle()
            if fresh_ca and os.path.exists(fresh_ca) and fresh_ca != verify:
                try:
                    return requests.get(url, headers=headers, timeout=timeout, stream=stream, verify=fresh_ca)
                except requests.exceptions.SSLError:
                    pass
            # Secure fallback with warning suppressed in case local cert bundle path was removed
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            return requests.get(url, headers=headers, timeout=timeout, stream=stream, verify=False)

    def _get_headers(self, accept: str = "application/vnd.github.v3+json") -> dict:
        headers = {
            "User-Agent": "NovaCare-SystemCare-Suite",
            "Accept": accept
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def verify_token(self) -> tuple[bool, str]:
        """Verifies if the configured token is valid with GitHub API."""
        if not self.token:
            return False, "Token tanımlanmadı."
        try:
            r = self._safe_request_get("https://api.github.com/user", headers=self._get_headers(), timeout=8)
            if r.status_code == 200:
                user_data = r.json()
                login = user_data.get("login", "Bilinmiyor")
                return True, login
            return False, f"Geçersiz token (HTTP {r.status_code})"
        except Exception as e:
            return False, str(e)

    def check_for_updates(self, mode: Optional[str] = None) -> UpdateInfo:
        """
        Checks for updates.
        CRITICAL: If running as a frozen executable (NovaCare.exe), ALWAYS track official Releases
        to download compiled binary packages (NovaCare_Update.zip containing NovaCare.exe).
        Raw source code zipballs only contain .py scripts and cannot update a frozen PyInstaller binary!
        """
        if getattr(sys, 'frozen', False):
            return self._check_releases()

        current_mode = mode or self.config.get("update_mode", "release")
        if current_mode == "release":
            return self._check_releases()
        else:
            return self._check_branch_commits()

    def _check_branch_commits(self) -> UpdateInfo:
        """
        Inspects the latest commit on the repository branch (e.g. 'main') for source development mode.
        """
        if getattr(sys, 'frozen', False):
            return self._check_releases()

        commits_url = f"https://api.github.com/repos/{self.repo}/commits/{self.branch}"
        local_sha = self.config.get("local_commit_sha", "")

        try:
            resp = self._safe_request_get(commits_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                remote_sha = data.get("sha", "")
                commit_info = data.get("commit", {})
                commit_msg = commit_info.get("message", "GitHub güncellemesi").strip()
                commit_date = commit_info.get("author", {}).get("date", "")[:10]
                short_sha = remote_sha[:7]

                # If local_sha is unset, initialize it with current remote sha
                if not local_sha:
                    self.config.set("local_commit_sha", remote_sha)
                    local_sha = remote_sha

                available = bool(remote_sha) and not remote_sha.startswith(local_sha) and not local_sha.startswith(remote_sha)

                download_url = f"https://api.github.com/repos/{self.repo}/zipball/{self.branch}"

                cur_display = self.config.get_display_version()
                cur_base = self.config.get_version()

                if available:
                    title = f"NovaCare Sistem Güncellemesi ({short_sha})"
                    changelog = (
                        f"NovaCare için yeni bir optimizasyon ve sürüm güncellemesi yayınlandı.\n\n"
                        f"• Güncelleme Derlemesi: {short_sha}\n"
                        f"• Yenilikler & Notlar: {commit_msg}\n"
                        f"• Yayın Tarihi: {commit_date}\n\n"
                        "Güncellemeyi yükleyerek en son performans iyileştirmelerini doğrudan sisteminize uygulayabilirsiniz."
                    )
                    ver_label = f"v{cur_base} (Derleme: {short_sha})"
                else:
                    title = "Uygulamanız Güncel"
                    changelog = f"NovaCare en son sürümündedir ({cur_display}). Sisteminiz en güncel güvenlik ve performans iyileştirmeleriyle korunmaktadır."
                    ver_label = cur_display

                return UpdateInfo(
                    available=available,
                    current_version=cur_display,
                    latest_version=ver_label,
                    release_title=title,
                    changelog=changelog,
                    download_url=download_url,
                    download_size=0,
                    published_at=commit_date,
                    new_commit_sha=remote_sha
                )
            elif resp.status_code == 404:
                # If branch not found, fallback to releases
                return self._check_releases()
            elif resp.status_code == 401:
                raise RuntimeError("Güncelleme sunucusu yetkilendirme hatası.")
            else:
                raise RuntimeError(f"Güncelleme sunucusu yanıt vermedi ({resp.status_code})")
        except requests.RequestException:
            raise RuntimeError("Güncelleme sunucusuna bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")

    def _check_releases(self) -> UpdateInfo:
        """Traditional GitHub Release tag inspector."""
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            resp = self._safe_request_get(api_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                tag_name = data.get("tag_name", "0.0.0")
                clean_version = tag_name.lstrip("vV")
                title = data.get("name") or f"NovaCare v{clean_version}"
                body = data.get("body") or "Yeni güncelleme mevcut."
                published = data.get("published_at", "")[:10]
                is_pre = data.get("prerelease", False)

                download_url = ""
                download_size = 0

                assets = data.get("assets", [])
                update_zip = None
                portable_zip = None
                other_zip = None
                exe_asset = None

                for asset in assets:
                    aname = asset.get("name", "").lower()
                    if "update" in aname and aname.endswith(".zip"):
                        update_zip = asset
                    elif "portable" in aname and aname.endswith(".zip"):
                        portable_zip = asset
                    elif aname.endswith(".zip"):
                        other_zip = asset
                    elif aname.endswith(".exe") and "setup" not in aname:
                        exe_asset = asset

                chosen_asset = update_zip or portable_zip or other_zip or exe_asset
                if chosen_asset:
                    if self.token and chosen_asset.get("url"):
                        download_url = chosen_asset.get("url")
                    else:
                        download_url = chosen_asset.get("browser_download_url") or chosen_asset.get("url")
                    download_size = chosen_asset.get("size", 0)

                if not download_url:
                    download_url = data.get("zipball_url", "")

                cur_display = self.config.get_display_version()
                cur_base = self.config.get_version()

                available = is_newer_version(clean_version, cur_base)

                return UpdateInfo(
                    available=available,
                    current_version=cur_display,
                    latest_version=f"v{clean_version}",
                    release_title=title,
                    changelog=body,
                    download_url=download_url,
                    download_size=download_size,
                    published_at=published,
                    is_prerelease=is_pre
                )
            elif resp.status_code == 404:
                return self._check_branch_commits()
            else:
                raise RuntimeError(f"Güncelleme sunucusu yanıt vermedi ({resp.status_code})")
        except requests.RequestException:
            raise RuntimeError("Güncelleme sunucusuna bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")

    def download_and_prepare_update(
        self,
        download_url: str,
        new_commit_sha: str = "",
        new_version: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Downloads update zip to temp folder, extracts it, and generates apply_update.bat.
        Returns the path to apply_update.bat ready to execute.
        """
        temp_dir = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'NovaCare_Update')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        zip_path = os.path.join(temp_dir, 'update.zip')
        extracted_dir = os.path.join(temp_dir, 'extracted')
        os.makedirs(extracted_dir, exist_ok=True)

        headers = self._get_headers()
        if "api.github.com/repos/" in download_url and "/releases/assets/" in download_url:
            headers["Accept"] = "application/octet-stream"

        resp = self._safe_request_get(download_url, headers=headers, stream=True, timeout=30)
        resp.raise_for_status()

        total_size = int(resp.headers.get('content-length', 0))
        downloaded = 0
        block_size = 65536

        with open(zip_path, 'wb') as out_f:
            for chunk in resp.iter_content(chunk_size=block_size):
                if chunk:
                    out_f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)

        # Extract zip or handle direct executable
        is_zip = zip_path.lower().endswith('.zip') and zipfile.is_zipfile(zip_path)
        if is_zip:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extracted_dir)

            # Handle zipball inner root directory
            source_dir = extracted_dir
            items = os.listdir(extracted_dir)
            if len(items) == 1 and os.path.isdir(os.path.join(extracted_dir, items[0])):
                inner_dir = os.path.join(extracted_dir, items[0])
                if any(os.path.exists(os.path.join(inner_dir, f)) for f in ('main.py', 'core', 'ui', 'VERSION', 'NovaCare.exe')):
                    source_dir = inner_dir
        else:
            # Standalone exe payload
            source_dir = temp_dir
            if os.path.exists(zip_path):
                dest_direct_exe = os.path.join(temp_dir, "NovaCare.exe")
                shutil.copy2(zip_path, dest_direct_exe)

        # 1. Determine target version (DO NOT prematurely save to settings.json before copy succeeds!)
        clean_ver_num = ""
        v_file = os.path.join(source_dir, "VERSION")
        if os.path.exists(v_file):
            try:
                with open(v_file, "r", encoding="utf-8") as vf:
                    from core.config import parse_version_content
                    extracted_ver, _ = parse_version_content(vf.read())
                    if extracted_ver:
                        clean_ver_num = extracted_ver
            except Exception:
                pass
        elif new_version:
            from core.config import parse_version_content
            clean_nv, _ = parse_version_content(new_version)
            clean_ver_num = clean_nv

        if not clean_ver_num:
            clean_ver_num = self.config.get_version()

        current_pid = os.getpid()

        # Determine app paths
        if getattr(sys, 'frozen', False):
            app_root = os.path.dirname(sys.executable)
            launcher_target = os.path.join(app_root, "NovaCare.exe")
        else:
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            launcher_target = os.path.join(app_root, "NovaCare.bat")
        main_py = os.path.join(app_root, "main.py")

        # =====================================================================
        # 2. Generate apply_update.ps1 (Ultra-robust PowerShell script)
        # =====================================================================
        ps1_path = os.path.join(temp_dir, "apply_update.ps1")
        with open(ps1_path, "w", encoding="utf-8") as pf:
            pf.write(f"""# NovaCare System Suite - Robust In-Place PowerShell Updater
$ErrorActionPreference = 'SilentlyContinue'
$sourceDir = '{source_dir}'
$appRoot = '{app_root}'
$launcher = '{launcher_target}'
$parentPid = {current_pid}
$version = '{clean_ver_num}'
$commitSha = '{new_commit_sha}'

# 1. Terminate current NovaCare process and any tree processes
if ($parentPid -gt 0) {{
    Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue
}}
Get-Process -Name 'NovaCare' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Wait up to 15 seconds for complete process exit & file release
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
while ($stopwatch.Elapsed.TotalSeconds -lt 15) {{
    $running = Get-Process -Name 'NovaCare' -ErrorAction SilentlyContinue
    if (-not $running) {{ break }}
    Start-Sleep -Milliseconds 600
}}
Start-Sleep -Milliseconds 800

# 2. Atomic executable replacement
$srcExe = Join-Path $sourceDir 'NovaCare.exe'
$destExe = Join-Path $appRoot 'NovaCare.exe'
$oldExe = Join-Path $appRoot 'NovaCare.exe.old'

if (Test-Path $srcExe) {{
    if (Test-Path $oldExe) {{ Remove-Item $oldExe -Force -ErrorAction SilentlyContinue }}
    if (Test-Path $destExe) {{
        # In Windows NT, renaming an in-use / closing executable always succeeds
        Move-Item -Path $destExe -Destination $oldExe -Force -ErrorAction SilentlyContinue
    }}

    $copied = $false
    for ($attempt = 1; $attempt -le 10; $attempt++) {{
        Copy-Item -Path $srcExe -Destination $destExe -Force -ErrorAction SilentlyContinue
        if ((Test-Path $destExe) -and ((Get-Item $destExe).Length -gt 1000000)) {{
            $copied = $true
            break
        }}
        Start-Sleep -Milliseconds 800
    }}

    if (-not $copied) {{
        # Rollback original executable if copy failed
        if (Test-Path $oldExe) {{
            Move-Item -Path $oldExe -Destination $destExe -Force -ErrorAction SilentlyContinue
        }}
        Start-Process $launcher
        exit 1
    }}
    if (Test-Path $oldExe) {{ Remove-Item $oldExe -Force -ErrorAction SilentlyContinue }}
}}

# 3. Synchronize all updated assets and files
Get-ChildItem -Path $sourceDir | ForEach-Object {{
    if ($_.Name -ne 'NovaCare.exe') {{
        Copy-Item -Path $_.FullName -Destination $appRoot -Recurse -Force -ErrorAction SilentlyContinue
    }}
}}

# 4. Synchronize Registry DisplayVersion
if ($version) {{
    Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare' -Name 'DisplayVersion' -Value $version -ErrorAction SilentlyContinue
    Set-ItemProperty -Path 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare' -Name 'DisplayVersion' -Value $version -ErrorAction SilentlyContinue
}}

# 5. Persist new version to settings.json ONLY after copy has succeeded
$cfgPath = Join-Path $env:LOCALAPPDATA 'NovaCare\\settings.json'
if (Test-Path $cfgPath) {{
    try {{
        $json = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($version) {{ $json.version = $version }}
        if ($commitSha) {{ $json.local_commit_sha = $commitSha }}
        $json | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding UTF8
    }} catch {{}}
}}

# 6. Relaunch updated NovaCare
Start-Sleep -Milliseconds 500
Start-Process $launcher
exit 0
""")

        # =====================================================================
        # 3. Generate apply_update.bat (BOM-encoded runner & fail-safe fallback)
        # =====================================================================
        batch_path = os.path.join(temp_dir, "apply_update.bat")
        with open(batch_path, "w", encoding="utf-8-sig") as bf:
            bf.write(f"""@echo off
chcp 65001 > nul
title NovaCare Guncelleme Yoneticisi
echo ========================================================
echo   NovaCare System Care Suite - Guncelleme Uygulaniyor
echo ========================================================
echo NovaCare yeni surum dosyalari yukleniyor, lutfen bekleyin...

:: PyInstaller onefile child-process validation variables strip
set _PYI_PARENT_PID=
set _MEIPASS2=
set _PYI_APPLICATION_HOME_DIR=
set _PYI_ARCHIVE_FILE=
set _PYI_SPLASH_IPC=

:: 1. Try PowerShell Updater engine first (100% reliable Unicode & atomic rename handling)
if exist "%~dp0apply_update.ps1" (
    powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0apply_update.ps1"
    if not errorlevel 1 goto cleanup_batch
)

:: 2. Fail-safe native CMD fallback in case PowerShell is disabled or restricted
taskkill /f /t /pid {current_pid} > nul 2>&1
taskkill /f /t /im NovaCare.exe > nul 2>&1
timeout /t 1 /nobreak > nul

for /l %%i in (1,1,15) do (
    tasklist /fi "imagename eq NovaCare.exe" 2>nul | find /i "NovaCare.exe" >nul
    if errorlevel 1 (
        goto ready_to_copy
    )
    taskkill /f /t /im NovaCare.exe > nul 2>&1
    timeout /t 1 /nobreak > nul
)

:ready_to_copy
timeout /t 1 /nobreak > nul

:: Atomic replacement via move/rename trick
if exist "{source_dir}\\NovaCare.exe" (
    if exist "{app_root}\\NovaCare.exe.old" del /f /q "{app_root}\\NovaCare.exe.old" > nul 2>&1
    move /y "{app_root}\\NovaCare.exe" "{app_root}\\NovaCare.exe.old" > nul 2>&1
    for /l %%k in (1,1,10) do (
        copy /y "{source_dir}\\NovaCare.exe" "{app_root}\\NovaCare.exe" > nul 2>&1
        if exist "{app_root}\\NovaCare.exe" goto exe_copied
        timeout /t 1 /nobreak > nul
    )
    :: Rollback if copy failed
    if exist "{app_root}\\NovaCare.exe.old" move /y "{app_root}\\NovaCare.exe.old" "{app_root}\\NovaCare.exe" > nul 2>&1
    goto launch_fallback
)

:exe_copied
if exist "{app_root}\\NovaCare.exe.old" del /f /q "{app_root}\\NovaCare.exe.old" > nul 2>&1

:: Copy other assets
xcopy /s /e /y /i /q "{source_dir}\\*" "{app_root}\\" > nul 2>&1

:: Update registry DisplayVersion
reg add "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare" /v "DisplayVersion" /d "{clean_ver_num}" /f > nul 2>&1
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare" /v "DisplayVersion" /d "{clean_ver_num}" /f > nul 2>&1

:launch_fallback
echo Guncelleme islemi tamamlandi. NovaCare yeniden baslatiliyor...
timeout /t 1 /nobreak > nul

set _PYI_PARENT_PID=
set _MEIPASS2=
set _PYI_APPLICATION_HOME_DIR=
set _PYI_ARCHIVE_FILE=
set _PYI_SPLASH_IPC=

if exist "{launcher_target}" (
    start "" "{launcher_target}"
) else (
    start "" pythonw "{main_py}"
)

:cleanup_batch
del /f /q "%~f0" > nul 2>&1
exit
""")

        return batch_path

    def launch_updater_and_exit(self, batch_path: str):
        """Spawns the updater batch script in background and exits current application cleanly."""
        clean_env = os.environ.copy()
        for k in list(clean_env.keys()):
            if k.startswith('_PYI') or k.startswith('_MEI'):
                clean_env.pop(k, None)

        flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        subprocess.Popen(["cmd.exe", "/c", batch_path], env=clean_env, creationflags=flags)

        # Cleanly close all Qt windows to release file handles immediately
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.closeAllWindows()
                app.quit()
        except Exception:
            pass

        sys.exit(0)
