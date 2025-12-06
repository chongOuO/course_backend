from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class CourseTimeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    weekday: int
    start_section: int
    end_section: int
    classroom: Optional[str] = None

class CourseDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # course 欄位
    id: str
    name_zh: str
    name_en: Optional[str] = None
    semester: Optional[str] = None
    grade: Optional[int] = None
    class_group: Optional[str] = None
    group_code: Optional[str] = None
    credit: int
    required_type: Optional[str] = None
    category: Optional[str] = None
    limit_min: Optional[int] = None
    limit_max: Optional[int] = None
    chinese_summary: Optional[str] = None
    english_summary: Optional[str] = None
    raw_remark: Optional[str] = None

    # join 來的資訊
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None

    # 時間
    times: List[CourseTimeOut] = []

    course_like_count: int = 0
    comment_count: int = 0
