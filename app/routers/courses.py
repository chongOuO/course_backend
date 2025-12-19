# app/routers/courses.py
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi.responses import StreamingResponse
from fastapi import HTTPException


from app.database import get_db
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.course_time import CourseTime
from app.utils.timeslots import parse_time_slots

from app.schemas.course_detail import CourseDetailOut, CourseTimeOut
from app.utils.excel_export import courses_to_xlsx_bytes, make_filename
from app.models.favorite import Favorite
from app.utils.auth import get_current_user
from sqlalchemy import exists
from sqlalchemy import func, cast,tuple_
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by

from collections import OrderedDict


router = APIRouter(prefix="/courses", tags=["Courses"])

import logging
logger = logging.getLogger("app.admin")


@router.get("")
def search_courses(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),

    keyword: Optional[str] = Query(None, description="課程名稱關鍵字（中/英）"),
    semester: Optional[str] = Query(None, description="學期，例如 1141"),
    required_type: Optional[str] = Query(None, description="課別，例如 專業必修(系所)"),
    grade: Optional[int] = Query(None, description="年級"),
    teacher: Optional[str] = Query(None, description="教師（可用代碼或姓名關鍵字）"),
    category: Optional[str] = Query(None, description="課程分類（category 欄位）"),

    # 同時支援「系所代碼」或「系所名稱」
    department: Optional[str] = Query(None, description="系所（可輸入代碼或名稱關鍵字）"),

    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2,3-5..."),

    weekday: Optional[int] = Query(None, ge=1, le=7, description="上課星期 1~7"),
    start_section: Optional[int] = Query(None, ge=1, le=15, description="起始節次"),
    end_section: Optional[int] = Query(None, ge=1, le=15, description="結束節次"),

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    
    is_fav_expr = exists().where(
        and_(
            Favorite.user_id == user.id,
            Favorite.course_id == Course.id,
        )
    )

    
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

    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            is_fav_expr.label("is_favorite"),
            times_sq.c.times.label("times"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
        .outerjoin(times_sq, times_sq.c.cid == Course.id)
    )

    # ===== 一般篩選 =====
    if keyword:
        k = f"%{keyword.strip()}%"
        q = q.filter(or_(Course.name_zh.ilike(k), Course.name_en.ilike(k)))

    if semester:
        q = q.filter(Course.semester == semester)

    if required_type:
        q = q.filter(Course.required_type == required_type)

    if grade is not None:
        q = q.filter(Course.grade == grade)

    if category:
        q = q.filter(Course.category == category)

    if department:
        d = department.strip()
        q = q.filter(or_(
            Course.department_id == d,          # 代碼
            Department.name.ilike(f"%{d}%"),    # 名稱
        ))

    if teacher:
        t = teacher.strip()
        q = q.filter(or_(Course.teacher_id == t, Teacher.name.ilike(f"%{t}%")))

    # ===== 時間篩選（需要 join CourseTime 才能 filter）=====
    slots = parse_time_slots(time_slots)
    if weekday is not None or start_section is not None or end_section is not None or slots:
        q = q.join(CourseTime, CourseTime.course_id == Course.id)

    if weekday is not None:
        q = q.filter(CourseTime.weekday == weekday)

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

    # 範圍內：只要完全落在 start_section ~ end_section 之間
    if start_section is not None and end_section is not None:
        q = q.filter(
            and_(
                CourseTime.start_section >= start_section,
                CourseTime.end_section <= end_section,
            )
        )
    elif start_section is not None:
        q = q.filter(CourseTime.start_section >= start_section)
    elif end_section is not None:
        q = q.filter(CourseTime.end_section <= end_section)

    # 有使用時間條件才去 distinct，避免同一課多個時段重複
    if weekday is not None or start_section is not None or end_section is not None or slots:
        
        q = q.distinct()

    total = q.count()

    
    rows = (
        q.order_by(is_fav_expr.desc(), Course.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for course, teacher_name, dept_id, dept_name, is_favorite, times in rows:
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

            "is_favorite": bool(is_favorite),
            "times": times or [],
        })

    return {"page": page, "page_size": page_size, "total": total, "items": items}
