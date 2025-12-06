
from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class SimulatedSelection(Base):
    __tablename__ = "simulated_selection"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    course_id = Column(String(20), ForeignKey("courses.id", ondelete="CASCADE"))
