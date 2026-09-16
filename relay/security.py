import base64
import hashlib
import hmac
import secrets

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def new_token() -> str:
    return secrets.token_urlsafe(32)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(result).decode()

def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, expected = stored.split('$')
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False

