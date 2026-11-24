"""
Authentification à deux facteurs TOTP (RFC 6238) native sans dépendance externe.
Compatible Google Authenticator, Microsoft Authenticator, Authy, FreeOTP.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse
from django.contrib.auth.hashers import check_password, make_password


def generate_totp_secret(length_bytes: int = 20) -> str:
    """Génère un secret Base32 aléatoire cryptographiquement sûr (160 bits)."""
    raw = secrets.token_bytes(length_bytes)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def _totp_at(secret: str, for_time: int, period: int = 30, digits: int = 6) -> str:
    padded = secret.strip().replace(" ", "").upper()
    pad_len = (8 - len(padded) % 8) % 8
    key = base64.b32decode(padded + "=" * pad_len, casefold=True)
    counter = int(for_time // period)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)


def generate_totp_code(secret: str, for_time: int | None = None) -> str:
    """Calcule le code TOTP courant à 6 chiffres (utile pour la vérification et les tests)."""
    ts = int(time.time()) if for_time is None else int(for_time)
    return _totp_at(secret, ts)


def verify_totp_code(secret: str, code: str, window: int = 1, now: int | None = None) -> bool:
    """Vérifie un code TOTP à 6 chiffres avec tolérance d'horloge (±window * 30s)."""
    if not secret or not code:
        return False
    clean = str(code).strip().replace(" ", "")
    if not (clean.isdigit() and len(clean) == 6):
        return False
    ts = int(time.time()) if now is None else int(now)
    for delta in range(-window, window + 1):
        expected = _totp_at(secret, ts + delta * 30)
        if hmac.compare_digest(expected, clean):
            return True
    return False


def build_otpauth_uri(secret: str, username: str, issuer: str = "SmartSchool ERP") -> str:
    label = urllib.parse.quote(f"{issuer}:{username}")
    params = urllib.parse.urlencode({
        "secret": secret,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": 6,
        "period": 30,
    })
    return f"otpauth://totp/{label}?{params}"


def generate_backup_codes(count: int = 6) -> tuple[list[str], str]:
    """
    Génère `count` codes de secours lisibles (XXXX-XXXX) et retourne
    (codes_en_clair, chaine_hachee_stockable).
    """
    plain = [f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}" for _ in range(count)]
    hashed = "\n".join(make_password(c) for c in plain)
    return plain, hashed


def consume_backup_code(hashed_blob: str, candidate: str) -> tuple[bool, str]:
    """Vérifie et consomme un code de secours à usage unique."""
    if not hashed_blob or not candidate:
        return False, hashed_blob or ""
    cand = candidate.strip().upper()
    remaining = []
    matched = False
    for line in hashed_blob.splitlines():
        line = line.strip()
        if not line:
            continue
        if not matched and check_password(cand, line):
            matched = True
            continue
        remaining.append(line)
    return matched, "\n".join(remaining)
