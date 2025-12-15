from typing import Optional, Literal
from pydantic import BaseModel

class AddSelectionTestIn(BaseModel):
    course_id: str
    semester: Optional[str] = None
    status: Optional[Literal["planned", "completed"]] = "planned"
