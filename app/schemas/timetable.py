from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict

class CourseTimeOut(BaseModel):
    weekday: int
    start_section: int
    end_section: int
    classroom: Optional[str] = None

class TimetableCourseOut(BaseModel):
    id: str
    name_zh: str
    credit: int
    semester: str
    teacher_id: Optional[str] = None
    department_id: Optional[str] = None
    times: List[CourseTimeOut] = []

class TimetableSlotOut(BaseModel):
    course_id: str
    name_zh: str
    weekday: int
    start_section: int
    end_section: int
    classroom: Optional[str] = None

class TimetableOut(BaseModel):
    semester: str
    total_credits: int
    courses: List[TimetableCourseOut]
    grid: Dict[str, List[TimetableSlotOut]]  # "1".."7"
