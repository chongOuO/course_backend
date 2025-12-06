
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.hashing import hash_password, verify_password
from app.utils.auth import create_access_token, get_current_user
from app.schemas.user import UserCreate, UserLogin, UserOut
from app.models.user import User
from fastapi.security import OAuth2PasswordRequestForm

from datetime import datetime, timezone
from app.models.student_profile import StudentProfile

from app.schemas.change_password import ChangePasswordIn



import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/auth", tags=["Auth"])


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
        profile = StudentProfile(user_id=user.id, student_no=user.username)  # 視你的欄位調整
        db.add(profile)

    profile.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# 取得使用者資料
@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    
    if len(body.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes for bcrypt).")

    db_user = db.query(User).filter(User.id == user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.old_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    db_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"detail": "Password changed"}