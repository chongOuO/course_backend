# app/routers/favorites.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.favorite import Favorite
from app.models.course import Course
from app.utils.auth import get_current_user
from app.models.course_time import CourseTime
from app.schemas.favorite import FavoriteCourseOut

from app.models.teacher import Teacher
from app.models.department import Department

from sqlalchemy import and_, func, cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import exists, tuple_
from sqlalchemy.dialects.postgresql import aggregate_order_by

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/favorites", tags=["Favorites"])

router = APIRouter(prefix="/favorites", tags=["Favorites"])

WEEKDAY_MAP = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}

def format_times(times: list[CourseTime]) -> str | None:
    """
    把多筆 CourseTime 轉成前端好顯示的節次字串
    e.g. 週一 2-4 A101；週三 5-6 B201
    """
    if not times:
        return None

    parts = []
    for t in times:
        wd = WEEKDAY_MAP.get(t.weekday, str(t.weekday))
        # 節次顯示：單節 or 範圍
        if t.start_section == t.end_section:
            sec = f"{t.start_section}"
        else:
            sec = f"{t.start_section}-{t.end_section}"
        room = f" {t.classroom}" if t.classroom else ""
        parts.append(f"週{wd} {sec}{room}")

    # 去重 + 保持順序
    seen = set()
    uniq = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)

    return "；".join(uniq)



# 收藏課程
@router.post("/{course_id}")
def add_favorite(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")

    exists = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.course_id == course_id
    ).first()

    if exists:
        raise HTTPException(400, "Already in favorites")

    fav = Favorite(user_id=user.id, course_id=course_id)
    db.add(fav)
    db.commit()
    return {"message": "Added to favorites"}


# 查看收藏
@router.get("")
def list_my_favorites(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    # 如果你也要分頁，可以保留
    page: int = 1,
    page_size: int = 200,
):
    # times 聚合（跟搜尋一模一樣）
    times_sq = (
        db.query(
            CourseTime.course_id.label("cid"),
            func.coalesce(
                func.jsonb_agg(
                    aggregate_order_by(
                        func.jsonb_build_object(
                            "weekday", CourseTime.weekday,
                            "start_section", CourseTime.start_section,
                            "end_section", CourseTime.end_section,
                            "classroom", CourseTime.classroom,
                        ),
                        tuple_(CourseTime.weekday, CourseTime.start_section),
                    )
                ),
                cast("[]", JSONB),
            ).label("times"),
        )
        .group_by(CourseTime.course_id)
        .subquery()
    )

    # 只列出「我的收藏」：JOIN favorites
    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            times_sq.c.times.label("times"),
        )
        .join(Favorite, and_(Favorite.course_id == Course.id, Favorite.user_id == user.id))
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
        .outerjoin(times_sq, times_sq.c.cid == Course.id)
    )

    total = q.count()

    rows = (
        q.order_by(Course.semester.desc().nullslast(), Course.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for course, teacher_name, dept_id, dept_name, times in rows:
        items.append({
            "id": course.id,
            "name_zh": course.name_zh,
            "name_en": course.name_en,
            "semester": course.semester,
            "grade": course.grade,
            "required_type": course.required_type,
            "category": course.category,

            "department_id": dept_id,
            "department_name": dept_name,

            "teacher_id": course.teacher_id,
            "teacher_name": teacher_name,
            "credit": course.credit,
            "class_group": course.class_group,
            "group_code": course.group_code,
            "limit_min": course.limit_min,
            "limit_max": course.limit_max,
            "raw_remark": course.raw_remark,

            "is_favorite": True,     
            "times": times or [],
        })

    return {"page": page, "page_size": page_size, "total": total, "items": items}


# 移除收藏
@router.delete("/{course_id}")
def remove_fav(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    fav = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.course_id == course_id
    ).first()

    if not fav:
        raise HTTPException(404, "Favorite not found")

    db.delete(fav)
    db.commit()
    return {"message": "Removed"}
