from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import Integer, String, func
from sqlalchemy.types import DateTime
from datetime import datetime
from typing import Optional
from backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=False)
    logout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
