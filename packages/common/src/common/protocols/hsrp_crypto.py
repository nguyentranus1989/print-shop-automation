"""AES-128-CBC crypto helpers for the HSRP protocol.

Key: b"Hs_Encrypt" padded to 16 bytes with null bytes.
IV:  16 zero bytes.
"""

from __future__ import annotations

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# AES key: "Hs_Encrypt" padded to 16 bytes with null bytes
AES_KEY = b"Hs_Encrypt\x00\x00\x00\x00\x00\x00"
AES_IV = b"\x00" * 16


def encrypt(plaintext: bytes) -> bytes:
    """AES-128-CBC encrypt with PKCS7 padding."""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(plaintext, AES.block_size))


def decrypt(ciphertext: bytes) -> bytes:
    """AES-128-CBC decrypt and strip PKCS7 padding."""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return unpad(cipher.decrypt(ciphertext), AES.block_size)
