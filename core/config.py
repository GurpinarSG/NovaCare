"""
NovaCare System Suite - Configuration & Settings Manager
Persists user preferences, updater settings, and application metadata.
Cryptographically protects GitHub tokens using Windows DPAPI.
"""
import os
import json
from core.security import encrypt_string, decrypt_string

CURRENT_VERSION = "1.0.0"
DEFAULT_GITHUB_REPO = "GurpinarSG/NovaCare"
DEFAULT_GITHUB_TOKEN = "" # NEVER hardcode tokens in distributed code
DEFAULT_BRANCH = "main"
DEFAULT_COMMIT_SHA = "3cfb6bd"

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

    def _get_defaults(self) -> dict:
        return {
            "version": CURRENT_VERSION,
            "github_repo": DEFAULT_GITHUB_REPO,
            "update_mode": "branch",       # "branch" (anında klasör/commit takibi) or "release"
            "target_branch": DEFAULT_BRANCH,
            "local_commit_sha": DEFAULT_COMMIT_SHA,
            "auto_check_updates": True,
            "autostart_on_boot": True,
            "notify_on_update": True,
            "last_update_check": "",
            "minimize_to_tray": True,
            "close_to_tray": False,
            "auto_backup_registry": True
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
                return data
        except Exception:
            return defaults

    def _save(self, data: dict):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self.settings.get(key, default)

    def set(self, key: str, value):
        self.settings[key] = value
        self._save(self.settings)

    def get_secure_token(self) -> str:
        """Returns the decrypted GitHub token for the current Windows user."""
        # 1. Check encrypted token
        enc_token = self.settings.get("github_token_encrypted")
        if enc_token:
            dec = decrypt_string(enc_token)
            if dec:
                return dec

        # 2. Migration from legacy plaintext if present
        plain = self.settings.get("github_token")
        if plain:
            # Upgrade to encrypted
            self.set_secure_token(plain)
            return plain

        return ""

    def set_secure_token(self, token: str):
        """Encrypts and stores token securely using Windows DPAPI."""
        if token:
            enc = encrypt_string(token.strip())
            self.settings["github_token_encrypted"] = enc
            # Remove any plaintext token key
            self.settings.pop("github_token", None)
        else:
            self.settings.pop("github_token_encrypted", None)
            self.settings.pop("github_token", None)
        self._save(self.settings)

    def save_all(self):
        self._save(self.settings)
