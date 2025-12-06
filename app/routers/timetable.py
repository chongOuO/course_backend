from typing import Optional, Dict, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.auth import get_current_user

from app.models.student_course_selection import StudentCourseSelection
from app.models.course import Course
from app.models.course_time import CourseTime

from app.schemas.timetable import (
    TimetableOut, TimetableCourseOut, CourseTimeOut, TimetableSlotOut
)

router = APIRouter(prefix="/students/me", tags=["Student - Timetable"])

@router.get("/timetable", response_model=list[TimetableCourseOut])
def get_my_timetable(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    semester: str = Query(...),
    status: str = Query("planned"),
):
    rows = (
        db.query(StudentCourseSelection.course_id)
        .filter(
            StudentCourseSelection.user_id == user.id,
            StudentCourseSelection.semester == semester,
            StudentCourseSelection.status == status,
        ).all()
    )
    course_ids = [r[0] for r in rows]
    if not course_ids:
        return []

    courses = (
        db.query(Course)
        .filter(Course.id.in_(course_ids), Course.semester == semester)
        .all()
    )

    times = (
        db.query(CourseTime)
        .filter(CourseTime.course_id.in_(course_ids))
        .all()
    )
    times_map = {}
    for t in times:
        times_map.setdefault(t.course_id, []).append(t)

    out = []
    for c in courses:
        out.append(
            TimetableCourseOut(
                id=c.id,                            
                name_zh=c.name_zh or "",          
                semester=c.semester or semester,
                credit=int(c.credit or 0),
                times=[
                    CourseTimeOut(
                        weekday=t.weekday,
                        start_section=t.start_section,
                        end_section=t.end_section,
                        classroom=t.classroom,
                    )
                    for t in sorted(times_map.get(c.id, []), key=lambda x: (x.weekday, x.start_section))
                ],
            )
        )
    return out