
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.simulate import SimulatedSelection
from app.models.course import Course
from app.utils.auth import get_current_user
from app.utils.conflict import is_conflict

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/simulate", tags=["Simulated Selection"])

# 預選課
@router.post("/{course_id}")
def add_simulated(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    new_course = db.query(Course).filter(Course.id == course_id).first()
    if not new_course:
        raise HTTPException(404, "Course not found")

    # 取得使用者目前預選課
    selected = db.query(SimulatedSelection).filter(
        SimulatedSelection.user_id == user.id
    ).all()

    selected_courses = [db.query(Course).filter(Course.id == s.course_id).first() for s in selected]

    # 整理時段
    existing_times = []
    for c in selected_courses:
        existing_times.extend(c.times)

    new_times = new_course.times

    if is_conflict(existing_times, new_times):
        raise HTTPException(400, "Time conflict")

    # 寫入預選
    entry = SimulatedSelection(user_id=user.id, course_id=course_id)
    db.add(entry)
    db.commit()
    return {"message": "Added to simulated selection"}


# 查看預選課
@router.get("/")
def list_simulated(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(SimulatedSelection).filter(SimulatedSelection.user_id == user.id).all()


# 移除預選
@router.delete("/{course_id}")
def remove_simulated(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(SimulatedSelection).filter(
        SimulatedSelection.user_id == user.id,
        SimulatedSelection.course_id == course_id
    ).first()

    if not s:
        raise HTTPException(404, "Not found")

    db.delete(s)
    db.commit()
    return {"message": "Removed from simulated selection"}
