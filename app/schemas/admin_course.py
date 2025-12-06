
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CourseTimeIn(BaseModel):
    weekday: int
    start_section: int
    end_section: int
    classroom: Optional[str] = None


class AdminCourseBase(BaseModel):
    id: str
    name_zh: str
    name_en: Optional[str] = None
    semester: Optional[str] = None
    department_id: Optional[str] = None
    teacher_id: Optional[str] = None
    grade: Optional[int] = None
    class_group: Optional[str] = None
    group_code: Optional[str] = None
    credit: int = 0
    required_type: Optional[str] = None
    category: Optional[str] = None
    limit_min: Optional[int] = None
    limit_max: Optional[int] = None
    chinese_summary: Optional[str] = None
    english_summary: Optional[str] = None
    raw_remark: Optional[str] = None


class AdminCourseCreate(AdminCourseBase):
    """
     新增課程：支援兩種時間輸入方式（二選一即可）
    1) times: [{weekday,start_section,end_section,...}]
    2) time_slots: ["1-1","1-2","3-5"] + classroom(可選)
    """
    times: List[CourseTimeIn] = Field(default_factory=list)

    #時間表勾選
    time_slots: List[str] = Field(default_factory=list, description="例如 ['1-1','1-2','3-5']")
    classroom: Optional[str] = Field(default=None, description="若使用 time_slots，可填統一教室")


class AdminCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    semester: Optional[str] = None
    department_id: Optional[str] = None
    teacher_id: Optional[str] = None
    grade: Optional[int] = None
    class_group: Optional[str] = None
    group_code: Optional[str] = None
    credit: Optional[int] = None
    required_type: Optional[str] = None
    category: Optional[str] = None
    limit_min: Optional[int] = None
    limit_max: Optional[int] = None
    chinese_summary: Optional[str] = None
    english_summary: Optional[str] = None
    raw_remark: Optional[str] = None


class AdminCourseOut(AdminCourseBase):
    model_config = ConfigDict(from_attributes=True)


class AdminCourseListOut(BaseModel):
    items: List[AdminCourseOut]
    total: int
    page: int
    page_size: int
