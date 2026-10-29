"""
NovaCare System Suite - Public Auto-Updater & Security Verification Tests
Verifies unauthenticated public updates, release asset streaming, DPAPI token storage,
and credential decoupling.
"""
import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import core.security as sec
from core.config import ConfigManager
from core.updater import GitHubUpdater

def test_security_cleanliness():
    print("[1/10] Testing core.security cleanliness...")
    # Verify no ciphertext vault constants in security module
    assert not hasattr(sec, '_CIPHER_PAYLOAD'), "Found _CIPHER_PAYLOAD in core.security!"
    assert not hasattr(sec, '_AUTH_TAG'), "Found _AUTH_TAG in core.security!"
    assert not hasattr(sec, '_VAULT_SALT'), "Found _VAULT_SALT in core.security!"
    assert not hasattr(sec, '_SEED_A'), "Found _SEED_A in core.security!"
    assert not hasattr(sec, '_SEED_B'), "Found _SEED_B in core.security!"

    # Verify get_embedded_token() returns empty string when env var is unset
    orig_env = os.environ.pop("GITHUB_TOKEN", None)
    try:
        assert sec.get_embedded_token() == "", "get_embedded_token() must return empty when GITHUB_TOKEN not set"
        os.environ["GITHUB_TOKEN"] = "test_env_token_val"
        assert sec.get_embedded_token() == "test_env_token_val", "get_embedded_token() must read GITHUB_TOKEN"
    finally:
        if orig_env is not None:
            os.environ["GITHUB_TOKEN"] = orig_env
        else:
            os.environ.pop("GITHUB_TOKEN", None)
    print("  [✔] core.security is clean of hardcoded secrets and correctly delegates to env.")

def test_config_token_resolution():
    print("[2/10] Testing ConfigManager token resolution...")
    cfg = ConfigManager()

    # Save and restore current DPAPI token if any
    saved_enc = cfg.settings.get("github_token_encrypted")
    orig_env = os.environ.pop("GITHUB_TOKEN", None)
    try:
        # With neither env nor DPAPI, must return empty string
        cfg.settings.pop("github_token_encrypted", None)
        assert cfg.get_secure_token() == "", "Must return empty string when no token configured"

        # When set_secure_token is called, encrypts via DPAPI
        cfg.set_secure_token("test_token_12345")
        assert "github_token_encrypted" in cfg.settings
        assert cfg.get_secure_token() == "test_token_12345"

        # Clearing token removes key from settings
        cfg.set_secure_token("")
        assert "github_token_encrypted" not in cfg.settings
        assert cfg.get_secure_token() == ""

        # Environment variable overrides
        os.environ["GITHUB_TOKEN"] = "env_override_token"
        assert cfg.get_secure_token() == "env_override_token"
    finally:
        if orig_env is not None:
            os.environ["GITHUB_TOKEN"] = orig_env
        else:
            os.environ.pop("GITHUB_TOKEN", None)
        if saved_enc:
            cfg.settings["github_token_encrypted"] = saved_enc
            cfg.save_all()
    print("  [✔] ConfigManager get_secure_token and set_secure_token work as expected.")

def test_unauthenticated_release_check():
    print("[3/10] Testing unauthenticated GitHub Release checking...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.3")
    info = updater.check_for_updates(mode="release")

    assert info.available == True, "Should detect v1.2.4 as newer than v1.2.3"
    assert info.latest_version == "v1.2.4"
    assert "https://github.com/GurpinarSG/NovaCare/releases/download/" in info.download_url
    assert info.download_url.endswith(".zip")
    assert info.download_size > 0
    print(f"  [✔] Release check succeeded: {info.latest_version} -> {info.download_url} ({info.download_size} bytes)")

def test_unauthenticated_branch_check():
    print("[4/10] Testing unauthenticated branch/commit checking...")
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.3")
    info = updater.check_for_updates(mode="branch")

    assert info.new_commit_sha != "", "Must fetch remote commit SHA"
    assert "https://github.com/GurpinarSG/NovaCare/archive/refs/heads/main.zip" in info.download_url
    print(f"  [✔] Branch commit check succeeded: SHA={info.new_commit_sha[:10]} -> {info.download_url}")

def test_invalid_token_resilience():
    print("[5/10] Testing resilience against invalid/expired tokens...")
    # Bad token should not crash; it must automatically fall back to unauthenticated public access
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="ghp_REVOKED_TOKEN_XYZ", current_version="1.2.3")
    info = updater.check_for_updates(mode="release")
    assert info.available == True
    assert info.latest_version == "v1.2.4"
    print("  [✔] Graceful 401 fallback to public unauthenticated access succeeded.")

def test_unauthenticated_download_stream():
    print("[6/10] Testing unauthenticated release asset download streaming...")
    import requests
    url = "https://github.com/GurpinarSG/NovaCare/releases/download/v1.2.4/NovaCare_Update.zip"
    headers = {"User-Agent": "NovaCare-SystemCare-Suite", "Accept": "*/*"}
    r = requests.get(url, headers=headers, stream=True, timeout=15)
    assert r.status_code == 200, f"Expected HTTP 200, got {r.status_code}"
    chunk = next(r.iter_content(chunk_size=4096))
    assert chunk[:4] == b"PK\x03\x04", "Downloaded content must begin with ZIP magic bytes PK\\x03\\x04"
    r.close()
    print("  [✔] Asset downloaded and verified ZIP header without any credentials.")

