from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_no = Column(String(32), unique=True, nullable=False, index=True)

    full_name = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)

    avatar_url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)