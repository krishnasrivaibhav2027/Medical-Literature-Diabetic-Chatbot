from fastapi import APIRouter, Depends, status
from backend.auth.schemas import UserLogin, Token, LogoutResponse
from backend.auth.service import AuthService
from backend.auth.dependencies import get_current_user
from backend.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(login_data: UserLogin, auth_service: AuthService = Depends()) -> Token:
    return await auth_service.login(login_data)


@router.post("/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(auth_service: AuthService = Depends(), current_user: User = Depends(get_current_user)) -> LogoutResponse:
    return await auth_service.logout(current_user)
