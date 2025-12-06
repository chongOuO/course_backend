from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StudentProgram(Base):
    __tablename__ = "student_program"
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
