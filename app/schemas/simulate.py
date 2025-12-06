from pydantic import BaseModel

class SimulateOut(BaseModel):
    course_id: str

    class Config:
        orm_mode = True
