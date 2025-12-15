"""
API Dependencies

This file contains reusable dependencies used across multiple API endpoints,
primarily for handling authentication and resource injection (like database clients).
"""
from fastapi import Depends, HTTPException, status, Request # type: ignore
from fastapi.security import OAuth2PasswordBearer # type: ignore

from core.db import get_data_client, get_userdb_client, get_redis_client
from models.pydantic_models import TokenData

# This scheme is still useful for API documentation and client-side integrations,
# but our new get_current_user dependency won't use it directly to get the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(request: Request) -> TokenData:
    """
    Dependency to get the current user from the request state.

    This function relies on the AuthContextMiddleware having already decoded
    the JWT, validated it, and attached the resulting user data to
    `request.state.user`.

    This approach is highly efficient as the token is only decoded once per
    request. If no user is found on the request state, it means a valid
    token was not provided, and an exception is raised.

    Returns:
        The validated token data payload for the authenticated user.
    Raises:
        HTTPException: with status 401 if authentication fails.
    """
    if hasattr(request.state, "user") and request.state.user:
        return request.state.user
    
    # If the middleware did not find a valid user, reject the request.
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

