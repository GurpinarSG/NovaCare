"""
NovaCare - GitHub Publisher & Release Creator Script
Uploads local project source files to GitHub (GurpinarSG/NovaCare)
and publishes official GitHub Releases with setup installer, portable zip, and update packages.
"""
import os
import sys
import base64
import json
import zipfile
import hashlib
import requests
from typing import Optional

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.config import ConfigManager

cfg = ConfigManager()
TOKEN = cfg.get_secure_token()
REPO = cfg.get("github_repo", "GurpinarSG/NovaCare")
BRANCH = cfg.get("target_branch", "main")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "NovaCare-Publisher"
}

def get_current_version() -> str:
    from core.config import load_base_version
    return load_base_version()

def get_latest_commit_sha() -> str:
    url = f"https://api.github.com/repos/{REPO}/git/refs/heads/{BRANCH}"
    r = requests.get(url, headers=HEADERS, timeout=12)
    r.raise_for_status()
    return r.json()["object"]["sha"]

def upload_blob(file_path: str) -> str:
    with open(file_path, "rb") as f:
        content = f.read()
    b64_content = base64.b64encode(content).decode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/git/blobs"
    payload = {"content": b64_content, "encoding": "base64"}
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["sha"]

def push_files_to_github(commit_msg: Optional[str] = None):
    if not TOKEN:
        print("[X] HATA: GitHub tokeni tanımlanmamış. Lütfen ayarlar sekmesinden tokeninizi kaydedin.")
        return False

    print("=" * 65)
    print(f"  NovaCare System Care - GitHub Kod Yükleyici")
    print(f"  Hedef Depo: {REPO} (Dal: {BRANCH})")
    print("=" * 65)

    try:
        base_sha = get_latest_commit_sha()
    except Exception as e:
        print(f"[X] Hedef depoya ulaşılamadı: {e}")
        return False

    ignore_dirs = {
        '.git', '__pycache__', '.pytest_cache', '.vscode', '.idea',
        'dist', 'build', 'temp', 'NovaCare_Build', 'NovaCare_Setup_Build'
    }

    files_to_push = []
    for root, dirs, files in os.walk(ROOT_DIR):
        # Exclude ignored directories or any github_release_* folders
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('github_release_')]
        for f in files:
            if f.endswith(('.pyc', '.pyo', '.tmp', '.zip', '.tar.gz', '.exe', '.lnk', '.log', '.spec')):
                continue
            if f in ('err.txt', 'out.txt', 'config.json'):
                continue
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, ROOT_DIR).replace('\\', '/')
            files_to_push.append((rel_p, full_p))

    print(f"[*] Kaynak kod taranıyor... Toplam {len(files_to_push)} dosya yüklenecek.")
    tree_items = []

    for idx, (rel_p, full_p) in enumerate(files_to_push, 1):
        try:
            blob_sha = upload_blob(full_p)
            tree_items.append({
                "path": rel_p,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })
            print(f"  [{idx:02d}/{len(files_to_push):02d}] + {rel_p}")
        except Exception as e:
            print(f"  [X] Hata: {rel_p} yüklenemedi: {e}")
            return False

    # Create Tree
    print("\n[*] GitHub Ağacı (Git Tree) oluşturuluyor...")
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees"
    r = requests.post(tree_url, headers=HEADERS, json={"tree": tree_items}, timeout=20)
    r.raise_for_status()
    new_tree_sha = r.json()["sha"]

    # Create Commit
    version = get_current_version()
    msg = commit_msg or f"NovaCare v{version}: Setup wizard overhaul, uninstaller, responsive layout & bugfixes"
    print(f"[*] Commit oluşturuluyor: '{msg}'...")
    commit_url = f"https://api.github.com/repos/{REPO}/git/commits"
    commit_payload = {
        "message": msg,
        "tree": new_tree_sha,
        "parents": [base_sha]
    }
    r = requests.post(commit_url, headers=HEADERS, json=commit_payload, timeout=20)
    r.raise_for_status()
    new_commit_sha = r.json()["sha"]

    # Update Branch Ref
    print(f"[*] Branch güncelleniyor: refs/heads/{BRANCH}...")
    ref_url = f"https://api.github.com/repos/{REPO}/git/refs/heads/{BRANCH}"
    r = requests.patch(ref_url, headers=HEADERS, json={"sha": new_commit_sha}, timeout=20)
    r.raise_for_status()

    cfg.set("local_commit_sha", new_commit_sha)

    print("\n" + "=" * 65)
    print("  [✔] TEBRİKLER! Güncel kodlar GitHub deposuna başarıyla yüklendi!")
    print(f"  Commit SHA: {new_commit_sha[:10]}")
    print(f"  Depo Linki: https://github.com/{REPO}")
    print("=" * 65)
    return True

