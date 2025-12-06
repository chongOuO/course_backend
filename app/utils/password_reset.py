import secrets
import hashlib

def generate_reset_token() -> str:
    # 產生給使用者的原始 token（只會顯示一次）
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    # DB 存 hash，避免 DB 外洩直接拿到 token
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