@router.get("/public")
def search_courses_public(
    db: Session = Depends(get_db),

    keyword: Optional[str] = Query(None, description="課程名稱關鍵字（中/英）"),
    semester: Optional[str] = Query(None, description="學期，例如 1141"),
    required_type: Optional[str] = Query(None, description="課別，例如 專業必修(系所)"),
    grade: Optional[int] = Query(None, description="年級"),
    teacher: Optional[str] = Query(None, description="教師（可用代碼或姓名關鍵字）"),
    category: Optional[str] = Query(None, description="課程分類（category 欄位）"),

   
    department: Optional[str] = Query(None, description="系所（可輸入代碼或名稱關鍵字）"),

    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2,3-5..."),

    weekday: Optional[int] = Query(None, ge=1, le=7, description="上課星期 1~7"),
    start_section: Optional[int] = Query(None, ge=1, le=15, description="起始節次"),
    end_section: Optional[int] = Query(None, ge=1, le=15, description="結束節次"),

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    # times 聚合
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

    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
            times_sq.c.times.label("times"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
        .outerjoin(times_sq, times_sq.c.cid == Course.id)
    )

    # ===== 篩選 =====
    if keyword:
        k = f"%{keyword.strip()}%"
        q = q.filter(or_(Course.name_zh.ilike(k), Course.name_en.ilike(k)))

    if semester:
        q = q.filter(Course.semester == semester)

    if required_type:
        q = q.filter(Course.required_type == required_type)

    if grade is not None:
        q = q.filter(Course.grade == grade)

    if category:
        q = q.filter(Course.category == category)

    #  department：代碼或名稱
    if department:
        d = department.strip()
        q = q.filter(or_(
            Course.department_id == d,
            Department.name.ilike(f"%{d}%")
        ))

    if teacher:
        t = teacher.strip()
        q = q.filter(or_(Course.teacher_id == t, Teacher.name.ilike(f"%{t}%")))

    # ===== 時間篩選（需要 join CourseTime 才能 filter）=====
    slots = parse_time_slots(time_slots)
    if weekday is not None or start_section is not None or end_section is not None or slots:
        q = q.join(CourseTime, CourseTime.course_id == Course.id)

    if weekday is not None:
        q = q.filter(CourseTime.weekday == weekday)

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

    # 範圍內
    if start_section is not None and end_section is not None:
        q = q.filter(
            and_(
                CourseTime.start_section >= start_section,
                CourseTime.end_section <= end_section,
            )
        )
    elif start_section is not None:
        q = q.filter(CourseTime.start_section >= start_section)
    elif end_section is not None:
        q = q.filter(CourseTime.end_section <= end_section)

    if weekday is not None or start_section is not None or end_section is not None or slots:
        q = q.distinct(Course.id)

    total = q.count()

    rows = (
        q.order_by(Course.id.asc())
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
            "times": times or [],
        })

    return {"page": page, "page_size": page_size, "total": total, "items": items}

