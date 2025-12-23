from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_

from app.database import get_db
from app.schemas.credits import ProgramOut, SetProgramIn
from app.models.program import Program
from app.models.student_program import StudentProgram
from app.models.program_course import ProgramCourse
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.utils.auth import get_current_user
from app.models.student_course_selection import StudentCourseSelection

import logging
logger = logging.getLogger("app.credits")

router = APIRouter(tags=["Credits"])

GRAD_TOTAL = 128
REQ_GEN = 28
REQ_MAJOR = 65
REQ_ELECT = 35
PROGRAM_MIN = 20


@router.get("/credits/programs", response_model=list[ProgramOut])
def list_programs(db: Session = Depends(get_db)):
    rows = db.query(Program).order_by(Program.code.asc()).all()
    return [{"code": p.code, "name": p.name} for p in rows]


@router.put("/students/me/program")
def set_my_program(
    body: SetProgramIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    允許用 program_code 傳：
    - Program.code（例如 'AI'）
    - Program.name（例如 '醫療資訊學程'）
    """

    key = (body.program_code or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="program_code is required")

    program = (
        db.query(Program)
        .filter(or_(Program.code == key, Program.name == key))
        .first()
    )
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    sp = db.query(StudentProgram).filter(StudentProgram.student_id == user.id).first()
    if sp:
        sp.program_id = program.id
    else:
        sp = StudentProgram(student_id=user.id, program_id=program.id)
        db.add(sp)

    db.commit()
    return {"program": {"code": program.code, "name": program.name}}


@router.get("/students/me/credits/summary")
def my_credit_summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    # 取學生學程（可能為 None）
    sp_row = (
        db.query(StudentProgram, Program)
        .join(Program, Program.id == StudentProgram.program_id)
        .filter(StudentProgram.student_id == user.id)
        .first()
    )
    program = sp_row[1] if sp_row else None

    completed_sq = (
        db.query(
            Course.id.label("course_id"),
            Course.credit.label("credit"),
            Course.required_type.label("required_type"),
        )
        .join(StudentCourseSelection, StudentCourseSelection.course_id == Course.id)
        .filter(
            StudentCourseSelection.user_id == user.id,
            StudentCourseSelection.status == "completed",
        )
        .distinct(Course.id)
        .subquery()
    )

    earned_total = db.query(func.coalesce(func.sum(completed_sq.c.credit), 0)).scalar()

    earned_major = db.query(
        func.coalesce(
            func.sum(
                case(
                    (completed_sq.c.required_type.ilike("%專業必修%"), completed_sq.c.credit),
                    else_=0,
                )
            ),
            0,
        )
    ).scalar()

    earned_gen = db.query(
        func.coalesce(
            func.sum(
                case(
                    (completed_sq.c.required_type.ilike("%通識必修%"), completed_sq.c.credit),
                    else_=0,
                )
            ),
            0,
        )
    ).scalar()

    earned_elect = int(earned_total) - int(earned_major) - int(earned_gen)

    #學程學分：已完成課程（selections completed）∩ program_courses
    logger.info(f"[credits] user.id={user.id} type={type(user.id)}")
    logger.info(f"[credits] program.id={(program.id if program else None)} code={(program.code if program else None)}")
    program_earned = 0
    if program:
        program_sq = (
            db.query(
                Course.id.label("cid"),
                Course.credit.label("credit"),
            )
            .join(StudentCourseSelection, StudentCourseSelection.course_id == Course.id)
            .join(ProgramCourse, ProgramCourse.course_id == Course.id)
            .filter(
                StudentCourseSelection.user_id == user.id,
                StudentCourseSelection.status == "completed",
                ProgramCourse.program_id == program.id,
            )
            .distinct(Course.id)
            .subquery()
        )
        program_earned = db.query(func.coalesce(func.sum(program_sq.c.credit), 0)).scalar()

    def status(required: int, earned: int) -> str:
        return "done" if earned >= required else "in_progress"

    remaining_total = max(0, GRAD_TOTAL - int(earned_total))
    progress_percent = int(round((int(earned_total) / GRAD_TOTAL) * 100)) if GRAD_TOTAL else 0

    return {
        "graduation": {
            "required_total": GRAD_TOTAL,
            "earned_total": int(earned_total),
            "remaining_total": remaining_total,
            "progress_percent": min(100, progress_percent),
        },
        "categories": [
            {
                "key": "major_required",
                "name": "專業必修",
                "required": REQ_MAJOR,
                "earned": int(earned_major),
                "remaining": max(0, REQ_MAJOR - int(earned_major)),
                "status": status(REQ_MAJOR, int(earned_major)),
            },
            {
                "key": "elective",
                "name": "選修",
                "required": REQ_ELECT,
                "earned": int(earned_elect),
                "remaining": max(0, REQ_ELECT - int(earned_elect)),
                "status": status(REQ_ELECT, int(earned_elect)),
            },
            {
                "key": "general_required",
                "name": "通識必修",
                "required": REQ_GEN,
                "earned": int(earned_gen),
                "remaining": max(0, REQ_GEN - int(earned_gen)),
                "status": status(REQ_GEN, int(earned_gen)),
            },
        ],
        "program": {
            "selected": {"code": program.code, "name": program.name} if program else None,
            "min_required": PROGRAM_MIN,
            "earned": int(program_earned),
            "remaining": max(0, PROGRAM_MIN - int(program_earned)),
            "status": status(PROGRAM_MIN, int(program_earned)),
        },
    }