from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional
import re


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    confirm_password: str = Field(..., description="Password confirmation")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        allowed_domains = ["outlook", "yahoo", "gmail"]
        if not re.match(pattern, v):
            raise ValueError("Enter a valid email address.")
        domain = v.split("@")[1].split(".")[0].lower()
        if domain not in allowed_domains:
            raise ValueError(f"Email must be from one of: {', '.join(allowed_domains)}.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*" for c in v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*).")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    login_at: Optional[datetime] = None
    logout_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
