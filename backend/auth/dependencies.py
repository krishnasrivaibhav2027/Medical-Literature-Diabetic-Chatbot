from backend.core.exceptions import CredentialsException
from datetime import datetime, timezone
from jose import JWTError
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.users.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False
)


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    if not token:
        token = request.query_params.get('token')
    if not token:
        raise CredentialsException

    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise CredentialsException
        user_email = str(sub)
        iat = payload.get("iat")
    except (JWTError, ValueError):
        raise CredentialsException

    repository = UserRepository(db)
    user = await repository.get_user_by_email(user_email)
    if user is None:
        raise CredentialsException

    if user.logout_at and iat:
        if iat < user.logout_at.timestamp():
            raise CredentialsException
    return user
