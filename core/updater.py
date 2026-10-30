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
import shutil
import zipfile
import subprocess
import ctypes
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
    sha256: str = ""
    sha256sums_url: str = ""

def parse_version_tuple(v_str: str) -> tuple[int, ...]:
    cleaned = re.sub(r'^[vV]', '', str(v_str).strip())
    # Match the leading version number segment like "1.2.4"
    m = re.match(r'^(\d+(?:\.\d+)*)', cleaned)
    if m:
        return tuple(int(p) for p in m.group(1).split('.'))
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
        # In a public repository, updates are completely unauthenticated by default.
        # Token is only used if explicitly provided or configured locally for private forks/dev.
        self.token = token if token is not None else self.config.get_secure_token()
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
            # Re-ensure persistent CA bundle and retry strictly with verified CA
            from core.utils import ensure_ssl_ca_bundle
            fresh_ca = ensure_ssl_ca_bundle()
            if fresh_ca and os.path.exists(fresh_ca) and fresh_ca != verify:
                return requests.get(url, headers=headers, timeout=timeout, stream=stream, verify=fresh_ca)
            raise

    def _get_headers(self, accept: str = "application/vnd.github.v3+json", include_auth: bool = True) -> dict:
        headers = {
            "User-Agent": "NovaCare-SystemCare-Suite",
            "Accept": accept
        }
        if include_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def verify_token(self) -> tuple[bool, str]:
        """Verifies if the configured token is valid with GitHub API."""
        if not self.token:
            return True, "Genel Erişim (Token gerekmez)"
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
            return self._check_releases(allow_fallback=False)

        current_mode = mode or self.config.get("update_mode", "release")
        if current_mode == "release":
            return self._check_releases(allow_fallback=True)
        else:
            return self._check_branch_commits(allow_fallback=True)

    def _check_branch_commits(self, allow_fallback: bool = True) -> UpdateInfo:
        """
        Inspects the latest commit on the repository branch (e.g. 'main') for source development mode.
        """
        if getattr(sys, 'frozen', False):
            return self._check_releases(allow_fallback=False)

        commits_url = f"https://api.github.com/repos/{self.repo}/commits/{self.branch}"
        local_sha = self.config.get("local_commit_sha", "")

        try:
            resp = self._safe_request_get(commits_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 401 and self.token:
                # If an invalid/expired token was present, retry unauthenticated for public repos
                resp = self._safe_request_get(commits_url, headers=self._get_headers(include_auth=False), timeout=10)

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

                download_url = f"https://github.com/{self.repo}/archive/refs/heads/{self.branch}.zip"

                cur_display = f"v{self.current_version}" if self.current_version else self.config.get_display_version()
                cur_base = self.current_version or self.config.get_version()

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
                # If branch not found, fallback to releases only if allowed
                if allow_fallback:
                    return self._check_releases(allow_fallback=False)
                raise RuntimeError(f"GitHub üzerinde '{self.repo}' deposunun '{self.branch}' dalı bulunamadı (404).")
            elif resp.status_code == 403 and "rate limit" in resp.text.lower():
                raise RuntimeError("GitHub API istek sınırı aşıldı. Lütfen daha sonra tekrar deneyin.")
            elif resp.status_code == 401:
                raise RuntimeError("Güncelleme sunucusu yetkilendirme hatası.")
            else:
                raise RuntimeError(f"Güncelleme sunucusu yanıt vermedi ({resp.status_code})")
        except requests.RequestException:
            raise RuntimeError("Güncelleme sunucusuna bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")

    def _check_releases(self, allow_fallback: bool = True) -> UpdateInfo:
        """Traditional GitHub Release tag inspector."""
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            resp = self._safe_request_get(api_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 401 and self.token:
                # If an invalid/expired token was present, retry unauthenticated for public repos
                resp = self._safe_request_get(api_url, headers=self._get_headers(include_auth=False), timeout=10)

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
                sha256sums_url = ""

                for asset in assets:
                    aname = asset.get("name", "").lower()
                    if aname == "sha256sums.txt":
                        sha256sums_url = asset.get("browser_download_url") or asset.get("url") or ""
                    elif "update" in aname and aname.endswith(".zip"):
                        update_zip = asset
                    elif "portable" in aname and aname.endswith(".zip"):
                        portable_zip = asset
                    elif aname.endswith(".zip"):
                        other_zip = asset
                    elif aname.endswith(".exe") and "setup" not in aname:
                        exe_asset = asset

                chosen_asset = update_zip or portable_zip or other_zip or exe_asset
                if chosen_asset:
                    # In a public repository, browser_download_url is CDN-cached, unauthenticated,
                    # and does not consume API rate limits. Fall back to asset API url only if missing.
                    download_url = chosen_asset.get("browser_download_url") or chosen_asset.get("url") or ""
                    download_size = chosen_asset.get("size", 0)

                if not download_url:
                    # Fallback to direct public CDN archive URL (bypasses API rate limit)
                    download_url = f"https://github.com/{self.repo}/archive/refs/tags/{tag_name}.zip" if tag_name else f"https://github.com/{self.repo}/archive/refs/heads/{self.branch}.zip"

                cur_display = f"v{self.current_version}" if self.current_version else self.config.get_display_version()
                cur_base = self.current_version or self.config.get_version()

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
                    is_prerelease=is_pre,
                    sha256sums_url=sha256sums_url
                )
            elif resp.status_code == 404:
                if allow_fallback and not getattr(sys, 'frozen', False):
                    return self._check_branch_commits(allow_fallback=False)
                raise RuntimeError(f"GitHub üzerinde '{self.repo}' için yayınlanmış bir sürüm (Release) bulunamadı (404).")
            elif resp.status_code == 403 and "rate limit" in resp.text.lower():
                # Attempt public web redirect fallback which does not consume API rate limits
                try:
                    web_url = f"https://github.com/{self.repo}/releases/latest"
                    head_resp = requests.get(web_url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=False, timeout=8)
                    loc = head_resp.headers.get("Location", "")
                    if loc and "/releases/tag/" in loc:
                        web_tag = loc.split("/releases/tag/")[-1].strip()
                        clean_version = web_tag.lstrip("vV")
                        cur_display = f"v{self.current_version}" if self.current_version else self.config.get_display_version()
                        cur_base = self.current_version or self.config.get_version()
                        available = is_newer_version(clean_version, cur_base)
                        download_url = f"https://github.com/{self.repo}/releases/download/{web_tag}/NovaCare_Update.zip"
                        return UpdateInfo(
                            available=available,
                            current_version=cur_display,
                            latest_version=f"v{clean_version}",
                            release_title=f"NovaCare System Care Suite v{clean_version}",
                            changelog="NovaCare için yeni bir optimizasyon ve sürüm güncellemesi yayınlandı.",
                            download_url=download_url,
                            download_size=0,
                            published_at=""
                        )
                except Exception:
                    pass
                raise RuntimeError("GitHub API istek sınırı aşıldı. Lütfen daha sonra tekrar deneyin.")
            elif resp.status_code == 401:
                raise RuntimeError("Güncelleme sunucusu yetkilendirme hatası.")
            else:
                raise RuntimeError(f"Güncelleme sunucusu yanıt vermedi ({resp.status_code})")
        except requests.RequestException:
            raise RuntimeError("Güncelleme sunucusuna bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")

    def download_and_prepare_update(
        self,
        download_url: str,
        new_commit_sha: str = "",
        new_version: str = "",
        expected_sha256: str = "",
        sha256sums_url: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> str:
        """
        Downloads update zip to temp folder, verifies SHA-256 integrity, extracts safely,
        and generates apply_update.bat.
        Returns the path to apply_update.bat ready to execute.
        """
        temp_dir = os.path.join(os.environ.get('TEMP', os.path.expanduser('~')), 'NovaCare_Update')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        zip_path = os.path.join(temp_dir, 'update.zip')
        extracted_dir = os.path.join(temp_dir, 'extracted')
        os.makedirs(extracted_dir, exist_ok=True)

        is_api_asset = "api.github.com/repos/" in download_url and "/releases/assets/" in download_url
        headers = {
            "User-Agent": "NovaCare-SystemCare-Suite",
            "Accept": "application/octet-stream" if is_api_asset else "*/*"
        }
        if is_api_asset and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        resp = self._safe_request_get(download_url, headers=headers, stream=True, timeout=30)
        if resp.status_code == 401 and "Authorization" in headers:
            headers.pop("Authorization", None)
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

        # 0. SHA-256 integrity verification
        import hashlib
        hasher = hashlib.sha256()
        with open(zip_path, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        downloaded_hash = hasher.hexdigest().lower()

        if expected_sha256:
            if downloaded_hash != expected_sha256.strip().lower():
                raise ValueError(
                    f"SHA-256 bütünlük doğrulaması başarısız oldu!\n"
                    f"Beklenen: {expected_sha256.strip().lower()}\n"
                    f"İndirilen: {downloaded_hash}"
                )
        elif sha256sums_url:
            try:
                sums_resp = self._safe_request_get(sha256sums_url, headers=self._get_headers(include_auth=False), timeout=15)
                if sums_resp.status_code == 200:
                    target_fn = download_url.split("?")[0].rstrip("/").split("/")[-1].lower()
                    expected_from_sums = None
                    candidate_matches = []
                    for line in sums_resp.text.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            h, fn = parts[0], parts[1].lstrip("*")
                            base_fn = os.path.basename(fn).lower()
                            if base_fn == target_fn:
                                expected_from_sums = h.lower()
                                break
                            elif base_fn in ("novacare_update.zip", "novacare.zip") or base_fn.endswith(".zip"):
                                candidate_matches.append(h.lower())
                    if not expected_from_sums and len(candidate_matches) == 1:
                        expected_from_sums = candidate_matches[0]

                    if expected_from_sums and downloaded_hash != expected_from_sums:
                        raise ValueError(
                            f"SHA256SUMS.txt bütünlük doğrulaması başarısız oldu!\n"
                            f"Beklenen: {expected_from_sums}\n"
                            f"İndirilen: {downloaded_hash}"
                        )
            except requests.RequestException:
                pass

        # Extract zip with strict Zip Slip canonical path checking or handle direct executable
        is_zip = zip_path.lower().endswith('.zip') and zipfile.is_zipfile(zip_path)
        if is_zip:
            canonical_extracted = os.path.realpath(os.path.abspath(extracted_dir))
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for member in zf.infolist():
                    clean_name = os.path.splitdrive(member.filename)[1].lstrip('\\/')
                    target_path = os.path.realpath(os.path.abspath(os.path.join(canonical_extracted, clean_name)))
                    try:
                        is_within = (os.path.commonpath([canonical_extracted, target_path]) == canonical_extracted)
                    except ValueError:
                        is_within = False
                    if not is_within:
                        raise ValueError(f"Güvenlik Uyarısı (Zip Slip): Zararlı arşiv üyesi tespit edildi: {member.filename}")
                    zf.extract(member, canonical_extracted)

            # Handle zipball inner root directory
            source_dir = extracted_dir
            markers = ('main.py', 'core', 'ui', 'VERSION', 'NovaCare.exe')
            if not any(os.path.exists(os.path.join(source_dir, m)) for m in markers):
                for item in os.listdir(extracted_dir):
                    sub = os.path.join(extracted_dir, item)
                    if os.path.isdir(sub) and any(os.path.exists(os.path.join(sub, m)) for m in markers):
                        source_dir = sub
                        break
        else:
            # Standalone exe payload (isolated in extracted_dir so temp_dir files don't leak)
            source_dir = extracted_dir
            if os.path.exists(zip_path):
                with open(zip_path, 'rb') as f:
                    magic = f.read(2)
                if magic != b'MZ':
                    raise ValueError("İndirilen güncelleme dosyası geçerli bir Windows yürütülebilir dosyası veya ZIP arşivi değil.")
                dest_direct_exe = os.path.join(extracted_dir, "NovaCare.exe")
                shutil.copy2(zip_path, dest_direct_exe)

        # 1. Determine target version (DO NOT prematurely save to settings.json before copy succeeds!)
        clean_ver_num = ""
        if new_version:
            from core.config import parse_version_content
            clean_nv, _ = parse_version_content(new_version)
            if clean_nv:
                clean_ver_num = clean_nv

        if not clean_ver_num:
            v_file = os.path.join(source_dir, "VERSION")
            if os.path.exists(v_file):
                try:
                    with open(v_file, "r", encoding="utf-8-sig", errors="replace") as vf:
                        from core.config import parse_version_content
                        extracted_ver, _ = parse_version_content(vf.read())
                        if extracted_ver:
                            clean_ver_num = extracted_ver
                except Exception:
                    pass

        if not clean_ver_num:
            clean_ver_num = self.config.get_version()

        # CRITICAL FIX: Ensure source_dir's VERSION file reflects the target version
        # so that copying source_dir to appRoot deploys the updated version number!
        if clean_ver_num:
            v_file = os.path.join(source_dir, "VERSION")
            try:
                existing_notes = ""
                if os.path.exists(v_file):
                    with open(v_file, "r", encoding="utf-8-sig", errors="replace") as vf:
                        from core.config import parse_version_content
                        _, existing_notes = parse_version_content(vf.read())

                v_content = clean_ver_num
                if existing_notes:
                    v_content += f"\n---\n{existing_notes}"
                with open(v_file, "w", encoding="utf-8") as vf:
                    vf.write(v_content)
            except Exception:
                pass

        current_pid = os.getpid()

        # Determine app paths and exact python interpreter
        if getattr(sys, 'frozen', False):
            app_root = os.path.dirname(sys.executable)
            launcher_target = os.path.join(app_root, "NovaCare.exe")
            python_exe = ""
        else:
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            launcher_target = os.path.join(app_root, "NovaCare.bat")
            python_exe = sys.executable
            pw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pw):
                python_exe = pw

        main_py = os.path.join(app_root, "main.py")

        ps_source_dir = source_dir.replace("'", "''")
        ps_app_root = app_root.replace("'", "''")
        ps_launcher = launcher_target.replace("'", "''")
        ps_main_py = main_py.replace("'", "''")
        ps_python_exe = python_exe.replace("'", "''")
        ps_version = clean_ver_num.replace("'", "''")
        ps_sha = new_commit_sha.replace("'", "''")

        # =====================================================================
        # 2. Generate apply_update.ps1 (Ultra-robust PowerShell script with UTF-8 BOM)
        # =====================================================================
        ps1_path = os.path.join(temp_dir, "apply_update.ps1")
        with open(ps1_path, "w", encoding="utf-8-sig") as pf:
            pf.write(f"""# NovaCare System Suite - Robust In-Place PowerShell Updater
$ErrorActionPreference = 'SilentlyContinue'
$sourceDir = '{ps_source_dir}'
$appRoot = '{ps_app_root}'
$launcher = '{ps_launcher}'
$pythonExe = '{ps_python_exe}'
$mainPy = '{ps_main_py}'
$parentPid = {current_pid}
$version = '{ps_version}'
$commitSha = '{ps_sha}'

# 0. Check administrative permissions and self-elevate if required for $appRoot
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$canWrite = $true
$testWriteFile = Join-Path $appRoot ('.nc_write_test_' + [System.Guid]::NewGuid().ToString('N'))
try {{
    [System.IO.File]::WriteAllText($testWriteFile, 'test')
    Remove-Item -LiteralPath $testWriteFile -Force -ErrorAction SilentlyContinue
}} catch {{
    $canWrite = $false
}}

if (-not $isAdmin -and -not $canWrite) {{
    $proc = Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSCommandPath`"" -Verb RunAs -PassThru -Wait
    exit $proc.ExitCode
}}

# 1. Terminate current NovaCare process and any tree processes
if ($parentPid -gt 0) {{
    Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue
    $pStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($pStopwatch.Elapsed.TotalSeconds -lt 10) {{
        $pProc = Get-Process -Id $parentPid -ErrorAction SilentlyContinue
        if (-not $pProc) {{ break }}
        Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }}
}}
Get-Process -Name 'NovaCare' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Wait up to 15 seconds for complete process exit & file release
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
while ($stopwatch.Elapsed.TotalSeconds -lt 15) {{
    $running = Get-Process -Name 'NovaCare' -ErrorAction SilentlyContinue
    if (-not $running) {{ break }}
    Start-Sleep -Milliseconds 500
}}
Start-Sleep -Milliseconds 500

# 2. Atomic executable replacement with retry loop against external file locks (antivirus, OneDrive)
$srcExe = Join-Path $sourceDir 'NovaCare.exe'
$destExe = Join-Path $appRoot 'NovaCare.exe'
$oldExe = Join-Path $appRoot ('NovaCare.exe.old.' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8))

if (Test-Path -LiteralPath $srcExe) {{
    # Clear any old backup files from previous updates
    Get-ChildItem -LiteralPath $appRoot -Filter 'NovaCare.exe.old*' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

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
        Remove-Item -LiteralPath $destExe -Force -ErrorAction SilentlyContinue
        if (-not (Test-Path -LiteralPath $destExe)) {{
            $destCleared = $true
            break
        }}
        Start-Sleep -Milliseconds 1000
    }}

    $copied = $false
    for ($attempt = 1; $attempt -le 15; $attempt++) {{
        Copy-Item -LiteralPath $srcExe -Destination $destExe -Force -ErrorAction SilentlyContinue
        if ((Test-Path -LiteralPath $destExe) -and ((Get-Item -LiteralPath $destExe).Length -gt 0) -and ((Get-Item -LiteralPath $destExe).Length -eq (Get-Item -LiteralPath $srcExe).Length)) {{
            $copied = $true
            break
        }}
        Start-Sleep -Milliseconds 800
    }}

    if (-not $copied) {{
        # Rollback original executable if copy failed
        if (Test-Path -LiteralPath $oldExe) {{
            Move-Item -LiteralPath $oldExe -Destination $destExe -Force -ErrorAction SilentlyContinue
        }}
        exit 1
    }}
    if (Test-Path -LiteralPath $oldExe) {{ Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue }}
}}

# 3. Synchronize all updated assets and files
Get-ChildItem -LiteralPath $sourceDir -Force | ForEach-Object {{
    if ($_.Name -ne 'NovaCare.exe') {{
        Copy-Item -LiteralPath ($_.FullName) -Destination $appRoot -Recurse -Force -ErrorAction SilentlyContinue
    }}
}}

# Explicitly ensure VERSION in appRoot is updated
$destVFile = Join-Path $appRoot 'VERSION'
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
if ($version) {{
    try {{
        $vNotes = ''
        $srcVFile = Join-Path $sourceDir 'VERSION'
        if (Test-Path -LiteralPath $srcVFile) {{
            $vRaw = [System.IO.File]::ReadAllText($srcVFile, [System.Text.Encoding]::UTF8)
            $parts = $vRaw -split '---', 2
            if ($parts.Length -gt 1) {{ $vNotes = "`n---" + $parts[1] }}
        }}
        [System.IO.File]::WriteAllText($destVFile, ($version + $vNotes), $utf8NoBom)
    }} catch {{}}
}}

# 4. Synchronize Registry DisplayVersion
if ($version) {{
    Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare' -Name 'DisplayVersion' -Value $version -ErrorAction SilentlyContinue
    Set-ItemProperty -Path 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NovaCare' -Name 'DisplayVersion' -Value $version -ErrorAction SilentlyContinue
}}

# 5. Persist new version to settings.json WITHOUT UTF-8 BOM (so Python json.load succeeds)
$cfgDir = Join-Path $env:LOCALAPPDATA 'NovaCare'
if (-not (Test-Path -LiteralPath $cfgDir)) {{
    New-Item -ItemType Directory -Path $cfgDir -Force -ErrorAction SilentlyContinue | Out-Null
}}
$cfgPath = Join-Path $cfgDir 'settings.json'
try {{
    if (Test-Path -LiteralPath $cfgPath) {{
        $jsonRaw = [System.IO.File]::ReadAllText($cfgPath, [System.Text.Encoding]::UTF8)
        $json = $jsonRaw | ConvertFrom-Json
    }} else {{
        $json = [PSCustomObject]@{{}}
    }}
    if ($version) {{ $json.version = $version }}
    if ($commitSha) {{ $json.local_commit_sha = $commitSha }}
    $jsonText = $json | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($cfgPath, $jsonText, $utf8NoBom)
}} catch {{}}

# 6. Relaunch updated NovaCare
Start-Sleep -Milliseconds 500
if (Test-Path -LiteralPath $launcher) {{
    if ($launcher.EndsWith('.bat')) {{
        Start-Process -FilePath 'cmd.exe' -ArgumentList "/c `"$launcher`"" -WorkingDirectory $appRoot
    }} else {{
        Start-Process -FilePath $launcher -WorkingDirectory $appRoot
    }}
}} elseif (Test-Path -LiteralPath $mainPy) {{
    if ((Test-Path -LiteralPath $pythonExe) -and $pythonExe) {{
        Start-Process -FilePath $pythonExe -ArgumentList "`"$mainPy`"" -WorkingDirectory $appRoot -ErrorAction SilentlyContinue
    }} else {{
        Start-Process -FilePath 'pythonw.exe' -ArgumentList "`"$mainPy`"" -WorkingDirectory $appRoot -ErrorAction SilentlyContinue
    }}
}}
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
if {current_pid} gtr 0 (
    taskkill /f /pid {current_pid} > nul 2>&1
)
taskkill /f /im NovaCare.exe > nul 2>&1
timeout /t 1 /nobreak > nul

for /l %%i in (1,1,15) do (
    tasklist /fi "imagename eq NovaCare.exe" 2>nul | find /i "NovaCare.exe" >nul
    if errorlevel 1 (
        goto ready_to_copy
    )
    taskkill /f /im NovaCare.exe > nul 2>&1
    timeout /t 1 /nobreak > nul
)

:ready_to_copy
timeout /t 1 /nobreak > nul

:: Clear destExe with retry loop against locks
if exist "{source_dir}\\NovaCare.exe" (
    if exist "{app_root}\\NovaCare.exe.old" del /f /q "{app_root}\\NovaCare.exe.old" > nul 2>&1
    for /l %%m in (1,1,15) do (
        if not exist "{app_root}\\NovaCare.exe" goto dest_cleared
        move /y "{app_root}\\NovaCare.exe" "{app_root}\\NovaCare.exe.old" > nul 2>&1
        if not exist "{app_root}\\NovaCare.exe" goto dest_cleared
        del /f /q "{app_root}\\NovaCare.exe" > nul 2>&1
        if not exist "{app_root}\\NovaCare.exe" goto dest_cleared
        timeout /t 1 /nobreak > nul
    )
    :dest_cleared
    for /l %%k in (1,1,15) do (
        copy /y "{source_dir}\\NovaCare.exe" "{app_root}\\NovaCare.exe" > nul 2>&1
        if not errorlevel 1 if exist "{app_root}\\NovaCare.exe" goto exe_copied
        timeout /t 1 /nobreak > nul
    )
    :: Rollback if copy failed
    if exist "{app_root}\\NovaCare.exe.old" move /y "{app_root}\\NovaCare.exe.old" "{app_root}\\NovaCare.exe" > nul 2>&1
    goto launch_fallback
)

:exe_copied
if exist "{app_root}\\NovaCare.exe.old" del /f /q "{app_root}\\NovaCare.exe.old" > nul 2>&1

:: Copy other assets (/r overwrites read-only, /h copies hidden)
xcopy /s /e /y /i /q /r /h "{source_dir}\\*" "{app_root}\\" > nul 2>&1

:: Explicitly copy VERSION file if exists
if exist "{source_dir}\\VERSION" copy /y "{source_dir}\\VERSION" "{app_root}\\VERSION" > nul 2>&1

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

cd /d "{app_root}"
if exist "{launcher_target}" (
    start "" "{launcher_target}"
) else if exist "{main_py}" (
    if exist "{python_exe}" (
        start "" "{python_exe}" "{main_py}"
    ) else (
        start "" pythonw "{main_py}"
    )
)

:cleanup_batch
if exist "%~dp0apply_update.ps1" del /f /q "%~dp0apply_update.ps1" > nul 2>&1
if exist "%~dp0update.zip" del /f /q "%~dp0update.zip" > nul 2>&1
if exist "%~dp0extracted" rd /s /q "%~dp0extracted" > nul 2>&1
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

        from core.utils import is_admin
        spawned = False
        if not is_admin() and sys.platform == 'win32':
            # Request UAC elevation for updater so it can update files in Program Files and HKLM
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c "{batch_path}"', None, 1)
                if ret > 32:
                    spawned = True
            except Exception:
                pass

        if not spawned:
            flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            flags |= getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            subprocess.Popen(["cmd.exe", "/c", batch_path], env=clean_env, creationflags=flags)

        # Cleanly close all Qt windows to release file handles immediately
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                for widget in app.topLevelWidgets():
                    if hasattr(widget, '_force_exit'):
                        widget._force_exit = True
                    if hasattr(widget, 'cleanup_workers'):
                        try:
                            widget.cleanup_workers()
                        except Exception:
                            pass
                    if hasattr(widget, 'tray_icon') and widget.tray_icon:
                        try:
                            widget.tray_icon.hide()
                        except Exception:
                            pass
                app.closeAllWindows()
                app.quit()
        except Exception:
            pass

        import threading, time
        def _hard_exit():
            time.sleep(1.5)
            os._exit(0)
        threading.Thread(target=_hard_exit, daemon=True).start()

        sys.exit(0)
