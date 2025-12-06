from sqlalchemy import Column, String
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(String(10), primary_key=True)
    name = Column(String(100), nullable=False)
