from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
import re


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
    department_name: Optional[str] = None
    teacher_name: Optional[str] = None    

    times: List[CourseTimeIn] = Field(default_factory=list)

    time_slots: List[str] = Field(default_factory=list, description="例如 ['1-1','1-2','3-5']")
    classroom: Optional[str] = Field(default=None, description="若使用 time_slots，可填統一教室")



    @model_validator(mode="after")
    def _validate_time_create(self):
        has_times = len(self.times) > 0
        has_slots = len(self.time_slots) > 0

    
        if has_times and has_slots:
            raise ValueError("times 與 time_slots 不能同時提供，請擇一填寫。")
        if not has_times and not has_slots:
            raise ValueError("請至少提供 times 或 time_slots 其中一種課程時間資料。")

        if has_slots:
            if self.classroom is None or self.classroom.strip() == "":
                raise ValueError("使用 time_slots 時，classroom（統一教室）為必填。")

            slot_pat = re.compile(r"^\d+-\d+$")
            for s in self.time_slots:
                if not slot_pat.match(s):
                    raise ValueError(f"time_slots 格式錯誤：{s}，請使用 '星期-節次' 格式，例如 '1-1'。")

        return self


class AdminCourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_zh: Optional[str] = None
    name_en: Optional[str] = None
    semester: Optional[str] = None
    department_id: Optional[str] = None
    teacher_id: Optional[str] = None
    department_name: Optional[str] = None
    teacher_name: Optional[str] = None
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

   
    times: Optional[List[CourseTimeIn]] = None
    time_slots: Optional[List[str]] = None
    classroom: Optional[str] = None

    @model_validator(mode="after")
    def _validate_time_update(self):
        has_times = self.times is not None
        has_slots = self.time_slots is not None
        has_classroom = self.classroom is not None

        # 沒要改時間
        if not has_times and not has_slots and not has_classroom:
            return self

        # 只給 classroom 不允許
        if has_classroom and not has_slots and not has_times:
            raise ValueError("若要修改上課時間，請提供 times 或 time_slots；僅提供 classroom 無法更新課表。")

        # times / time_slots 不能同時提供
        if has_times and has_slots:
            raise ValueError("times 與 time_slots 不能同時提供，請擇一填寫。")

        # 使用 time_slots 時 classroom 必填
        if has_slots:
            slots = self.time_slots or []
            if len(slots) > 0 and (self.classroom is None or self.classroom.strip() == ""):
                raise ValueError("使用 time_slots 時，classroom（統一教室）為必填。")

            slot_pat = re.compile(r"^\d+-\d+$")
            for s in slots:
                if not slot_pat.match(s):
                    raise ValueError(f"time_slots 格式錯誤：{s}，請使用 '星期-節次' 格式，例如 '1-1'。")

        return self


class AdminCourseOut(AdminCourseBase):
    model_config = ConfigDict(from_attributes=True)


class AdminCourseListOut(BaseModel):
    items: List[AdminCourseOut]
    total: int
    page: int
    page_size: int