def get_changelog_for_tag(tag: str) -> str:
    # 1. First check if VERSION file contains manual update notes
    try:
        from core.config import load_version_and_notes
        v_num, v_notes = load_version_and_notes()
        if v_notes and v_num == tag.lstrip("vV"):
            return f"### 🚀 NovaCare System Care Suite {tag} - Güncelleme Notları\n\n{v_notes}"
    except Exception:
        pass

    # 2. Check CHANGELOG.md
    cl_path = os.path.join(ROOT_DIR, "CHANGELOG.md")
    if os.path.exists(cl_path):
        try:
            with open(cl_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            clean_tag = tag.lstrip("vV")
            capturing = False
            result = []
            for line in lines:
                if f"[{clean_tag}]" in line or f"[v{clean_tag}]" in line:
                    capturing = True
                    result.append(line)
                    continue
                if capturing:
                    if line.startswith("## [") or line.startswith("## v"):
                        break
                    result.append(line)
            if result:
                return "".join(result).strip()
        except Exception:
            pass

    return (
        f"### NovaCare System Care Suite {tag}\n\n"
        "• Modern Kurulum Sihirbazı (Setup Wizard)\n"
        "• Entegre Yerel Program Kaldırıcı (Windows Denetim Masası desteği)\n"
        "• Duyarlı Pencere Geometrisi ve Kelime Kaydırma Desteği\n"
        "• Tek Tıkla Sistem Bakımı ve Sağlık Skoru\n"
        "• Çöp Dosya ve Tarayıcı Temizliği\n"
        "• Kayıt Defteri Onarımı ve Otomatik Yedekleme\n"
        "• RAM Hızlandırıcı ve Süreç Yöneticisi\n"
        "• GitHub Otomatik ve Manuel Güncelleme Sistemi"
    )

def upload_release_asset(upload_url: str, file_path: str, asset_name: str, content_type: str = "application/octet-stream", max_retries: int = 4):
    print(f"  [*] Yükleniyor: {asset_name} ({os.path.getsize(file_path) / (1024 * 1024):.1f} MB)...")
    url = upload_url.split("{")[0]
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": content_type,
        "User-Agent": "NovaCare-Publisher"
    }
    import time
    for attempt in range(1, max_retries + 1):
        try:
            with open(file_path, "rb") as f:
                r = requests.post(url, headers=headers, params={"name": asset_name}, data=f, timeout=180)
                r.raise_for_status()
            print(f"  [✔] Yüklendi: {asset_name}")
            return True
        except Exception as e:
            if attempt < max_retries:
                print(f"  [!] Yükleme denemesi {attempt} başarısız ({e}). 3 saniye sonra tekrar deneniyor...")
                time.sleep(3)
            else:
                raise e

