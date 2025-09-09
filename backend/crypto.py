import os, time, json, base64, hmac, hashlib


def hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120_000, dklen=32)
    return base64.urlsafe_b64encode(salt + dk).decode()


def verify_password(password: str, stored: str) -> bool:
    raw = base64.urlsafe_b64decode(stored.encode())
    salt, dk = raw[:16], raw[16:]
    test = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120_000, dklen=32)
    return hmac.compare_digest(dk, test)


def create_token(payload: dict, secret: str, expire_seconds: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {**payload, "exp": now + expire_seconds, "iat": now}
    enc = lambda b: base64.urlsafe_b64encode(json.dumps(b, separators=(',', ':')).encode()).rstrip(b'=')
    signing_input = enc(header) + b'.' + enc(payload)
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b'.' + base64.urlsafe_b64encode(sig).rstrip(b'=')).decode()


def verify_token(token: str, secret: str) -> dict:
    head_b64, pay_b64, sig_b64 = token.split('.')
    signing_input = (head_b64 + '.' + pay_b64).encode()
    sig = base64.urlsafe_b64decode(sig_b64 + '==')
    expect = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expect):
        raise ValueError("bad signature")
    payload = json.loads(base64.urlsafe_b64decode(pay_b64 + '==').decode())
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("expired")
    return payload

