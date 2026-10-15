"""
NovaCare System Suite - Security & Cryptographic Storage
Protects sensitive credentials (such as GitHub PAT) using Windows Data Protection API (DPAPI).
Tokens are tied to the current Windows user login and cannot be decrypted on other computers.
"""
import ctypes
from ctypes import wintypes

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_byte))
    ]

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
            res = ctypes.string_at(out_blob.pbData, out_blob.cbData).hex()
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return res
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
            res = ctypes.string_at(out_blob.pbData, out_blob.cbData).decode('utf-8')
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
            return res
    except Exception:
        pass
    return ""

def mask_token(token: str) -> str:
    """Returns safe masked preview e.g. ghp_SWkd••••••••9rp"""
    if not token:
        return ""
    if len(token) <= 10:
        return "••••••••"
    return f"{token[:8]}••••••••••••••••••••{token[-4:]}"
