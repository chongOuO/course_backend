from pydantic import BaseModel
from typing import List, Optional

class TimeGridUpdate(BaseModel):
    time_slots: List[str]          
    classroom: Optional[str] = None  
