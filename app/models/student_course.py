from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StudentCourse(Base):
    __tablename__ = "student_courses"

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)

    status = Column(String(20), nullable=False, default="completed")
    passed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
