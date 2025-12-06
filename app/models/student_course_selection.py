
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from app.database import Base

class StudentCourseSelection(Base):
    __tablename__ = "student_course_selections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(String(32), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    semester = Column(String(10), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="planned")  
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
