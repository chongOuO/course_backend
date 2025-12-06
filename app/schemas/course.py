
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.department import Department

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.get("")
def list_courses(
    db: Session = Depends(get_db),

    
    keyword: Optional[str] = Query(None, description="課程名稱關鍵字（中/英）"),
    semester: Optional[str] = Query(None, description="學期，例如 1141"),
    program: Optional[str] = Query(None, description="學制（目前DB沒有，先保留參數）"),
    required_type: Optional[str] = Query(None, description="課別，例如 專業必修(系所)"),
    grade: Optional[int] = Query(None, description="年級"),
    teacher: Optional[str] = Query(None, description="教師（可用教師代碼或姓名關鍵字）"),
    category: Optional[str] = Query(None, description="課程分類/課別代碼"),
    department: Optional[str] = Query(None, description="系所代碼"),

    # 分頁
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    q = (
        db.query(Course, Teacher.name.label("teacher_name"), Department.name.label("department_name"))
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
    )

    # 搜尋中文或英文課名
    if keyword:
        k = f"%{keyword.strip()}%"
        q = q.filter(or_(Course.name_zh.ilike(k), Course.name_en.ilike(k)))

    # 學期
    if semester:
        q = q.filter(Course.semester == semester)

    # 課別
    if required_type:
        q = q.filter(Course.required_type == required_type)

    # 年級
    if grade is not None:
        q = q.filter(Course.grade == grade)

    # 課程分類
    if category:
        q = q.filter(Course.category == category)

    # 系所
    if department:
        q = q.filter(Course.department_id == department)

    # 允許用教師代碼或姓名模糊搜尋
    if teacher:
        t = teacher.strip()
        if t:
            q = q.filter(or_(Course.teacher_id == t, Teacher.name.ilike(f"%{t}%")))


    total = q.count()

    items = (
        q.order_by(Course.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 組回傳格式
    results = []
    for course, teacher_name, dept_name in items:
        results.append({
            "id": course.id,
            "name_zh": course.name_zh,
            "name_en": course.name_en,
            "semester": course.semester,
            "grade": course.grade,
            "required_type": course.required_type,
            "category": course.category,
            "department_id": course.department_id,
            "department_name": dept_name,
            "teacher_id": course.teacher_id,
            "teacher_name": teacher_name,
            "credit": course.credit,
            "class_group": course.class_group,
            "group_code": course.group_code,
            "limit_min": course.limit_min,
            "limit_max": course.limit_max,
            "raw_remark": course.raw_remark,
        })

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": results,
    }
