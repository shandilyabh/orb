"""
Centralized rate limiting configuration for the application.
"""
from slowapi import Limiter # type: ignore
from slowapi.util import get_remote_address # type: ignore
from starlette.requests import Request # type: ignore

from core.config import settings


def key_func(request: Request) -> str:
    """
    Determines the identifier for rate limiting a request.
    It prioritizes the authenticated user's ID if available on the request state.
    If no user is authenticated, it falls back to the client's IP address.
    """
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user.user_id
    
    # For anonymous requests, fall back to the IP address.
    return get_remote_address(request)


limiter = Limiter(key_func=key_func, storage_uri=settings.REDIS_URL)
