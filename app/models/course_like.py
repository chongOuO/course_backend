from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class CourseLike(Base):
    __tablename__ = "course_likes"
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
