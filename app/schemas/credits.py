from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict

class ProgramOut(BaseModel):
    code: str
    name: str

class SetProgramIn(BaseModel):
    program_code: str

class CategoryRow(BaseModel):
    key: Literal["major_required", "elective", "general_required"]
    name: str
    required: int
    earned: int
    remaining: int
    status: Literal["done", "in_progress"]

class CreditSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    graduation: dict
    categories: List[CategoryRow]
    program: dict
