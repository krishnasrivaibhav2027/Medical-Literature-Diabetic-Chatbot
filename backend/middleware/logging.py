from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from backend.core.logging import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"Incoming request: {request.method} {request.url.path} from {client_host}"
        )

        try:
            response = await call_next(request)
            logger.info(
                f"Outgoing response: {request.method} {request.url.path} - status {response.status_code}"
            )
            return response
        except Exception as e:
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {e}"
            )
            raise
