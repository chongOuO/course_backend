from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user

from app.models.course import Course
from app.models.course_time import CourseTime                   
from app.models.student_course_selection import StudentCourseSelection  
from app.schemas.student_course_selection_test import AddSelectionTestIn

router = APIRouter(prefix="/test", tags=["Test"])


def _is_time_conflict(existing_times: list[CourseTime], new_times: list[CourseTime]) -> bool:
    """
    判斷是否衝堂：同 weekday 且 節次區間重疊就算衝堂
    """
    for a in existing_times:
        for b in new_times:
            if a.weekday != b.weekday:
                continue
            # 區間重疊：not (a在b前面 或 b在a前面)
            if not (a.end_section < b.start_section or b.end_section < a.start_section):
                return True
    return False


@router.post("/student-course-selections")
def test_add_student_course_selection(
    body: AddSelectionTestIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    # 1) 確認課程存在
    course = db.query(Course).filter(Course.id == body.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    semester = body.semester or course.semester
    if not semester:
        raise HTTPException(status_code=400, detail="semester is required (and course.semester is empty)")

    # 2) 避免重複
    exists_row = (
        db.query(StudentCourseSelection)
        .filter(
            StudentCourseSelection.user_id == user.id,
            StudentCourseSelection.course_id == body.course_id,
            StudentCourseSelection.semester == semester,
        )
        .first()
    )
    if exists_row:
        return {
            "detail": "Already exists",
            "id": exists_row.id,
            "user_id": exists_row.user_id,
            "course_id": exists_row.course_id,
            "semester": exists_row.semester,
            "status": exists_row.status,
        }

    # 3) 檢查衝堂
    new_times = (
        db.query(CourseTime)
        .filter(CourseTime.course_id == body.course_id)
        .all()
    )

    # 沒有時間就不做衝堂（可自行改成要擋）
    if new_times:
        existing_times = (
            db.query(CourseTime)
            .join(StudentCourseSelection, StudentCourseSelection.course_id == CourseTime.course_id)
            .filter(
                StudentCourseSelection.user_id == user.id,
                StudentCourseSelection.semester == semester,
                
                StudentCourseSelection.status.in_(["planned", "completed"]),
            )
            .all()
        )

        if _is_time_conflict(existing_times, new_times):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Time conflict",
                    "course_id": body.course_id,
                    "semester": semester,
                },
            )

    # 4) 寫入
    row = StudentCourseSelection(
        user_id=user.id,
        course_id=body.course_id,
        semester=semester,
        status=body.status or "planned",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "detail": "Inserted",
        "id": row.id,
        "user_id": row.user_id,
        "course_id": row.course_id,
        "semester": row.semester,
        "status": row.status,
        "created_at": row.created_at,
    }