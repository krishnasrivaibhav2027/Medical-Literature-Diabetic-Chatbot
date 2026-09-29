from fastapi import HTTPException, status


class AppException(HTTPException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "An internal server error occurred"

    def __init__(self, detail: str = None):
        super().__init__(
            status_code=self.status_code,
            detail=detail if detail is not None else self.detail,
        )


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized"

    def __init__(self, detail: str = None):
        super().__init__(detail=detail)
        self.headers = {"WWW-Authenticate": "Bearer"}


class CredentialsException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Could not validate credentials"

    def __init__(self, detail: str = None):
        super().__init__(detail=detail)
        self.headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to access this resource"


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists"


class UnprocessableEntityException(AppException):
    status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    detail = "Unprocessable entity"