def test_recursion_guard_on_404():
    print("[7/10] Testing 404 recursion guard resilience...")
    from unittest.mock import patch, MagicMock
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.3")
    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404

    with patch.object(updater, '_safe_request_get', return_value=mock_resp_404):
        # Must raise RuntimeError, NOT RecursionError
        try:
            updater.check_for_updates(mode="release")
            assert False, "Should have raised RuntimeError on 404"
        except RuntimeError as e:
            assert "404" in str(e) or "bulunamadı" in str(e)
        except RecursionError:
            assert False, "Fatal infinite recursion detected on 404!"

        try:
            updater.check_for_updates(mode="branch")
            assert False, "Should have raised RuntimeError on 404"
        except RuntimeError as e:
            assert "404" in str(e) or "bulunamadı" in str(e)
        except RecursionError:
            assert False, "Fatal infinite recursion detected on 404!"
    print("  [✔] Recursion guard prevents mutual infinite recursion on 404.")

def test_version_parsing_edge_cases():
    print("[8/10] Testing version parsing and comparison edge cases...")
    from core.updater import parse_version_tuple, is_newer_version
    assert parse_version_tuple("v1.2.4") == (1, 2, 4)
    assert parse_version_tuple("1.2.4") == (1, 2, 4)
    assert parse_version_tuple("1.2") == (1, 2)
    # Crucial: commit sha in display label must NOT corrupt version numbers
    assert parse_version_tuple("1.2.4 (Derleme: c77c7b8)") == (1, 2, 4)
    assert parse_version_tuple("v1.2.4-rc1") == (1, 2, 4)

    assert not is_newer_version("1.2.4", "1.2.4")
    assert not is_newer_version("1.2.4", "1.2.4 (Derleme: c77c7b8)")
    assert is_newer_version("1.2.5", "1.2.4 (Derleme: c77c7b8)")
    assert is_newer_version("1.3.0", "1.2.4")
    assert not is_newer_version("1.2.3", "1.2.4")
    print("  [✔] Version parsing correctly handles build SHAs and semver comparisons.")

def test_download_and_prepare_update_pipeline():
    print("[9/10] Testing download_and_prepare_update pipeline & script generation...")
    import tempfile, zipfile
    updater = GitHubUpdater("GurpinarSG/NovaCare", token="", current_version="1.2.3")

    # Create dummy update zip to test preparation and script syntax without huge network downloads
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tf:
        dummy_zip_path = tf.name
    with zipfile.ZipFile(dummy_zip_path, "w") as zf:
        zf.writestr("VERSION", "1.2.5\n---\nTest Notes\n")
        zf.writestr("NovaCare.exe", b"MZdummyexecutablebytes")

    # Use file:// URL or mock download
    from unittest.mock import patch
    class DummyStreamResp:
        status_code = 200
        headers = {'content-length': str(os.path.getsize(dummy_zip_path))}
        def iter_content(self, chunk_size=65536):
            with open(dummy_zip_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    yield chunk
        def raise_for_status(self): pass

    with patch.object(updater, '_safe_request_get', return_value=DummyStreamResp()):
        batch_path = updater.download_and_prepare_update(
            "https://github.com/GurpinarSG/NovaCare/releases/download/v1.2.5/NovaCare_Update.zip",
            new_version="1.2.5"
        )
        assert os.path.exists(batch_path), "apply_update.bat must exist"
        ps1_path = batch_path.replace(".bat", ".ps1")
        assert os.path.exists(ps1_path), "apply_update.ps1 must exist"

        with open(ps1_path, "r", encoding="utf-8") as pf:
            ps1_text = pf.read()
        assert "$version = '1.2.5'" in ps1_text
        assert "NovaCare.exe" in ps1_text
        assert "$($_.FullName)" in ps1_text or "($_.FullName)" in ps1_text

    try:
        os.remove(dummy_zip_path)
    except Exception:
        pass
    print("  [✔] download_and_prepare_update script generation and syntax verified.")

def test_update_mode_persistence():
    print("[10/10] Testing update_mode configuration persistence...")
    cfg = ConfigManager()
    orig_mode = cfg.get("update_mode", "release")
    try:
        cfg.set("update_mode", "branch")
        assert cfg.get("update_mode") == "branch"
        # Simulate new ConfigManager reload
        loaded_settings = cfg._load()
        assert loaded_settings.get("update_mode") == "branch", "update_mode 'branch' must persist across loads"
    finally:
        cfg.set("update_mode", orig_mode)
    print("  [✔] update_mode configuration correctly persists.")

if __name__ == "__main__":
    print("=" * 65)
    print("  NovaCare Public Auto-Updater & Credential Decoupling Tests")
    print("=" * 65)
    test_security_cleanliness()
    test_config_token_resolution()
    test_unauthenticated_release_check()
    test_unauthenticated_branch_check()
    test_invalid_token_resilience()
    test_unauthenticated_download_stream()
    test_recursion_guard_on_404()
    test_version_parsing_edge_cases()
    test_download_and_prepare_update_pipeline()
    test_update_mode_persistence()
    print("\n" + "=" * 65)
    print("  ALL 10 PUBLIC UPDATER TESTS PASSED PERFECTLY!")
    print("=" * 65)

