"""
API router for authentication and user management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request # type: ignore
from fastapi.security import OAuth2PasswordRequestForm # type: ignore
from pymongo import MongoClient # type: ignore
from redis import Redis # type: ignore

from api.dependencies import get_current_user, get_userdb_client, get_data_client, get_redis_client # type: ignore
from models.pydantic_models import (Token, TokenData, UserCreate,
                                    UserCreateResponse, UserUpdate, StatusResponse, UserMeResponse)
from services.authn import Auth
from services.exceptions import (AuthenticationError, DatabaseError,
                                 DocumentNotFoundError, DuplicateUserError, PolicyNotFoundError)
from services.query_router import QueryRouter
from core.limiter import limiter

router = APIRouter(tags=["Authentication & Users"])


@router.post("/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    userdb_client: MongoClient = Depends(get_userdb_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Logs in a user to get an access token.
    
    Takes a standard OAuth2 form request with 'username' and 'password'.
    In our case, 'password' corresponds to the user's API key.
    """
    try:
        auth_service = Auth(r=redis_client, client=userdb_client)
        access_token = auth_service.authenticate_user(
            user_id=form_data.username, api_key=form_data.password
        )
        return {"access_token": access_token, "token_type": "bearer", "status_code": 200}
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/users/me", response_model=UserMeResponse)
@limiter.limit("100/minute;1000000/day")
async def read_users_me(request: Request, current_user: TokenData = Depends(get_current_user)):
    """
    Fetches the data for the currently authenticated user.
    
    A simple protected endpoint to verify that the 'get_current_user'
    dependency is working correctly.
    """
    return UserMeResponse(**current_user.model_dump(), status_code=200)


@router.post("/users", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("100/minute;1000000/day")
async def create_new_user(
    request: Request,
    user_to_create: UserCreate,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Creates a new user. This is a protected endpoint requiring
    'user_management' permissions.
    """
    # Authorization: Check if the current user has permission to create users.
    if not current_user.permissions.get("user_management"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create new users.",
        )

    # Prepare the payload for the query router service
    payload = {
        "op": "create_user",
        "info": current_user.model_dump(),
        "request": {
            "user_id": user_to_create.user_id,
            "policy": user_to_create.policy,
            "metadata": {
                "name": user_to_create.name,
                "department": user_to_create.department,
            },
            "perm": {
                "read": user_to_create.read_permissions,
                "write": user_to_create.write_permissions,
            },
        },
    }

    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        api_key = query_router.route_query(request, payload)
        
        return UserCreateResponse(
            user_id=user_to_create.user_id,
            api_key=api_key
        )
    except DuplicateUserError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/users/{user_id_to_update}", response_model=StatusResponse)
@limiter.limit("100/minute;1000000/day")
async def update_existing_user(
    request: Request,
    user_id_to_update: str,
    user_updates: UserUpdate,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Updates a user's policy and/or permissions. This is a protected
    endpoint requiring 'user_management' permissions.
    """
    if not current_user.permissions.get("user_management"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update users.",
        )

    payload = {
        "op": "update_user",
        "info": current_user.model_dump(),
        "request": {
            "user_id": user_id_to_update,
            "policy": user_updates.policy,
            "permissions": user_updates.permissions,
        },
    }

    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        query_router.route_query(request, payload)
        return StatusResponse(message=f"User '{user_id_to_update}' updated successfully.")
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/users/{user_id_to_delete}", response_model=StatusResponse)
@limiter.limit("100/minute;1000000/day")
async def delete_existing_user(
    request: Request,
    user_id_to_delete: str,
    current_user: TokenData = Depends(get_current_user),
    userdb_client: MongoClient = Depends(get_userdb_client),
    data_client: MongoClient = Depends(get_data_client),
    redis_client: Redis = Depends(get_redis_client),
):
    """
    Deletes a user. This is a protected endpoint requiring
    'user_management' permissions.
    """
    if user_id_to_delete == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete themselves.",
        )
    
    if not current_user.permissions.get("user_management"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete users.",
        )

    payload = {
        "op": "delete_user",
        "info": current_user.model_dump(),
        "request": {"user_id": user_id_to_delete},
    }

    try:
        query_router = QueryRouter(userdb_client=userdb_client, data_client=data_client, redis_client=redis_client)
        query_router.route_query(request, payload)
        return StatusResponse(message="User deleted successfully.")
    except DocumentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (DatabaseError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
