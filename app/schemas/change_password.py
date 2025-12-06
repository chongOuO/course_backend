from pydantic import BaseModel, Field

class ChangePasswordIn(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)
