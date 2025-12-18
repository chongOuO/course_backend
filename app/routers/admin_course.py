from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.utils.auth import get_current_user

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


@router.get("", response_model=AdminCourseListOut)
def admin_search_courses(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),

    #篩選
    course_id: Optional[str] = Query(None, description="科目代號/編號"),
    semester: Optional[str] = Query(None, description="學期 e.g. 1141"),
    grade: Optional[int] = Query(None, description="年級"),
    department_id: Optional[str] = Query(None, description="系所代碼"),
    teacher_id: Optional[str] = Query(None, description="教師代碼"),
    keyword: Optional[str] = Query(None, description="課程名稱關鍵字(中英)"),
    category: Optional[str] = Query(None, description="課別代碼"),
    required_type: Optional[str] = Query(None, description="課別名稱"),
    credit: Optional[int] = Query(None, description="學分數"),
    limit_max: Optional[int] = Query(None, description="上限人數"),

    #時間複選
    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2..."),

    
    weekday: Optional[int] = Query(None, ge=1, le=7),
    section: Optional[int] = Query(None, description="某一節(例如 3)，會找 start<=3<=end"),

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = db.query(Course)

    #基本欄位過濾
    if course_id:
        q = q.filter(Course.id.ilike(f"%{course_id}%"))
    if semester:
        q = q.filter(Course.semester == semester)
    if grade is not None:
        q = q.filter(Course.grade == grade)
    if department_id:
        q = q.filter(Course.department_id == department_id)
    if teacher_id:
        q = q.filter(Course.teacher_id == teacher_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(Course.name_zh.ilike(like), Course.name_en.ilike(like)))
    if category:
        q = q.filter(Course.category == category)
    if required_type:
        q = q.filter(Course.required_type == required_type)
    if credit is not None:
        q = q.filter(Course.credit == credit)
    if limit_max is not None:
        q = q.filter(Course.limit_max == limit_max)

    #時間條件
    slots = parse_time_slots(time_slots)
    need_time_join = bool(slots) or (weekday is not None) or (section is not None)

    if need_time_join:
        q = q.join(CourseTime, CourseTime.course_id == Course.id)

        # 複選time_slots-符合任一格
        if slots:
            slot_filters = [
                and_(
                    CourseTime.weekday == w,
                    CourseTime.start_section <= sec,
                    CourseTime.end_section >= sec,
                )
                for (w, sec) in slots
            ]
            q = q.filter(or_(*slot_filters))

        # 舊參數 weekday / section
        if weekday is not None:
            q = q.filter(CourseTime.weekday == weekday)
        if section is not None:
            q = q.filter(and_(CourseTime.start_section <= section, CourseTime.end_section >= section))

        q = q.distinct()

    total = q.count()
    items = (
        q.order_by(Course.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AdminCourseListOut(
        items=[AdminCourseOut.model_validate(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


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

    # FK 檢查
    if body.department_id:
        if not db.query(Department.id).filter(Department.id == body.department_id).first():
            raise HTTPException(status_code=400, detail="department_id not found")
    if body.teacher_id:
        if not db.query(Teacher.id).filter(Teacher.id == body.teacher_id).first():
            raise HTTPException(status_code=400, detail="teacher_id not found")

    c = Course(
        id=body.id,
        name_zh=body.name_zh,
        name_en=body.name_en,
        semester=body.semester,
        department_id=body.department_id,
        teacher_id=body.teacher_id,
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


from sqlalchemy.exc import IntegrityError

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

    #  把時間相關欄位先抽出來，避免 setattr 到 Course 上報錯
    times_in = data.pop("times", None)         # 可能不存在
    time_slots_in = data.pop("time_slots", None)
    classroom_in = data.pop("classroom", None)

    # FK 檢查
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