@router.get("/export")
def export_courses_excel(
    db: Session = Depends(get_db),
    

    keyword: Optional[str] = Query(None, description="課程名稱關鍵字（中/英）"),
    semester: Optional[str] = Query(None, description="學期，例如 1141"),
    required_type: Optional[str] = Query(None, description="課別，例如 專業必修(系所)"),
    grade: Optional[int] = Query(None, description="年級"),
    teacher: Optional[str] = Query(None, description="教師（可用代碼或姓名關鍵字）"),
    category: Optional[str] = Query(None, description="課程分類（category 欄位）"),
    department: Optional[str] = Query(None, description="系所（可輸入代碼或名稱關鍵字）"),

    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2,3-5..."),

    weekday: Optional[int] = Query(None, ge=1, le=7, description="上課星期 1~7"),
    start_section: Optional[int] = Query(None, ge=1, le=15, description="起始節次"),
    end_section: Optional[int] = Query(None, ge=1, le=15, description="結束節次"),
):
    """
    匯出「課程查詢結果」成 Excel（.xlsx）
    """

    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.name.label("department_name"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
    )

    # ===== 一般篩選=====
    if keyword:
        k = f"%{keyword.strip()}%"
        q = q.filter(or_(Course.name_zh.ilike(k), Course.name_en.ilike(k)))

    if semester:
        q = q.filter(Course.semester == semester)

    if required_type:
        q = q.filter(Course.required_type == required_type)

    if grade is not None:
        q = q.filter(Course.grade == grade)

    if category:
        q = q.filter(Course.category == category)

    if department:
        d = department.strip()
        q = q.filter(or_(Course.department_id == d, Department.name.ilike(f"%{d}%")))

    if teacher:
        t = teacher.strip()
        q = q.filter(or_(Course.teacher_id == t, Teacher.name.ilike(f"%{t}%")))

    # ===== 時間篩選=====
    slots = parse_time_slots(time_slots)

    if weekday is not None or start_section is not None or end_section is not None or slots:
        q = q.join(CourseTime, CourseTime.course_id == Course.id)

    if weekday is not None:
        q = q.filter(CourseTime.weekday == weekday)

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

    if start_section is not None and end_section is not None:
        q = q.filter(and_(CourseTime.start_section >= start_section, CourseTime.end_section <= end_section))
    elif start_section is not None:
        q = q.filter(CourseTime.start_section >= start_section)
    elif end_section is not None:
        q = q.filter(CourseTime.end_section <= end_section)

    if weekday is not None or start_section is not None or end_section is not None or slots:
        q = q.distinct(Course.id)

    q = q.order_by(Course.id.asc())
    results = q.all()
    if not results:
        raise HTTPException(
            status_code=404,
            detail="No courses found for the given filters."
        )
    # ===== times map（避免 N+1）=====
    course_ids = [c.id for (c, _tname, _dname) in results]
    times_map: dict[str, list[CourseTime]] = {}
    if course_ids:
        times = (
            db.query(CourseTime)
            .filter(CourseTime.course_id.in_(course_ids))
            .order_by(CourseTime.course_id, CourseTime.weekday, CourseTime.start_section)
            .all()
        )
        for t in times:
            times_map.setdefault(t.course_id, []).append(t)

    def pick_first_time(course_id: str):
        """export 對齊 import：只輸出一筆 上課星期/上課節次/上課地點（若同課多時段，取第一筆）"""
        arr = times_map.get(course_id, [])
        if not arr:
            return None, None, None
        t = arr[0]
        w = t.weekday
        # 上課節次：單節就輸出 "3"，多節就輸出 "3-5"
        if t.start_section == t.end_section:
            sec = str(t.start_section)
        else:
            sec = f"{t.start_section}-{t.end_section}"
        return w, sec, t.classroom

    # ===== 匯出欄位：對齊 import 讀取的 header =====
    # 系所代碼、主開課教師代碼(舊碼)/授課教師代碼(舊碼)、主開課教師姓名/授課教師姓名、
    # 科目代碼(新碼全碼)、科目中文名稱、科目英文名稱、年級、上課班組、科目組別、學分數、課別名稱、課別代碼、
    # 上課人數、課程中文摘要、課程英文摘要、課表備註、學期、上課星期、上課節次、上課地點
    rows_for_excel = []
    for course, teacher_name, dept_name in results:
        w, sec, room = pick_first_time(course.id)

        rows_for_excel.append(OrderedDict([
            ("系所代碼", course.department_id),
            # 如果你之後想補系所名稱，可加欄位，但 import 不會用到：
            # ("系所名稱", dept_name or ""),
            ("主開課教師代碼(舊碼)", course.teacher_id),
            ("主開課教師姓名", teacher_name or ""),
            # 兼容你的 import（它會嘗試主開課/授課二選一）
            ("授課教師代碼(舊碼)", course.teacher_id),
            ("授課教師姓名", teacher_name or ""),

            ("科目代碼(新碼全碼)", course.id),
            ("科目中文名稱", course.name_zh or ""),
            ("科目英文名稱", course.name_en or ""),

            ("年級", course.grade),
            ("上課班組", course.class_group or ""),
            ("科目組別", course.group_code or ""),

            ("學分數", course.credit),
            ("課別名稱", course.required_type or ""),
            ("課別代碼", course.category or ""),
            ("上課人數", course.limit_max),

            ("課程中文摘要", course.chinese_summary or ""),
            ("課程英文摘要", course.english_summary or ""),
            ("課表備註", course.raw_remark or ""),
            ("學期", course.semester or ""),

            ("上課星期", w),
            ("上課節次", sec),
            ("上課地點", room or ""),
        ]))

    xlsx_bytes = courses_to_xlsx_bytes(rows_for_excel, sheet_name="Courses")
    filename = make_filename("courses")  

    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

#給前端下拉選單用
@router.get("/meta/teachers")
def list_teachers(db: Session = Depends(get_db)):
    rows = db.query(Teacher.id, Teacher.name).order_by(Teacher.id.asc()).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/meta/departments")
def list_departments(db: Session = Depends(get_db)):
    rows = db.query(Department.id, Department.name).order_by(Department.id.asc()).all()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.get("/meta/semesters")
def list_semesters(db: Session = Depends(get_db)):
    rows = db.query(Course.semester).distinct().order_by(Course.semester.desc()).all()
    return [r[0] for r in rows if r[0]]


@router.get("/meta/required-types")
def list_required_types(db: Session = Depends(get_db)):
    rows = db.query(Course.required_type).distinct().order_by(Course.required_type.asc()).all()
    return [r[0] for r in rows if r[0]]


@router.get("/meta/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(Course.category).distinct().order_by(Course.category.asc()).all()
    return [r[0] for r in rows if r[0]]


