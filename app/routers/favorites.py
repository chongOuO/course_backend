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
@router.get("", response_model=list[FavoriteCourseOut])
def list_my_favorites(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # 1) 先拿收藏的 course_id 清單
    fav_rows = db.query(Favorite.course_id).filter(Favorite.user_id == user.id).all()
    course_ids = [r[0] for r in fav_rows]
    if not course_ids:
        return []

    # 2) 一次查課程 + 老師 + 系所
    rows = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.name.label("department_name"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
        .filter(Course.id.in_(course_ids))
        .order_by(Course.semester.desc().nullslast(), Course.id.asc())
        .all()
    )

    # 3) 再一次把所有課程的時間抓回來（避免在迴圈 query N 次）
    time_rows = (
        db.query(CourseTime)
        .filter(CourseTime.course_id.in_(course_ids))
        .order_by(CourseTime.weekday.asc(), CourseTime.start_section.asc())
        .all()
    )
    times_map: dict[str, list[CourseTime]] = {}
    for t in time_rows:
        times_map.setdefault(t.course_id, []).append(t)

    # 4) 組回傳
    result: list[FavoriteCourseOut] = []
    for course, teacher_name, department_name in rows:
        result.append(
            FavoriteCourseOut(
                course_id=course.id,
                semester=course.semester,
                department_id=course.department_id,
                department_name=department_name,
                grade=course.grade,
                class_group=course.class_group,
                name_zh=course.name_zh,
                teacher_name=teacher_name,
                limit_max=course.limit_max,
                credit=course.credit,
                required_type=course.required_type,
                time_text=format_times(times_map.get(course.id, [])),
                is_favorite=True,
            )
        )

    return result


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
