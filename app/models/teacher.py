
from sqlalchemy import Column, String
from app.database import Base

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
