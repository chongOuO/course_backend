from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"))
