from sqlalchemy import Column, Integer, String
from app.database import Base

class Program(Base):
    __tablename__ = "programs"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
