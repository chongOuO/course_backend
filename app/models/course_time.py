
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class CourseTime(Base):
    __tablename__ = "course_time"

    id = Column(Integer, primary_key=True)
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"))

    weekday = Column(Integer)
    start_section = Column(Integer)
    end_section = Column(Integer)
    classroom = Column(String(50))

    course = relationship("Course", back_populates="times")
