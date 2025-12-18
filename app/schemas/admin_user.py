
from datetime import datetime
from typing import Optional,Literal
from pydantic import BaseModel, Field

Role = Literal["admin", "student"]


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    student_no: Optional[str] = None
    full_name: Optional[str] = None
    department_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None

class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserCreateIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=72)  
    role: Role = "student"
    student_no: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class AdminUserUpdateIn(BaseModel):
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    student_no: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_name: Optional[str] = None


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=0, max_length=72)