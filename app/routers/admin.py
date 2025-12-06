import pandas as pd
from pathlib import Path
from typing import Optional, Literal

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.utils.auth import get_current_user

from app.models.course import Course
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.course_time import CourseTime


from app.models.user import User
from app.models.student_profile import StudentProfile


from app.utils.hashing import hash_password as get_password_hash

from datetime import datetime
from typing import Optional

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/admin", tags=["Admin"])


#管理者驗證
def require_admin(user=Depends(get_current_user)):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


#excel匯入功能
def to_str(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return None if s == "" or s.lower() == "nan" else s


def to_int(v):
    if pd.isna(v):
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def parse_sections(text):
    # "2,3,4" -> (2,4)
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None, None
    try:
        parts = [int(str(x).strip()) for x in str(text).split(",") if str(x).strip() != ""]
        if not parts:
            return None, None
        return min(parts), max(parts)
    except Exception:
        return None, None


def find_header_row(df_raw: pd.DataFrame) -> int:
    # 找到包含「科目代碼(新碼全碼)」的那一列當表頭
    target = "科目代碼(新碼全碼)"
    for i in range(min(30, len(df_raw))):
        row = df_raw.iloc[i].astype(str).tolist()
        if any(target in cell for cell in row):
            return i
    return -1


#匯入課程api
@router.post("/import")
def import_courses(
    file: UploadFile = File(...),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        df_raw = pd.read_excel(file.file, header=None)
        header_i = find_header_row(df_raw)
        if header_i == -1:
            raise HTTPException(status_code=400, detail="Cannot find header row in Excel")

        header = df_raw.iloc[header_i].tolist()
        df = df_raw.iloc[header_i + 1:].copy()
        df.columns = [str(c).strip() for c in header]
        df = df.reset_index(drop=True)

        # 先準備 departments / teachers
        dept_ids = set()
        teachers = {}  # teacher_id -> name

        for _, row in df.iterrows():
            dept_id = to_str(row.get("系所代碼"))
            if dept_id:
                dept_ids.add(dept_id)

            teacher_id = to_str(row.get("主開課教師代碼(舊碼)")) or to_str(row.get("授課教師代碼(舊碼)"))
            teacher_name = to_str(row.get("主開課教師姓名")) or to_str(row.get("授課教師姓名"))
            if teacher_id:
                teachers[teacher_id] = teacher_name or "unknown"

        # 插入 departments
        for dept_id in dept_ids:
            exists = db.query(Department.id).filter(Department.id == dept_id).first()
            if not exists:
                db.add(Department(id=dept_id, name=""))  # 沒有系所名稱就先空字串

        # 插入 teachers
        for tid, tname in teachers.items():
            exists = db.query(Teacher.id).filter(Teacher.id == tid).first()
            if not exists:
                db.add(Teacher(id=tid, name=tname))

        db.commit()  # 先確保 FK 都存在

        # 匯入 courses / course_time 
        inserted_courses = 0
        inserted_times = 0

        for _, row in df.iterrows():
            course_id = to_str(row.get("科目代碼(新碼全碼)"))
            if not course_id:
                continue

            # 只查 id，避免重複插入
            if db.query(Course.id).filter(Course.id == course_id).first():
                continue

            dept_id = to_str(row.get("系所代碼")) or "unknown"
            teacher_id = (
                to_str(row.get("主開課教師代碼(舊碼)"))
                or to_str(row.get("授課教師代碼(舊碼)"))
                or "unknown"
            )

            course = Course(
                id=course_id,
                name_zh=to_str(row.get("科目中文名稱")) or "",
                name_en=to_str(row.get("科目英文名稱")),
                department_id=dept_id,
                teacher_id=teacher_id,
                grade=to_int(row.get("年級")),
                class_group=to_str(row.get("上課班組")),
                group_code=to_str(row.get("科目組別")),
                credit=to_int(row.get("學分數")) or 0,
                required_type=to_str(row.get("課別名稱")),
                category=to_str(row.get("課別代碼")),
                limit_max=to_int(row.get("上課人數")),
                chinese_summary=to_str(row.get("課程中文摘要")),
                english_summary=to_str(row.get("課程英文摘要")),
                raw_remark=to_str(row.get("課表備註")),
                semester=to_str(row.get("學期")),
            )
            db.add(course)
            inserted_courses += 1

            weekday = to_int(row.get("上課星期"))
            sections = to_str(row.get("上課節次"))
            classroom = to_str(row.get("上課地點"))

            if weekday is not None and sections:
                start, end = parse_sections(sections)
                if start is not None and end is not None:
                    db.add(
                        CourseTime(
                            course_id=course_id,
                            weekday=weekday,
                            start_section=start,
                            end_section=end,
                            classroom=classroom,
                        )
                    )
                    inserted_times += 1

        db.commit()
        return {
            "message": "Import completed!",
            "inserted_courses": inserted_courses,
            "inserted_times": inserted_times,
        }

    except Exception:
        db.rollback()
        raise


#使用者管理
Role = Literal["admin", "student"]


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    # profile（可能為 None）
    student_no: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None

class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserCreateIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=72)  
    role: Role = "student"
    student_no: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class AdminUserUpdateIn(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=72)


def _to_out(u: User, p: Optional[StudentProfile]) -> AdminUserOut:
    return AdminUserOut(
        id=u.id,
        username=u.username,
        role=getattr(u, "role", "student"),
        is_active=getattr(u, "is_active", True),
        student_no=getattr(p, "student_no", None),
        full_name=getattr(p, "full_name", None),
        email=getattr(p, "email", None),
        phone=getattr(p, "phone", None),
        avatar_url=getattr(p, "avatar_url", None),
        last_login_at=getattr(p, "last_login_at", None),
    )


@router.get("/users", response_model=AdminUserListOut)
def admin_list_users(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),

    name: Optional[str] = Query(None, description="姓名 full_name"),
    student_no: Optional[str] = Query(None, description="學號 student_no"),
    department: Optional[str] = Query(None, description="系所 department (name or code)"),
    email: Optional[str] = Query(None, description="Email"),


    keyword: Optional[str] = Query(None, description="模糊搜尋 username / student_no / full_name / department / email"),


    role: Optional[str] = Query(None, description="admin/student"),
    is_active: Optional[bool] = Query(None),

    # 分頁
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = db.query(User).outerjoin(StudentProfile, StudentProfile.user_id == User.id)

    if name:
        q = q.filter(StudentProfile.full_name.ilike(f"%{name}%"))

    if student_no:
        q = q.filter(StudentProfile.student_no.ilike(f"%{student_no}%"))

    if department:
        q = q.filter(StudentProfile.department.ilike(f"%{department}%"))

    if email:
        q = q.filter(StudentProfile.email.ilike(f"%{email}%"))

    # keyword模糊搜尋
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                User.username.ilike(like),
                StudentProfile.student_no.ilike(like),
                StudentProfile.full_name.ilike(like),
                StudentProfile.department.ilike(like),
                StudentProfile.email.ilike(like),
            )
        )

    if role:
        q = q.filter(User.role == role)

    if is_active is not None:
        q = q.filter(User.is_active.is_(is_active))

    total = q.count()

    users = (
        q.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_ids = [u.id for u in users]
    profs = db.query(StudentProfile).filter(StudentProfile.user_id.in_(user_ids)).all()
    prof_map = {p.user_id: p for p in profs}

    items = [_to_out(u, prof_map.get(u.id)) for u in users]
    return AdminUserListOut(items=items, total=total, page=page, page_size=page_size)



@router.get("/users/{user_id}", response_model=AdminUserOut)
def admin_get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    p = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    return _to_out(u, p)




@router.put("/users/{user_id}", response_model=AdminUserOut)
def admin_update_user(
    user_id: int,
    body: AdminUserUpdateIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    data = body.model_dump(exclude_unset=True)

    if "role" in data and data["role"] is not None:
        u.role = data["role"]

    if "is_active" in data and data["is_active"] is not None:
        u.is_active = data["is_active"]

    p = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
    if not p:
        # 確保 profile 存在
        p = StudentProfile(user_id=user_id, student_no=u.username)
        db.add(p)

    for k in ["full_name", "email", "phone", "avatar_url"]:
        if k in data:
            setattr(p, k, data[k])

    db.commit()
    db.refresh(u)
    db.refresh(p)
    return _to_out(u, p)


@router.patch("/users/{user_id}/password")
def admin_reset_password(
    user_id: int,
    body: AdminResetPasswordIn,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    u.password_hash = get_password_hash(body.new_password)
    db.commit()
    return {"detail": "password updated"}


@router.patch("/users/{user_id}/deactivate")
def admin_deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.is_active = False
    db.commit()
    return {"detail": "deactivated"}


@router.patch("/users/{user_id}/activate")
def admin_activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    u.is_active = True
    db.commit()
    return {"detail": "activated"}
