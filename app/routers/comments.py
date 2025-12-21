
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.comment import Comment
from app.models.course import Course
from app.schemas.comment import CommentCreate, CommentOut
from app.utils.auth import get_current_user,require_admin

from sqlalchemy import func
from app.models.comment_like import CommentLike
from app.models.comment import Comment


from app.models.course import Course
from app.models.course_like import CourseLike

from app.models.teacher import Teacher
from app.models.department import Department
from app.models.course_time import CourseTime
from app.utils.timeslots import parse_time_slots

from typing import Optional
from fastapi import Query
from sqlalchemy import func, or_, and_, tuple_

from app.models.student_profile import StudentProfile
from app.models.user import User

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/{course_id}", response_model=CommentOut)
def add_comment(course_id: str, data: CommentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")

    c = Comment(
        user_id=user.id,
        course_id=course_id,
        content=data.content
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@router.get("/search")
def search_courses_with_comments(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),

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

    comment_limit: int = Query(5, ge=1, le=50, description="每門課最多回傳幾則最新留言"),
):
    # ===== 先查課程=====
    q = (
        db.query(
            Course,
            Teacher.name.label("teacher_name"),
            Department.id.label("department_id"),
            Department.name.label("department_name"),
        )
        .outerjoin(Teacher, Teacher.id == Course.teacher_id)
        .outerjoin(Department, Department.id == Course.department_id)
    )

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

    # ===== 時間篩選（需要 join CourseTime 才能 filter）=====
    slots = parse_time_slots(time_slots)  # 回傳 [(weekday, sec), ...]
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

    total = q.count()

    course_rows = (
        q.order_by(Course.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 沒有課就直接回
    if not course_rows:
        return {"page": page, "page_size": page_size, "total": total, "items": []}

    course_ids = [course.id for course, *_ in course_rows]

    # =====  一次查回這些課程的留言=====
    like_cnt_sq = (
        db.query(CommentLike.comment_id.label("cid"), func.count().label("like_count"))
        .group_by(CommentLike.comment_id)
        .subquery()
    )

    liked_sq = (
        db.query(CommentLike.comment_id.label("cid"))
        .filter(CommentLike.user_id == user.id)
        .subquery()
    )

    comment_cnt_sq = (
        db.query(Comment.course_id.label("course_id"), func.count().label("comment_count"))
        .filter(Comment.course_id.in_(course_ids))
        .group_by(Comment.course_id)
        .subquery()
    )

    comment_rows = (
        db.query(
            Comment,
            func.coalesce(like_cnt_sq.c.like_count, 0).label("like_count"),
            (liked_sq.c.cid.isnot(None)).label("liked_by_me"),
            Department.name.label("author_department_name"),
        )
        .outerjoin(like_cnt_sq, like_cnt_sq.c.cid == Comment.id)
        .outerjoin(liked_sq, liked_sq.c.cid == Comment.id)

        .outerjoin(User, User.id == Comment.user_id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .outerjoin(Department, Department.id == User.department_id)
        .filter(Comment.course_id.in_(course_ids))
        .order_by(Comment.course_id.asc(), Comment.created_at.desc())
        .all()
    )

    # 每門課只取 comment_limit 則
    comments_map: dict[str, list] = {cid: [] for cid in course_ids}
    for c, like_count, liked_by_me,author_department_name in comment_rows:
        bucket = comments_map.get(c.course_id)
        if bucket is None:
            continue
        if len(bucket) >= comment_limit:
            continue
        bucket.append({
            "id": c.id,
            "course_id": c.course_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at,
            "like_count": int(like_count),
            "liked_by_me": bool(liked_by_me),
            "author_department_name": author_department_name,
        })

    # 每門課留言總數
    cnt_rows = (
        db.query(comment_cnt_sq.c.course_id, comment_cnt_sq.c.comment_count)
        .all()
    )
    comment_count_map = {cid: int(cc) for cid, cc in cnt_rows}

    # ===== 3) 組裝回傳 =====
    items = []
    for course, teacher_name, dept_id, dept_name in course_rows:
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

            "comment_count": comment_count_map.get(course.id, 0),
            "comments": comments_map.get(course.id, []),
        })

    return {"page": page, "page_size": page_size, "total": total, "items": items}


@router.get("/{course_id}/comments")
def list_comments(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    #每則留言的按讚數 + 有沒有按過讚
    like_cnt_sq = (
        db.query(CommentLike.comment_id.label("cid"), func.count().label("like_count"))
        .group_by(CommentLike.comment_id)
        .subquery()
    )

    # 按過讚的留言
    liked_sq = (
        db.query(CommentLike.comment_id.label("cid"))
        .filter(CommentLike.user_id == user.id)
        .subquery()
    )

    rows = (
        db.query(
            Comment,
            func.coalesce(like_cnt_sq.c.like_count, 0).label("like_count"),
            (liked_sq.c.cid.isnot(None)).label("liked_by_me"),
        )
        .outerjoin(like_cnt_sq, like_cnt_sq.c.cid == Comment.id)
        .outerjoin(liked_sq, liked_sq.c.cid == Comment.id)
        .filter(Comment.course_id == course_id)
        .order_by(Comment.created_at.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "course_id": c.course_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at,
            "like_count": int(like_count),
            "liked_by_me": bool(liked_by_me),
        }
        for c, like_count, liked_by_me in rows
    ]


@router.post("/{course_id}/like")
def toggle_course_like(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # course 存在性
    if not db.query(Course.id).filter(Course.id == course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")

    like = db.query(CourseLike).filter_by(course_id=course_id, user_id=user.id).first()
    if like:
        db.delete(like)
        liked = False
    else:
        db.add(CourseLike(course_id=course_id, user_id=user.id))
        liked = True

    db.commit()

    like_count = db.query(func.count()).select_from(CourseLike).filter(CourseLike.course_id == course_id).scalar()
    return {"liked": liked, "like_count": like_count}  

@router.post("/comments/{comment_id}/like")
def toggle_comment_like(comment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):

    if not db.query(Comment.id).filter(Comment.id == comment_id).first():
        confirm = False
        raise HTTPException(status_code=404, detail="Comment not found")

    like = db.query(CommentLike).filter_by(comment_id=comment_id, user_id=user.id).first()
    if like:
        db.delete(like)
        liked = False
    else:
        db.add(CommentLike(comment_id=comment_id, user_id=user.id))
        liked = True

    db.commit()

    like_count = db.query(func.count()).select_from(CommentLike).filter(CommentLike.comment_id == comment_id).scalar()
    return {"liked": liked, "like_count": like_count}

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), user=Depends (get_current_user)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    db.delete(comment)
    db.commit()
    return {"detail": "Comment deleted"}

@router.delete("/admin/{comment_id}")
def admin_delete_comment(
    comment_id:int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise  HTTPException(status_code=404,detail="Comment not Found")
    db.delete(comment)
    db.commit()
    return {"detail":"Comment deleted by admin"}