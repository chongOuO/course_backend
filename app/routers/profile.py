from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
import uuid

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.student_profile import StudentProfile
from app.schemas.profile import ProfileOut, ProfileUpdateIn
from app.models.department import Department
from app.models.user import User
import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/students", tags=["Students"])

STATIC_DIR = Path("static")
AVATAR_DIR = STATIC_DIR / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 2 * 1024 * 1024 


def _ensure_student_profile(db: Session, user_id: int, username: str) -> StudentProfile:
    prof = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if prof:
        return prof

    # 這裡需要你決定 student_no 從哪來：
    # - 若你 users 裡有 student_no，就用那個
    # - 沒有的話：暫用 username 當學號
    prof = StudentProfile(user_id=user_id, student_no=username)
    db.add(prof)
    db.commit()
    db.refresh(prof)
    return prof


@router.get("/me", response_model=ProfileOut)
def get_my_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    prof = _ensure_student_profile(db, user.id, getattr(user, "username", str(user.id)))

    
    row = (
        db.query(User.department_id, Department.name)
        .outerjoin(Department, Department.id == User.department_id)
        .filter(User.id == user.id)
        .first()
    )

    dept_id = row[0] if row else None
    dept_name = row[1] if row else None

    base = ProfileOut.model_validate(prof, from_attributes=True)
    return base.model_copy(update={
        "department_id": dept_id,
        "department_name": dept_name,
    })


@router.put("/me", response_model=ProfileOut)
def update_my_profile(body: ProfileUpdateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    prof = _ensure_student_profile(db, user.id, getattr(user, "username", str(user.id)))

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(prof, k, v)

    db.commit()
    db.refresh(prof)
    return prof


@router.post("/me/avatar", response_model=ProfileOut)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    prof = _ensure_student_profile(db, user.id, getattr(user, "username", str(user.id)))

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Only {sorted(ALLOWED_EXT)} are allowed")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    filename = f"{user.id}_{uuid.uuid4().hex}{suffix}"
    save_path = AVATAR_DIR / filename
    save_path.write_bytes(content)

    # 讓前端可直接顯示
    prof.avatar_url = f"/static/avatars/{filename}"

    db.commit()
    db.refresh(prof)
    return prof
