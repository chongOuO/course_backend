
from passlib.context import CryptContext
from fastapi import HTTPException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _check_bcrypt_len(password: str):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (bcrypt max 72 bytes)")

def hash_password(password: str):
    _check_bcrypt_len(password)
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    _check_bcrypt_len(plain_password)
    return pwd_context.verify(plain_password, hashed_password)
