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
    department: Optional[str] = Query(None, description="系所代碼（department_id）"),
    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2,3-5..."),

    weekday: Optional[int] = Query(None, ge=1, le=7, description="上課星期 1~7"),
    start_section: Optional[int] = Query(None, ge=1, le=15, description="起始節次"),
    end_section: Optional[int] = Query(None, ge=1, le=15, description="結束節次"),

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    # 是否收藏
    is_fav_expr = exists().where(
        and_(
            Favorite.user_id == user.id,
            Favorite.course_id == Course.id,
        )
    )

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
            Department.name.label("department_name"),
            is_fav_expr.label("is_favorite"),
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

    if department:
        q = q.filter(Course.department_id == department)

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
    for course, teacher_name, dept_name, is_favorite, times in rows:
        items.append({
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
            "is_favorite": bool(is_favorite),
            "times": times or [],
        })

    return {"page": page, "page_size": page_size, "total": total, "items": items}

@router.get("/export")
def export_courses_excel(
    db: Session = Depends(get_db),

    keyword: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    department_id: Optional[str] = Query(None),
    teacher_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    required_type: Optional[str] = Query(None),
    credit: Optional[int] = Query(None),
    limit_max: Optional[int] = Query(None),

    # 多選時間格：time_slots=1-1&time_slots=1-2...
    time_slots: list[str] | None = Query(None, description="多選: 1-1,1-2,3-5..."),
):
    """
    匯出「課程查詢結果」成 Excel（.xlsx）
    """
    # 以 join 方式把 teacher/department 名稱也一起帶出
    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.name.label("department_name"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
    )

    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(Course.name_zh.ilike(like), Course.name_en.ilike(like)))
    if semester:
        q = q.filter(Course.semester == semester)
    if grade is not None:
        q = q.filter(Course.grade == grade)
    if department_id:
        q = q.filter(Course.department_id == department_id)
    if teacher_id:
        q = q.filter(Course.teacher_id == teacher_id)
    if category:
        q = q.filter(Course.category == category)
    if required_type:
        q = q.filter(Course.required_type == required_type)
    if credit is not None:
        q = q.filter(Course.credit == credit)
    if limit_max is not None:
        q = q.filter(Course.limit_max == limit_max)

    slots = parse_time_slots(time_slots)
    if slots:
        q = q.join(CourseTime, CourseTime.course_id == Course.id)
        slot_filters = [
            and_(
                CourseTime.weekday == w,
                CourseTime.start_section <= sec,
                CourseTime.end_section >= sec,
            )
            for (w, sec) in slots
        ]
        q = q.filter(or_(*slot_filters)).distinct()

    q = q.order_by(Course.id.asc())

    results = q.all()

    # 把每門課的 times 彙整成字串（星期X 第a~b節）
    # 為了避免 N+1，這裡再抓一次 times
    course_ids = [c.id for (c, _tname, _dname) in results]
    times_map = {}
    if course_ids:
        times = (
            db.query(CourseTime)
            .filter(CourseTime.course_id.in_(course_ids))
            .order_by(CourseTime.course_id, CourseTime.weekday, CourseTime.start_section)
            .all()
        )
        for t in times:
            times_map.setdefault(t.course_id, []).append(t)

    def fmt_time_list(course_id: str) -> str:
        arr = times_map.get(course_id, [])
        parts = []
        for t in arr:
            if t.start_section == t.end_section:
                parts.append(f"{t.weekday}-{t.start_section}")
            else:
                parts.append(f"{t.weekday}-{t.start_section}~{t.end_section}")
        return ", ".join(parts)

    # Excel rows（欄位你可以依你介面調整）
    rows_for_excel = []
    for course, teacher_name, dept_name in results:
        rows_for_excel.append({
            "科目代號": course.id,
            "課程名稱": course.name_zh,
            "學期": course.semester,
            "年級": course.grade,
            "系所": dept_name or course.department_id,
            "教師": teacher_name or course.teacher_id,
            "學分數": course.credit,
            "課別": course.required_type,
            "類別代碼": course.category,
            "上限人數": course.limit_max,
            "時間": fmt_time_list(course.id),
            "備註": course.raw_remark,
        })

    xlsx_bytes = courses_to_xlsx_bytes(rows_for_excel, sheet_name="Courses")
    filename = make_filename("courses")

    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/{course_id}", response_model=CourseDetailOut)
def get_course_detail(course_id: str, db: Session = Depends(get_db)):
    # 先抓 course + teacher_name + department_name
    row = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.name.label("department_name"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
        .filter(Course.id == course_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Course not found")

    course, teacher_name, department_name = row

    #抓課程時間
    times = (
        db.query(CourseTime)
        .filter(CourseTime.course_id == course_id)
        .order_by(CourseTime.weekday.asc(), CourseTime.start_section.asc())
        .all()
    )

    #點讚/留言統計：如果你有相關表再打開
    course_like_count = 0
    comment_count = 0


    return CourseDetailOut(
        # course 欄位
        id=course.id,
        name_zh=course.name_zh,
        name_en=course.name_en,
        semester=course.semester,
        grade=course.grade,
        class_group=course.class_group,
        group_code=course.group_code,
        credit=course.credit,
        required_type=course.required_type,
        category=course.category,
        limit_min=course.limit_min,
        limit_max=course.limit_max,
        chinese_summary=course.chinese_summary,
        english_summary=course.english_summary,
        raw_remark=course.raw_remark,

        department_id=course.department_id,
        department_name=department_name,
        teacher_id=course.teacher_id,
        teacher_name=teacher_name,

        times=[CourseTimeOut.model_validate(t) for t in times],

        course_like_count=course_like_count,
        comment_count=comment_count,
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


