from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from app.database import get_db
from app.schemas.credits import ProgramOut, SetProgramIn
from app.models.program import Program
from app.models.student_program import StudentProgram
from app.models.program_course import ProgramCourse
from app.models.course import Course


from app.utils.auth import get_current_user


from app.models.student_course import StudentCourse

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(tags=["Credits"])

GRAD_TOTAL = 128
REQ_GEN = 28
REQ_MAJOR = 65
REQ_ELECT = 35
PROGRAM_MIN = 20


@router.get("/credits/programs", response_model=list[ProgramOut])
def list_programs(db: Session = Depends(get_db)):
    rows = db.query(Program).order_by(Program.id.asc()).all()
    return [{"code": p.code, "name": p.name} for p in rows]


@router.put("/students/me/program")
def set_my_program(body: SetProgramIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    program = db.query(Program).filter(Program.code == body.program_code).first()
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
    # 取學生學程
    sp = (
        db.query(StudentProgram, Program)
        .join(Program, Program.id == StudentProgram.program_id)
        .filter(StudentProgram.student_id == user.id)
        .first()
    )
    program = sp[1] if sp else None

    # 只算 completed + passed 的學分
    completed_sq = (
        db.query(Course.credit.label("credit"), Course.required_type.label("required_type"), Course.id.label("course_id"))
        .join(StudentCourse, StudentCourse.course_id == Course.id)
        .filter(
            StudentCourse.student_id == user.id,
            StudentCourse.status == "completed",
            StudentCourse.passed.is_(True),
        )
        .subquery()
    )

    earned_total = db.query(func.coalesce(func.sum(completed_sq.c.credit), 0)).scalar()

    earned_major = db.query(func.coalesce(func.sum(
        case((completed_sq.c.required_type.ilike("%專業必修%"), completed_sq.c.credit), else_=0)
    ), 0)).scalar()

    earned_gen = db.query(func.coalesce(func.sum(
        case((completed_sq.c.required_type.ilike("%通識必修%"), completed_sq.c.credit), else_=0)
    ), 0)).scalar()

    earned_elect = int(earned_total) - int(earned_major) - int(earned_gen)

    # 學程學分 = 已完成課程 ∩ program_courses
    program_earned = 0
    if program:
        program_earned = (
            db.query(func.coalesce(func.sum(Course.credit), 0))
            .join(StudentCourse, StudentCourse.course_id == Course.id)
            .join(ProgramCourse, ProgramCourse.course_id == Course.id)
            .filter(
                StudentCourse.student_id == user.id,
                StudentCourse.status == "completed",
                StudentCourse.passed.is_(True),
                ProgramCourse.program_id == program.id,
            )
            .scalar()
        )

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
