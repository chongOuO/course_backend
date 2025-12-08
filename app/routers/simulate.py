
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.simulate import SimulatedSelection
from app.models.course import Course
from app.utils.auth import get_current_user
from app.utils.conflict import is_conflict
from app.schemas.simulate import BulkSimulateIn

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/simulate", tags=["Simulated Selection"])


@router.post("/bulk")
def bulk_add_simulated(
    body: BulkSimulateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # 0) 去重
    course_ids = list(dict.fromkeys([c.strip() for c in body.course_ids if c and c.strip()]))
    if not course_ids:
        raise HTTPException(400, "course_ids is empty")

    # 1) 取出目前預選
    existing = db.query(SimulatedSelection).filter(SimulatedSelection.user_id == user.id).all()
    existing_ids = [s.course_id for s in existing]

    # replace = True 代表這次選的要覆蓋原本的
    if body.replace:
        existing_ids = []

    # 2) 一次把涉及到的課都查出來（含 times）
    all_need_ids = list(dict.fromkeys(existing_ids + course_ids))
    courses = db.query(Course).filter(Course.id.in_(all_need_ids)).all()
    course_map = {c.id: c for c in courses}

    # 3) 檢查課程是否存在
    not_found = [cid for cid in course_ids if cid not in course_map]
    if not_found:
        raise HTTPException(404, {"message": "Course not found", "course_ids": not_found})

    # 4) 整理「目前預選」的時間（用來跟新加的比）
    existing_times = []
    for cid in existing_ids:
        c = course_map.get(cid)
        if c:
            existing_times.extend(c.times)

    # 5) 新增時：也要檢查新加的彼此衝堂，所以用 running_times 累加
    running_times = list(existing_times)
    to_insert = []

    for cid in course_ids:
        # 已經在預選就跳過（避免重複）
        if cid in existing_ids:
            continue

        new_course = course_map[cid]
        new_times = new_course.times

        if is_conflict(running_times, new_times):
            raise HTTPException(400, {"message": "Time conflict", "conflict_course_id": cid})

        to_insert.append(SimulatedSelection(user_id=user.id, course_id=cid))
        running_times.extend(new_times)

    # 6) 寫入 DB（只 commit 一次）
    if body.replace:
        db.query(SimulatedSelection).filter(SimulatedSelection.user_id == user.id).delete(synchronize_session=False)

    db.add_all(to_insert)
    db.commit()

    return {
        "message": "Bulk added to simulated selection",
        "inserted": len(to_insert),
        "skipped_existing": len([cid for cid in course_ids if cid in existing_ids]),
        "total_after": db.query(SimulatedSelection).filter(SimulatedSelection.user_id == user.id).count(),
    }

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



@router.delete("")
def clear_simulated(db: Session = Depends(get_db), user=Depends(get_current_user)):
    deleted = (
        db.query(SimulatedSelection)
        .filter(SimulatedSelection.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"message": "Cleared", "deleted": deleted}

