from datetime import datetime, UTC
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.schemas import UserLogin, LogoutResponse
from backend.core.database import get_db
from backend.core.security import create_access_token, verify_password

from backend.users.repository import UserRepository
from backend.core.exceptions import CredentialsException
from backend.users.models import User


class AuthService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.repository = UserRepository(db)
        self.db = db

    async def login(self, login_data: UserLogin):
        user = await self.repository.get_user_by_email(login_data.email)
        if not user:
            raise CredentialsException()

        if not verify_password(login_data.password, user.hashed_password):
            raise CredentialsException()

        user.login_at = datetime.now()
        user.logout_at = None
        await self.db.commit()

        access_token = create_access_token(
            data={
                "sub": user.email,
            }
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "redirect_url": None,
        }

    async def logout(self, current_user: User) -> LogoutResponse:
        current_user.logout_at = datetime.now()
        await self.db.commit()
        return LogoutResponse(message="Successfully logged out")
