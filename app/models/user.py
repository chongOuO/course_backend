
from sqlalchemy import Column, Integer, String, TIMESTAMP
from datetime import datetime
from app.database import Base
from sqlalchemy import ForeignKey
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    department_id = Column(String, ForeignKey("departments.id"), nullable=True)
