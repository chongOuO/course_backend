from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.utils.auth import get_current_user
from sqlalchemy.exc import IntegrityError
from app.models.course import Course
from app.models.course_time import CourseTime
from app.models.teacher import Teacher
from app.models.department import Department

from app.utils.timeslots import parse_time_slots, compress_slots_to_ranges
from app.schemas.admin_course import (
    AdminCourseCreate, AdminCourseUpdate,
    AdminCourseOut, AdminCourseListOut,
    CourseTimeIn,
)
from app.schemas.admin_course_timegrid import TimeGridUpdate

import logging
logger = logging.getLogger("app.admin")



router = APIRouter(prefix="/admin/courses", tags=["Admin - Courses"])


def require_admin(user=Depends(get_current_user)):
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user




@router.get("/{course_id}", response_model=AdminCourseOut)
def admin_get_course(course_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    return AdminCourseOut.model_validate(c)


@router.post("", response_model=AdminCourseOut)
def admin_create_course(
    body: AdminCourseCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if db.query(Course.id).filter(Course.id == body.id).first():
        raise HTTPException(status_code=400, detail="Course id already exists")
    department_id = body.department_id
    teacher_id = body.teacher_id
    if getattr(body, "department_name", None):
        rows = db.query(Department).filter(Department.name == body.department_name).all()  # ← 改成你的欄位
        if len(rows) == 0:
            raise HTTPException(status_code=400, detail="department_name 找不到對應系所")
        if len(rows) > 1:
            raise HTTPException(status_code=400, detail="department_name 重複，請改用 department_id")
        department_id = rows[0].id

    if getattr(body, "teacher_name", None):
        rows = db.query(Teacher).filter(Teacher.name == body.teacher_name).all()  # ← 改成你的欄位
        if len(rows) == 0:
            raise HTTPException(status_code=400, detail="teacher_name 找不到對應教師")
        if len(rows) > 1:
            raise HTTPException(status_code=400, detail="teacher_name 重複，請改用 teacher_id")
        teacher_id = rows[0].id

    # FK 檢查
    if department_id:
        if not db.query(Department.id).filter(Department.id == department_id).first():
            raise HTTPException(status_code=400, detail="department_id not found")
    if teacher_id:
        if not db.query(Teacher.id).filter(Teacher.id == teacher_id).first():
            raise HTTPException(status_code=400, detail="teacher_id not found")

    c = Course(
        id=body.id,
        name_zh=body.name_zh,
        name_en=body.name_en,
        semester=body.semester,
        department_id=department_id,
        teacher_id=teacher_id,
        
        grade=body.grade,
        class_group=body.class_group,
        group_code=body.group_code,
        credit=body.credit,
        required_type=body.required_type,
        category=body.category,
        limit_min=body.limit_min,
        limit_max=body.limit_max,
        chinese_summary=body.chinese_summary,
        english_summary=body.english_summary,
        raw_remark=body.raw_remark,
    )
    db.add(c)

    # 建立時間
    slots = parse_time_slots(body.time_slots)
    if slots:
        ranges = compress_slots_to_ranges(slots)
        for w, start, end in ranges:
            db.add(CourseTime(
                course_id=body.id,
                weekday=w,
                start_section=start,
                end_section=end,
                classroom=body.classroom,
            ))
    else:
        # 沿用原本的 times
        for t in body.times:
            db.add(CourseTime(
                course_id=body.id,
                weekday=t.weekday,
                start_section=t.start_section,
                end_section=t.end_section,
                classroom=t.classroom,
            ))

    db.commit()
    db.refresh(c)
    return AdminCourseOut.model_validate(c)




@router.put("/{course_id}", response_model=AdminCourseOut)
def admin_update_course(
    course_id: str,
    body: AdminCourseUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    data = body.model_dump(exclude_unset=True)

   
    times_in = data.pop("times", None)         
    time_slots_in = data.pop("time_slots", None)
    classroom_in = data.pop("classroom", None)
    
    if "teacher_name" in data and data["teacher_name"] is not None:
        tname = data.pop("teacher_name")
        row = db.query(Teacher).filter(Teacher.name == tname).all()  
        if len(row) == 0:
            raise HTTPException(status_code=400, detail="teacher_name 找不到對應教師")
        if len(row) > 1:
            raise HTTPException(status_code=400, detail="teacher_name 重複，請改用 teacher_id")
        data["teacher_id"] = row[0].id   

    
    if "department_name" in data and data["department_name"] is not None:
        dname = data.pop("department_name")
        row = db.query(Department).filter(Department.name == dname).all()  
        if len(row) == 0:
            raise HTTPException(status_code=400, detail="department_name 找不到對應系所")
        if len(row) > 1:
            raise HTTPException(status_code=400, detail="department_name 重複，請改用 department_id")
        data["department_id"] = row[0].id
   
    if "department_id" in data and data["department_id"] is not None:
        if not db.query(Department.id).filter(Department.id == data["department_id"]).first():
            raise HTTPException(status_code=400, detail="department_id not found")
    if "teacher_id" in data and data["teacher_id"] is not None:
        if not db.query(Teacher.id).filter(Teacher.id == data["teacher_id"]).first():
            raise HTTPException(status_code=400, detail="teacher_id not found")

    # 更新 Course 基本欄位
    for k, v in data.items():
        setattr(c, k, v)

    #  是否要更新時間：只要 times / time_slots / classroom 有出現，就視為要更新課表
    wants_update_time = (times_in is not None) or (time_slots_in is not None) or (classroom_in is not None)

    if wants_update_time:
        
        db.query(CourseTime).filter(CourseTime.course_id == course_id).delete(synchronize_session=False)

        
        if time_slots_in is not None:
            slots = parse_time_slots(time_slots_in or [])
            ranges = compress_slots_to_ranges(slots)
            for w, start, end in ranges:
                db.add(CourseTime(
                    course_id=course_id,
                    weekday=w,
                    start_section=start,
                    end_section=end,
                    classroom=classroom_in,  
                ))
        elif times_in is not None:
            for t in (times_in or []):
                db.add(CourseTime(
                    course_id=course_id,
                    weekday=t["weekday"] if isinstance(t, dict) else t.weekday,
                    start_section=t["start_section"] if isinstance(t, dict) else t.start_section,
                    end_section=t["end_section"] if isinstance(t, dict) else t.end_section,
                    classroom=(t.get("classroom") if isinstance(t, dict) else t.classroom),
                ))
       

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e.orig))

    db.refresh(c)
    return AdminCourseOut.model_validate(c)



@router.delete("/{course_id}")
def admin_delete_course(
    course_id: str,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    c = db.query(Course).filter(Course.id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    db.query(CourseTime).filter(CourseTime.course_id == course_id).delete()
    db.delete(c)
    db.commit()
    return {"detail": "deleted"}


#時間選擇
@router.get("/{course_id}/times")
def admin_list_course_times(course_id: str, db: Session = Depends(get_db), admin=Depends(require_admin)):
    rows = (
        db.query(CourseTime)
        .filter(CourseTime.course_id == course_id)
        .order_by(CourseTime.weekday.asc(), CourseTime.start_section.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "weekday": r.weekday,
            "start_section": r.start_section,
            "end_section": r.end_section,
            "classroom": r.classroom,
        }
        for r in rows
    ]


@router.put("/{course_id}/times")
def admin_replace_course_times_by_grid(
    course_id: str,
    body: TimeGridUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not db.query(Course.id).filter(Course.id == course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")

    slots = parse_time_slots(body.time_slots)
    ranges = compress_slots_to_ranges(slots)

    # 全刪重建
    db.query(CourseTime).filter(CourseTime.course_id == course_id).delete()

    for w, start, end in ranges:
        db.add(CourseTime(
            course_id=course_id,
            weekday=w,
            start_section=start,
            end_section=end,
            classroom=body.classroom
        ))

    db.commit()
    return {"detail": "times replaced", "ranges": ranges}
