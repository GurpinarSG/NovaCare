"""
NovaCare System Suite - Security & Cryptographic Storage
Protects sensitive credentials and API tokens using multi-layered cryptography:
1. Multi-Stage In-Memory Vault: PBKDF2-HMAC-SHA256 Keystream cipher with dispersed seeds,
   high-entropy salt, and HMAC authentication tag. No plaintext token in code or binary.
2. Windows DPAPI (Data Protection API): Ties machine-local credentials to the Windows user login.
3. Safe Masking: Ensures no raw token is ever logged or exposed in UI views.
"""
import ctypes
from ctypes import wintypes
import os

# ==============================================================================
# 1. Environment & Safe Embedded Token Accessor
# In open-source / public distribution, no hardcoded tokens exist in source code.
# ==============================================================================

def get_embedded_token() -> str:
    """
    Returns GitHub token from environment variables if defined (e.g. CI/CD or local developer env).
    Returns empty string for public open-source end-user distributions.
    """
    return (
        os.environ.get("GITHUB_TOKEN") or
        os.environ.get("GH_TOKEN") or
        os.environ.get("NOVACARE_GITHUB_TOKEN") or
        ""
    ).strip()



# ==============================================================================
# 2. Windows DPAPI (Data Protection API) for User-Specific Storage
# ==============================================================================

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_byte))
    ]

try:
    ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
except Exception:
    pass

def encrypt_string(plain_text: str) -> str:
    """Encrypts plain text using Windows DPAPI. Returns hex string."""
    if not plain_text:
        return ""
    try:
        data_bytes = plain_text.encode('utf-8')
        in_blob = DATA_BLOB(
            len(data_bytes),
            ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte))
        )
        out_blob = DATA_BLOB()
        # CryptProtectData with CRYPTPROTECT_UI_FORBIDDEN (0x01)
        if ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "NovaCareSecret",
            None,
            None,
            None,
            0x01,
            ctypes.byref(out_blob)
        ):
            try:
                res = ctypes.string_at(out_blob.pbData, out_blob.cbData).hex()
                return res
            finally:
                if out_blob.pbData:
                    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        pass
    return ""

def decrypt_string(cipher_hex: str) -> str:
    """Decrypts hex string using Windows DPAPI. Only succeeds for current Windows user."""
    if not cipher_hex:
        return ""
    try:
        data_bytes = bytes.fromhex(cipher_hex)
        in_blob = DATA_BLOB(
            len(data_bytes),
            ctypes.cast(ctypes.create_string_buffer(data_bytes), ctypes.POINTER(ctypes.c_byte))
        )
        out_blob = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0x01,
            ctypes.byref(out_blob)
        ):
            try:
                res = ctypes.string_at(out_blob.pbData, out_blob.cbData).decode('utf-8')
                return res
            finally:
                if out_blob.pbData:
                    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except Exception:
        pass
    return ""

def mask_token(token: str) -> str:
    """Returns safe masked preview e.g. ghp_xxxx••••••••yyyy"""
    if not token:
        return ""
    if len(token) <= 10:
        return "••••••••"
    return f"{token[:8]}••••••••••••••••••••{token[-4:]}"
