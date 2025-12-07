from pydantic import BaseModel, Field

class ForgotPasswordIn(BaseModel):
    username: str

class ResetPasswordIn(BaseModel):
    username: str
    token: str
    new_password: str
