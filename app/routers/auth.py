
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import hashlib
from datetime import datetime, timedelta
import secrets
from app.database import get_db
from app.utils.hashing import hash_password, verify_password
from app.utils.auth import create_access_token, get_current_user
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.models.user import User
from fastapi.security import OAuth2PasswordRequestForm

from datetime import datetime, timezone
from app.models.student_profile import StudentProfile

from app.schemas.change_password import ChangePasswordIn
from app.models.password_reset_token import PasswordResetToken
from app.schemas.password_reset import ForgotPasswordIn, ResetPasswordIn


import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/auth", tags=["Auth"])

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

RESET_TTL_MINUTES = 15


# 註冊
@router.post("/register", response_model=UserOut)
def register(user_data: UserCreate, db: Session = Depends(get_db)):

    exists = db.query(User).filter(User.username == user_data.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role="student"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# 登入
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid credentials")
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if profile is None:
        profile = StudentProfile(user_id=user.id, student_no=user.username)  
        db.add(profile)

    profile.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# 取得使用者資料
@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    username = body.username.strip()

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 產生一次性 token
    raw_token = secrets.token_urlsafe(32)
    token_hash = sha256(raw_token)

    expires_at = datetime.utcnow() + timedelta(minutes=RESET_TTL_MINUTES)

    row = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    if row:
        row.token_hash = token_hash
        row.expires_at = expires_at
        row.used_at = None
    else:
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        ))

    db.commit()

    #  測試用：直接回傳 token
    return {
        "detail": "reset token generated",
        "username": username,
        "token": raw_token,
        "expires_in_minutes": RESET_TTL_MINUTES,
    }


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    
    if len(body.new_password.encode("utf-8")) > 72:
        raise HTTPException(stadtus_code=400, detail="Passwor too long (max 72 bytes for bcrypt).")

    user = db.query(User).filter(User.username == body.username.strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    row = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).first()
    if not row:
        raise HTTPException(status_code=400, detail="No reset token. Call /auth/forgot-password first.")

    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")

    if row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token expired")

    if row.token_hash != sha256(body.token):
        raise HTTPException(status_code=400, detail="Invalid token")

    #  通過驗證，重設密碼
    user.password_hash = hash_password(body.new_password)
    row.used_at = datetime.utcnow()

    db.commit()
    return {"detail": "Password reset"}