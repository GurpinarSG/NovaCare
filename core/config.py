"""
NovaCare System Suite - Configuration & Settings Manager
Persists user preferences, updater settings, and application metadata.
Cryptographically protects GitHub tokens using Windows DPAPI.
"""
import os
import sys
import json
from core.security import encrypt_string, decrypt_string, get_embedded_token

import re

def parse_version_content(content: str) -> tuple[str, str]:
    """
    Parses VERSION file content, returning (version_number, update_notes).
    Supports:
    - Pure version: '1.0.5'
    - Multi-line with notes:
        1.0.5
        ---
        • Akıllı çerez kalkanı eklendi
        • Pil sağlığı raporlayıcı entegre edildi
    - Variations like 'v1.0.5', '[v1.0.5]', 'VERSION = 1.0.5'
    """
    lines = content.strip().splitlines()
    if not lines:
        return "1.0.0", ""
    first_line = lines[0].strip()
    m = re.search(r'(\d+\.\d+(?:\.\d+)?)', first_line)
    if m:
        ver = m.group(1)
    else:
        ver = first_line.lstrip("vV").strip() or "1.0.0"

    notes_lines = lines[1:]
    while notes_lines and notes_lines[0].strip() in ('---', '===', '***', '###', ''):
        notes_lines.pop(0)
    notes = "\n".join(notes_lines).strip()
    return ver, notes

def load_version_and_notes() -> tuple[str, str]:
    """Reads both version number and update notes from VERSION file."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        v_path = os.path.join(base_dir, "VERSION")
        if os.path.exists(v_path):
            with open(v_path, "r", encoding="utf-8") as vf:
                return parse_version_content(vf.read())
    except Exception:
        pass
    return "1.0.0", ""

def load_base_version() -> str:
    """Reads clean base version string from VERSION file (e.g. '1.0.5')."""
    ver, _ = load_version_and_notes()
    return ver

CURRENT_VERSION = load_base_version()
DEFAULT_GITHUB_REPO = "GurpinarSG/NovaCare"
DEFAULT_GITHUB_TOKEN = "" # NEVER hardcode tokens in distributed code
DEFAULT_BRANCH = "main"
DEFAULT_COMMIT_SHA = "c77c7b8"

class ConfigManager:
    def __init__(self, config_dir: str | None = None):
        if config_dir is None:
            local_app = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
            self.config_dir = os.path.join(local_app, 'NovaCare')
        else:
            self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.settings = self._load()

    def get_version(self) -> str:
        """Returns clean base version string like '1.0.7', prioritizing the highest known version."""
        base_file_ver = load_base_version()
        stored_ver = self.settings.get("version", "").lstrip("vV").strip()
        if not stored_ver:
            return base_file_ver or "1.0.0"
        if not base_file_ver:
            return stored_ver

        try:
            import re
            def to_tuple(v):
                return tuple(int(x) for x in re.findall(r'\d+', v)) or (0, 0, 0)
            if to_tuple(stored_ver) > to_tuple(base_file_ver):
                return stored_ver
        except Exception:
            pass
        return base_file_ver

    def get_display_version(self) -> str:
        """Returns formatted version string for UI display, e.g. 'v1.0.0 (Derleme: c77c7b8)'."""
        base_v = self.get_version()
        mode = self.settings.get("update_mode", "branch")
        sha = self.settings.get("local_commit_sha", "")
        if mode == "branch" and sha:
            return f"v{base_v} (Derleme: {sha[:7]})"
        return f"v{base_v}"

    def get_version_notes(self) -> str:
        """Returns manually written release notes from VERSION file if present."""
        _, notes = load_version_and_notes()
        return notes

    def _get_defaults(self) -> dict:
        return {
            "version": CURRENT_VERSION,
            "github_repo": DEFAULT_GITHUB_REPO,
            "update_mode": "branch",       # "branch" (anında klasör/commit takibi) or "release"
            "target_branch": DEFAULT_BRANCH,
            "local_commit_sha": DEFAULT_COMMIT_SHA,
            "auto_check_updates": True,
            "auto_install_updates": True,
            "theme": "system",             # "system" (Windows uyumlu), "dark", "light"
            "autostart_on_boot": True,
            "autostart_widget_on_boot": False,
            "widget_autostart_prompted": False,
            "notify_on_update": True,
            "last_update_check": "",
            "minimize_to_tray": True,
            "close_to_tray": True,
            "always_run_as_admin": True,
            "auto_backup_registry": True,
            "auto_clean_enabled": True,
            "auto_clean_schedule": "daily",
            "auto_clean_threshold_mb": 1024,
            "auto_clean_junk": True,
            "auto_clean_ram": True,
            "auto_clean_traces": False,
            "auto_clean_notify": True,
            "last_auto_clean_time": "",
            "last_auto_clean_display": "Henüz yapılmadı",
            "last_auto_clean_freed_bytes": 0
        }

    def _load(self) -> dict:
        defaults = self._get_defaults()
        if not os.path.exists(self.config_file):
            self._save(defaults)
            return defaults
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                # Remove any plaintext token legacy leak if present
                if "github_token" in data:
                    data.pop("github_token", None)
                    self._save(data)
                return data
        except Exception:
            return defaults

    def _save(self, data: dict):
        try:
            # Ensure plaintext token is never written to disk
            clean_data = {k: v for k, v in data.items() if k != "github_token"}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value):
        self.settings[key] = value
        self._save(self.settings)

    def get_secure_token(self) -> str:
        """
        Returns the decrypted GitHub token for repository synchronization.
        Prioritizes user override (DPAPI) if defined, otherwise securely unpacks
        the in-memory cryptographic vault. Never exposes token in settings or logs.
        """
        # 1. Custom local user override (DPAPI encrypted)
        enc_token = self.settings.get("github_token_encrypted")
        if enc_token:
            dec = decrypt_string(enc_token)
            if dec:
                return dec

        # 2. Cryptographic in-memory vault (AES/HMAC keystream, cross-machine safe)
        vault_token = get_embedded_token()
        if vault_token:
            return vault_token

        return ""

    def set_secure_token(self, token: str):
        """Encrypts and stores a custom user token securely using Windows DPAPI."""
        embedded = get_embedded_token()
        if token and token.strip() and token.strip() != embedded:
            enc = encrypt_string(token.strip())
            self.settings["github_token_encrypted"] = enc
        else:
            # If empty or matching default embedded vault, clean up settings.json
            self.settings.pop("github_token_encrypted", None)
        self.settings.pop("github_token", None)
        self._save(self.settings)

    def save_all(self):
        self._save(self.settings)
