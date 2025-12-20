from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict


AnnouncementCategory = Literal[
    "office",        # 教務處
    "course_change", # 課程異動
    "department",    # 系所
    "activity",      # 活動
]


class AnnouncementBase(BaseModel):
    title: str
    content: str
    category: AnnouncementCategory
    is_pinned: bool = False
    is_active: bool = True
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class AnnouncementCreate(AnnouncementBase):
    pass


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[AnnouncementCategory] = None
    is_pinned: Optional[bool] = None
    is_active: Optional[bool] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class AnnouncementSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    category: AnnouncementCategory
    created_at: datetime
    is_pinned: bool


class AnnouncementDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    category: AnnouncementCategory
    created_at: datetime
    updated_at: datetime
    is_pinned: bool
    is_active: bool
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    author_id: Optional[int]



class AnnouncementListOut(BaseModel):
    items: list[AnnouncementSummary]
    total: int
    page: int
    page_size: int





    