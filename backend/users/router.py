from pydantic import EmailStr
from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.users.models import User
from backend.users.schemas import UserCreate, UserResponse
from backend.users.service import UserService
from backend.core.database import get_db
from backend.core.exceptions import BadRequestException, AppException, NotFoundException
from backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/user", tags=["Users"])


@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        service = UserService(db)
        return await service.create_user(user)
    except HTTPException:
        raise
    except ValueError as e:
        raise BadRequestException(str(e))
    except Exception as e:
        raise AppException(str(e))


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(current_user: User = Depends(get_current_user)):
    try:
        return current_user
    except HTTPException:
        raise
    except ValueError as e:
        raise BadRequestException(str(e))
    except Exception as e:
        raise AppException(str(e))


@router.get("/get_user_by_email_id/{email}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user_by_email(email: EmailStr, db: AsyncSession = Depends(get_db)):
    try:
        service = UserService(db)
        user = await service.get_user_by_email(email)
        if not user:
            raise NotFoundException("User not found")
        return user
    except HTTPException:
        raise
    except ValueError as e:
        raise BadRequestException(str(e))
    except Exception as e:
        raise AppException(str(e))
