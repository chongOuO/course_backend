from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class CommentLike(Base):
    __tablename__ = "comment_likes"
    comment_id = Column(BigInteger, ForeignKey("course_comments.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
