import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_master_key() -> bytes:
    key = os.getenv('MASTER_KEY', 'change-me-in-production').encode('utf-8')
    return hashlib.sha256(key).digest()


def encrypt_string(plain_text: str) -> str:
    aesgcm = AESGCM(_get_master_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plain_text.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


def decrypt_string(cipher_text: str) -> str:
    raw = base64.b64decode(cipher_text.encode('utf-8'))
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_get_master_key())
    return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
