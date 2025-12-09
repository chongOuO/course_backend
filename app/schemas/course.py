
from pydantic import BaseModel
from typing import List, Optional


class CourseTimeOut(BaseModel):
    weekday: int
    start_section: int
    end_section: int
    classroom: str

    class Config:
        orm_mode = True

class CourseOut(BaseModel):
    id: str
    name_zh: str
    credit: int
    teacher_id: str
    grade: int
    required_type: str
    category: str
    semester: str
    times: List[CourseTimeOut] = []

    class Config:
        orm_mode = True
