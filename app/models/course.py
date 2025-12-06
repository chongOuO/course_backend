
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Course(Base):
    __tablename__ = "courses"

    id = Column(String(20), primary_key=True)

    name_zh = Column(String(255), nullable=False)
    name_en = Column(Text)

    department_id = Column(String(10), ForeignKey("departments.id"))
    teacher_id = Column(String(10), ForeignKey("teachers.id"))

    grade = Column(Integer)
    class_group = Column(String(10))
    group_code = Column(String(10))

    credit = Column(Integer, nullable=False)
    required_type = Column(String(20))
    category = Column(String(50))

    limit_min = Column(Integer)
    limit_max = Column(Integer)

    chinese_summary = Column(Text)
    english_summary = Column(Text)
    raw_remark = Column(Text)

    semester = Column(String(10))

    # relationship
    times = relationship("CourseTime", back_populates="course")
