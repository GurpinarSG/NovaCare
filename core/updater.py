"""
NovaCare System Suite - GitHub Automatic & Manual Updater
Checks GitHub Releases for new versions, downloads assets/zipballs, and applies updates safely.
Supports Personal Access Tokens (PAT) for private repositories and higher rate limits.
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

def parse_version_tuple(v_str: str) -> tuple[int, ...]:
    """Extract integer version components from string (e.g. 'v1.2.3' -> (1, 2, 3))."""
    cleaned = re.sub(r'^[vV]', '', v_str.strip())
    parts = re.findall(r'\d+', cleaned)
    if not parts:
        return (0, 0, 0)
    return tuple(int(p) for p in parts)

def is_newer_version(latest_str: str, current_str: str) -> bool:
    """Returns True if latest_str is strictly newer than current_str."""
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
        current_version: str = CURRENT_VERSION
    ):
        self.config = ConfigManager()
        self.repo = repo or self.config.get("github_repo", "GurpinarSG/NovaCare")
        self.token = token or self.config.get("github_token", "")
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"

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
            r = requests.get("https://api.github.com/user", headers=self._get_headers(), timeout=8)
            if r.status_code == 200:
                user_data = r.json()
                login = user_data.get("login", "Bilinmiyor")
                return True, login
            return False, f"Geçersiz token (HTTP {r.status_code})"
        except Exception as e:
            return False, str(e)

    def check_for_updates(self) -> UpdateInfo:
        """
        Queries GitHub API for the latest release.
        Returns UpdateInfo dataclass.
        """
        try:
            resp = requests.get(self.api_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                tag_name = data.get("tag_name", "0.0.0")
                clean_version = tag_name.lstrip("vV")
                title = data.get("name") or f"NovaCare v{clean_version}"
                body = data.get("body") or "Yeni güncelleme mevcut."
                published = data.get("published_at", "")[:10]
                is_pre = data.get("prerelease", False)

                # Look for release asset zip
                download_url = ""
                download_size = 0

                assets = data.get("assets", [])
                for asset in assets:
                    if asset.get("name", "").endswith(".zip"):
                        download_url = asset.get("browser_download_url") or asset.get("url")
                        download_size = asset.get("size", 0)
                        break

                # Fallback to source zipball if no custom asset
                if not download_url:
                    download_url = data.get("zipball_url", "")

                available = is_newer_version(clean_version, self.current_version)

                return UpdateInfo(
                    available=available,
                    current_version=self.current_version,
                    latest_version=clean_version,
                    release_title=title,
                    changelog=body,
                    download_url=download_url,
                    download_size=download_size,
                    published_at=published,
                    is_prerelease=is_pre
                )
            elif resp.status_code == 404:
                # No official release found, try tags fallback
                return self._check_tags_fallback()
            elif resp.status_code == 401:
                raise RuntimeError("GitHub Yetkilendirme Hatası: Token geçersiz veya süresi dolmuş.")
            else:
                raise RuntimeError(f"GitHub API Hatası ({resp.status_code}): {resp.text[:120]}")
        except requests.RequestException as e:
            raise RuntimeError(f"GitHub sunucusuna bağlanılamadı: {e}")

    def _check_tags_fallback(self) -> UpdateInfo:
        """Fallback to /tags endpoint if no formal release is published yet."""
        tags_url = f"https://api.github.com/repos/{self.repo}/tags"
        try:
            resp = requests.get(tags_url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                tags = resp.json()
                if tags and isinstance(tags, list):
                    latest_tag = tags[0].get("name", "0.0.0")
                    clean_ver = latest_tag.lstrip("vV")
                    zipball = tags[0].get("zipball_url", "")
                    avail = is_newer_version(clean_ver, self.current_version)
                    return UpdateInfo(
                        available=avail,
                        current_version=self.current_version,
                        latest_version=clean_ver,
                        release_title=f"NovaCare {latest_tag}",
                        changelog="GitHub üzerinden yeni sürüm etiketi bulundu.",
                        download_url=zipball,
                        download_size=0,
                        published_at="En Son Sürüm"
                    )
        except Exception:
            pass

        return UpdateInfo(
            available=False,
            current_version=self.current_version,
            latest_version=self.current_version,
            release_title="Güncel",
            changelog="Depoda yeni bir sürüm veya etiket bulunamadı.",
            download_url="",
            download_size=0,
            published_at=""
        )

    def download_and_prepare_update(
        self,
        download_url: str,
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

        # Download with requests stream
        headers = self._get_headers()
        # If download_url points to GitHub API asset, accept octet-stream
        if "api.github.com/repos/" in download_url and "/releases/assets/" in download_url:
            headers["Accept"] = "application/octet-stream"

        resp = requests.get(download_url, headers=headers, stream=True, timeout=30)
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

        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extracted_dir)

        # Handle zipball inner root directory
        source_dir = extracted_dir
        items = os.listdir(extracted_dir)
        if len(items) == 1 and os.path.isdir(os.path.join(extracted_dir, items[0])):
            inner_dir = os.path.join(extracted_dir, items[0])
            if any(os.path.exists(os.path.join(inner_dir, f)) for f in ('main.py', 'core', 'ui')):
                source_dir = inner_dir

        # Create apply_update.bat
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        launcher_bat = os.path.join(app_root, "Başlat_NovaCare.bat")
        main_py = os.path.join(app_root, "main.py")

        batch_path = os.path.join(temp_dir, "apply_update.bat")
        with open(batch_path, "w", encoding="cp1254", errors="ignore") as bf:
            bf.write(f"""@echo off
title NovaCare Guncelleme Uygulaniyor...
echo NovaCare yeni surum dosyalari yukleniyor, lutfen bekleyin...
timeout /t 2 /nobreak > nul

:: Copy updated files over current directory
xcopy /s /e /y "{source_dir}\\*" "{app_root}\\"

echo Guncelleme basariyla tamamlandi. NovaCare yeniden baslatiliyor...
timeout /t 1 /nobreak > nul

if exist "{launcher_bat}" (
    start "" "{launcher_bat}"
) else (
    start "" pythonw "{main_py}"
)

:: Self clean batch
del /f /q "%~f0"
exit
""")

        return batch_path

    def launch_updater_and_exit(self, batch_path: str):
        """Spawns the updater batch script in background and exits current application."""
        subprocess.Popen(f'cmd.exe /c "{batch_path}"', shell=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        sys.exit(0)
