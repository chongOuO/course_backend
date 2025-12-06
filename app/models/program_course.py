from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class ProgramCourse(Base):
    __tablename__ = "program_courses"
    program_id = Column(Integer, ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
