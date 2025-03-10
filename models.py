# models.py
from pydantic import BaseModel

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class PasswordReset(BaseModel):
    email: str

class VerifyResetCode(BaseModel):
    email: str
    reset_code: str

class NewPassword(BaseModel):
    email: str
    new_password: str