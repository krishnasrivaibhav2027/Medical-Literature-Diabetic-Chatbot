from datetime import datetime, UTC
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from backend.users.models import User
from backend.users.schemas import UserCreate
from backend.users.repository import UserRepository
from backend.core.security import hash_password
from backend.core.exceptions import ConflictException


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = UserRepository(db)

    async def create_user(self, user_create: UserCreate) -> User:
        if await self.repository.get_user_by_email(user_create.email):
            raise ConflictException("A user with this email already exists.")

        now = datetime.now()
        db_user = User(
            username=user_create.username,
            email=user_create.email,
            hashed_password=hash_password(user_create.password),
            created_at=now,
            login_at=now,
        )

        try:
            return await self.repository.create_user(db_user)
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException("A user with this email or username already exists.")

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self.repository.get_user_by_email(email)
