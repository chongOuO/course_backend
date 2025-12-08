from pydantic import BaseModel
from typing import List
class SimulateOut(BaseModel):
    course_id: str

    class Config:
        orm_mode = True
class BulkSimulateIn(BaseModel):
    course_ids: List[str]
    # 是否要用這次的 course_ids 取代原本預選（等於先清空再新增）
    replace: bool = False