def create_release(tag_name: str, release_title: Optional[str] = None, changelog: Optional[str] = None):
    if not TOKEN:
        print("[X] HATA: GitHub tokeni tanımlanmamış.")
        return False

    clean_tag = tag_name.lstrip("vV")
    title = release_title or f"NovaCare System Care Suite v{clean_tag}"
    body = changelog or get_changelog_for_tag(tag_name)

    print("=" * 65)
    print(f"  GitHub Sürümü Oluşturuluyor: {tag_name}")
    print(f"  Başlık: {title}")
    print("=" * 65)

    # 1. Create or Find Release
    rel_url = f"https://api.github.com/repos/{REPO}/releases"
    payload = {
        "tag_name": tag_name,
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False
    }

    try:
        r = requests.post(rel_url, headers=HEADERS, json=payload, timeout=20)
        if r.status_code == 422:
            print("[!] Bu etiket zaten mevcut, mevcut sürüm bilgisi alınıyor...")
            r_get = requests.get(f"https://api.github.com/repos/{REPO}/releases/tags/{tag_name}", headers=HEADERS, timeout=15)
            r_get.raise_for_status()
            rel_data = r_get.json()
        else:
            r.raise_for_status()
            rel_data = r.json()
    except Exception as e:
        print(f"[X] Sürüm oluşturulurken hata: {e}")
        return False

    upload_url = rel_data.get("upload_url", "")
    rel_id = rel_data.get("id")

    # Helper to remove duplicate asset before re-upload
    def delete_existing_asset(name):
        try:
            r_assets = requests.get(f"https://api.github.com/repos/{REPO}/releases/{rel_id}/assets", headers=HEADERS, timeout=15)
            if r_assets.status_code == 200:
                for a in r_assets.json():
                    if a.get("name") == name:
                        requests.delete(f"https://api.github.com/repos/{REPO}/releases/assets/{a.get('id')}", headers=HEADERS, timeout=15)
        except Exception:
            pass

    rel_folder = os.path.join(ROOT_DIR, f"github_release_v{clean_tag}")
    os.makedirs(rel_folder, exist_ok=True)

    # 2. Prepare & Upload Setup Installer
    setup_file = os.path.join(rel_folder, f"NovaCare_Setup_v{clean_tag}.exe")
    if not os.path.exists(setup_file):
        for candidate in [
            os.path.join(ROOT_DIR, f"NovaCare_Setup_v{clean_tag}.exe"),
            os.path.join(ROOT_DIR, "NovaCare_Setup.exe"),
            os.path.join(ROOT_DIR, "dist", f"NovaCare_Setup_v{clean_tag}.exe")
        ]:
            if os.path.exists(candidate):
                import shutil
                shutil.copy2(candidate, setup_file)
                break

    if os.path.exists(setup_file):
        delete_existing_asset(f"NovaCare_Setup_v{clean_tag}.exe")
        upload_release_asset(upload_url, setup_file, f"NovaCare_Setup_v{clean_tag}.exe")

    # 3. Prepare & Upload Portable Zip
    portable_file = os.path.join(rel_folder, f"NovaCare_v{clean_tag}_Portable.zip")
    if os.path.exists(portable_file):
        delete_existing_asset(f"NovaCare_v{clean_tag}_Portable.zip")
        upload_release_asset(upload_url, portable_file, f"NovaCare_v{clean_tag}_Portable.zip", "application/zip")

    # 4. Prepare & Upload NovaCare_Update.zip
    update_file = os.path.join(rel_folder, "NovaCare_Update.zip")
    if os.path.exists(update_file):
        delete_existing_asset("NovaCare_Update.zip")
        upload_release_asset(upload_url, update_file, "NovaCare_Update.zip", "application/zip")

    # 5. Upload SHA256SUMS.txt
    sums_file = os.path.join(rel_folder, "SHA256SUMS.txt")
    if os.path.exists(sums_file):
        delete_existing_asset("SHA256SUMS.txt")
        upload_release_asset(upload_url, sums_file, "SHA256SUMS.txt", "text/plain")

    print("\n" + "=" * 65)
    print(f"  [✔] GitHub Sürümü (Release) Başarıyla Yayınlandı!")
    print(f"  Sürüm Bağlantısı: {rel_data.get('html_url')}")
    print("=" * 65)
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaCare GitHub Publisher")
    parser.add_argument("--push", action="store_true", help="Kaynak kodları GitHub deposuna yükler")
    parser.add_argument("--set-version", type=str, help="Sürüm numarasını günceller (Örn: 1.0.1)")
    parser.add_argument("--release", type=str, help="GitHub Sürümü yayınlar (Örn: v1.0.1)")
    parser.add_argument("--message", type=str, help="Özel commit mesajı")
    args = parser.parse_args()

    if args.set_version:
        v_clean = args.set_version.lstrip("vV").strip()
        v_file = os.path.join(ROOT_DIR, "VERSION")
        with open(v_file, "w", encoding="utf-8") as vf:
            vf.write(f"{v_clean}\n")
        print(f"[✔] Sürüm numarası güncellendi: v{v_clean}")

    if args.push:
        push_files_to_github(commit_msg=args.message)

    if args.release:
        create_release(tag_name=args.release)
