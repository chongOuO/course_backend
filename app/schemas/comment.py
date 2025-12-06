from pydantic import BaseModel, ConfigDict
from datetime import datetime

class CommentCreate(BaseModel):
    content: str

class CommentOut(BaseModel):
    id: int
    user_id: int
    course_id: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
