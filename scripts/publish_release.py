"""
NovaCare - GitHub Publisher & Release Creator Script
Uploads local project files to GurpinarSG/NovaCare and creates a GitHub Release with update asset.
"""
import os
import sys
import base64
import json
import zipfile
import requests

TOKEN = "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"
REPO = "GurpinarSG/NovaCare"
BRANCH = "main"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "NovaCare-Publisher"
}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_latest_commit_sha():
    url = f"https://api.github.com/repos/{REPO}/git/refs/heads/{BRANCH}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()["object"]["sha"]

def upload_blob(file_path: str) -> str:
    with open(file_path, "rb") as f:
        content = f.read()
    b64_content = base64.b64encode(content).decode("utf-8")
    url = f"https://api.github.com/repos/{REPO}/git/blobs"
    payload = {"content": b64_content, "encoding": "base64"}
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()["sha"]

def push_files_to_github():
    print(f"[*] '{REPO}' deposuna dosyalar yükleniyor...")
    base_sha = get_latest_commit_sha()

    # Collect files
    ignore_dirs = {'.git', '__pycache__', '.pytest_cache', '.vscode', '.idea'}
    files_to_push = []

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if f.endswith(('.pyc', '.tmp', '.zip')):
                continue
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, ROOT_DIR).replace('\\', '/')
            files_to_push.append((rel_p, full_p))

    print(f"[*] Toplam yüklenecek dosya sayısı: {len(files_to_push)}")
    tree_items = []

    for rel_p, full_p in files_to_push:
        blob_sha = upload_blob(full_p)
        tree_items.append({
            "path": rel_p,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha
        })
        print(f"  + Yüklendi: {rel_p}")

    # Create tree
    print("[*] Git ağacı oluşturuluyor...")
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees"
    r = requests.post(tree_url, headers=HEADERS, json={"base_tree": base_sha, "tree": tree_items})
    r.raise_for_status()
    new_tree_sha = r.json()["sha"]

    # Create commit
    print("[*] Commit oluşturuluyor...")
    commit_url = f"https://api.github.com/repos/{REPO}/git/commits"
    commit_payload = {
        "message": "NovaCare System Care Suite 2026 - Initial Release",
        "tree": new_tree_sha,
        "parents": [base_sha]
    }
    r = requests.post(commit_url, headers=HEADERS, json=commit_payload)
    r.raise_for_status()
    new_commit_sha = r.json()["sha"]

    # Update ref
    print("[*] Branch güncelleniyor (main)...")
    ref_url = f"https://api.github.com/repos/{REPO}/git/refs/heads/{BRANCH}"
    r = requests.patch(ref_url, headers=HEADERS, json={"sha": new_commit_sha})
    r.raise_for_status()
    print("[✔] Kodlar başarıyla GitHub'a yüklendi!")

def create_release(tag_name: str, release_title: str, changelog: str):
    print(f"[*] GitHub Sürümü oluşturuluyor: {tag_name}...")
    # Create zip asset
    zip_path = os.path.join(ROOT_DIR, "NovaCare_Update.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        ignore_dirs = {'.git', '__pycache__', '.pytest_cache'}
        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for f in files:
                if f in ("NovaCare_Update.zip",) or f.endswith(('.pyc', '.tmp')):
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, ROOT_DIR)
                zf.write(full_p, rel_p)

    # Create Release on GitHub
    rel_url = f"https://api.github.com/repos/{REPO}/releases"
    payload = {
        "tag_name": tag_name,
        "name": release_title,
        "body": changelog,
        "draft": False,
        "prerelease": False
    }
    r = requests.post(rel_url, headers=HEADERS, json=payload)
    r.raise_for_status()
    rel_data = r.json()
    upload_url = rel_data["upload_url"].split("{")[0]

    # Upload zip asset
    print("[*] Sürüm paketi (NovaCare_Update.zip) yükleniyor...")
    with open(zip_path, "rb") as zf:
        asset_headers = {
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/zip",
            "User-Agent": "NovaCare-Publisher"
        }
        params = {"name": "NovaCare_Update.zip"}
        r_asset = requests.post(upload_url, headers=asset_headers, params=params, data=zf)
        r_asset.raise_for_status()

    # Clean local zip
    if os.path.exists(zip_path):
        os.remove(zip_path)

    print(f"[✔] GitHub Sürümü başarıyla oluşturuldu: {tag_name} ({release_title})")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="Kodları GitHub'a gönderir")
    parser.add_argument("--release", type=str, help="Belirtilen etiketle yeni GitHub sürümü oluşturur (Örn: v1.0.0)")
    args = parser.parse_args()

    if args.push:
        push_files_to_github()

    if args.release:
        create_release(
            tag_name=args.release,
            release_title=f"NovaCare System Care Suite {args.release}",
            changelog="• Tek Tıkla Sistem Bakımı ve Sağlık Skoru\n• Çöp Dosya ve Tarayıcı Temizliği\n• Kayıt Defteri Onarımı ve Otomatik Yedekleme\n• RAM Hızlandırıcı ve Süreç Yöneticisi\n• Disk Analizörü ve Büyük Dosya Bulucu\n• GitHub Otomatik ve Manuel Güncelleme Sistemi"
        )
