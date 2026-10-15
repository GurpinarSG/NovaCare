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
        self.token = token or self.config.get("github_token", "")
        self.branch = branch or self.config.get("target_branch", "main")
        self.current_version = current_version

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

    def check_for_updates(self, mode: Optional[str] = None) -> UpdateInfo:
        """
        Checks for updates according to mode ('branch' for commit tracking or 'release').
        Default mode is read from config.
        """
        current_mode = mode or self.config.get("update_mode", "branch")
        if current_mode == "branch":
            return self._check_branch_commits()
        else:
            return self._check_releases()

    def _check_branch_commits(self) -> UpdateInfo:
        """
        Inspects the latest commit on the repository branch (e.g. 'main').
        Whenever you push or edit files directly on GitHub, this detects it instantly!
        """
        commits_url = f"https://api.github.com/repos/{self.repo}/commits/{self.branch}"
        local_sha = self.config.get("local_commit_sha", "")

        try:
            resp = requests.get(commits_url, headers=self._get_headers(), timeout=10)
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

                available = (remote_sha != local_sha) and bool(remote_sha)

                download_url = f"https://api.github.com/repos/{self.repo}/zipball/{self.branch}"

                if available:
                    title = f"GitHub Depo Değişikliği ({short_sha})"
                    changelog = (
                        f"GitHub deposundaki klasörde yeni değişiklikler tespit edildi!\n\n"
                        f"• Son Commit: {short_sha}\n"
                        f"• Değişiklik Mesajı: {commit_msg}\n"
                        f"• Tarih: {commit_date}\n\n"
                        "Güncellemeyi yükleyerek en son kodları doğrudan uygulayabilirsiniz."
                    )
                else:
                    title = "Depo ile Senkronize"
                    changelog = f"GitHub deposundaki en güncel commit ({short_sha}) bilgisayarınızda yüklü."

                return UpdateInfo(
                    available=available,
                    current_version=f"{local_sha[:7]}",
                    latest_version=f"{short_sha}",
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
                raise RuntimeError("GitHub Yetkilendirme Hatası: Token geçersiz veya süresi dolmuş.")
            else:
                raise RuntimeError(f"GitHub API Hatası ({resp.status_code}): {resp.text[:120]}")
        except requests.RequestException as e:
            raise RuntimeError(f"GitHub sunucusuna bağlanılamadı: {e}")

    def _check_releases(self) -> UpdateInfo:
        """Traditional GitHub Release tag inspector."""
        api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        try:
            resp = requests.get(api_url, headers=self._get_headers(), timeout=10)
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
                for asset in assets:
                    if asset.get("name", "").endswith(".zip"):
                        download_url = asset.get("browser_download_url") or asset.get("url")
                        download_size = asset.get("size", 0)
                        break

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
                return self._check_branch_commits()
            else:
                raise RuntimeError(f"GitHub API Hatası ({resp.status_code})")
        except requests.RequestException as e:
            raise RuntimeError(f"GitHub sunucusuna bağlanılamadı: {e}")

    def download_and_prepare_update(
        self,
        download_url: str,
        new_commit_sha: str = "",
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

        # If we updated to a new commit sha, save it to local settings now
        if new_commit_sha:
            self.config.set("local_commit_sha", new_commit_sha)

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
