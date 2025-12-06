from pydantic import BaseModel, Field

class ForgotPasswordIn(BaseModel):
    email: str  # 不用 EmailStr

class ResetPasswordIn(BaseModel):
    token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8, max_length=72)
