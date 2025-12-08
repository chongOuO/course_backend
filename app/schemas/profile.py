from pydantic import BaseModel, ConfigDict
from typing import Optional

class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    student_no: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    
class ProfileUpdateIn(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
