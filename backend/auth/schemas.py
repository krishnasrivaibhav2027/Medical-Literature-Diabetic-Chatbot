from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User Password")


class Token(BaseModel):
    access_token: str
    token_type: str
    redirect_url: Optional[str] = None


class TokenData(BaseModel):
    email: EmailStr | None = None


class LogoutResponse(BaseModel):
    message: str = Field(..., description="Successfully logged out")
