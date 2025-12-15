"""
Auth Module for Orb
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from core.config import settings
import jwt  # type: ignore
import redis  # type: ignore
from bson import ObjectId  # type: ignore
from pymongo import MongoClient, errors  # type: ignore

from .exceptions import AuthenticationError, DatabaseError
from .utils import verify_key


class Auth:
    def __init__(self, r: redis.Redis, client: MongoClient):
        self.redis_client = r
        self.action = "Authentication"
        self.mongo_client = client

    def authorize_user(self, jwt_token: str) -> Dict[str, Any]:
        """
        Validates a JWT and returns the payload if valid.

        Args:
            user_id: The user ID for whom the token is being validated. (Note: currently unused for validation itself)
            jwt_token: The user-provided JWT.

        Returns:
            The decoded token payload.

        Raises:
            AuthenticationError: If the token is expired or invalid.
        """
        secret = settings.SERVER_SECRET
        if not secret:
            raise AuthenticationError("Server secret is not configured.")

        try:
            payload = jwt.decode(jwt_token, secret, algorithms=["HS256"], options={"verify_exp": True})
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired.")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Token is invalid: {e}")


    def authenticate_user(self, user_id: str, api_key: str) -> str:
        """
        Authenticates a user with their API key and returns a new JWT.

        Args:
            user_id: The username of the user.
            api_key: The API key provided by the user.

        Returns:
            A new time-sensitive JWT.

        Raises:
            AuthenticationError: For any failure in the authentication process.
        """
        if not api_key:
            raise AuthenticationError("API key was not provided.")

        if self.redis_client.exists(f"{user_id}") == 0:
            raise AuthenticationError(f"User '{user_id}' not found.")

        user_data = self.redis_client.hgetall(user_id)
        hashed_key = user_data.get(b'api_key_hash')
        if not hashed_key:
            raise AuthenticationError(f"No API key is associated with user '{user_id}'.")

        if not verify_key(api_key, hashed_key):
            raise AuthenticationError("Invalid API key provided.")

        role_id = user_data.get(b'role_id')
        if not role_id:
            raise AuthenticationError(f"User '{user_id}' has no role ID assigned.")

        try:
            permissions = self.mongo_client.userdb.users.find_one(
                {"_id": ObjectId(role_id.decode('utf-8'))},
                {"_id": 0, "read": 1, "write": 1, "user_management": 1}
            )
        except errors.PyMongoError as e:
            raise DatabaseError(f"Failed to fetch permissions for user '{user_id}': {e}")

        if not permissions:
            raise AuthenticationError(f"Could not find permissions for user '{user_id}'.")

        token = self._create_jwt(user_id=user_id, user_info=user_data, permissions=permissions)

        return token


    def _create_jwt(self, user_id: str, user_info: dict, permissions: dict) -> str:
        """
        Internal function to generate a JWT.
        """
        secret = settings.SERVER_SECRET
        if not secret:
            raise AuthenticationError("Server secret is not configured.")

        try:
            payload = {
                "user_id": user_id,
                "role": user_info.get(b'role', b'').decode('utf-8'),
                "metadata": {
                    "name": user_info.get(b'name', b'').decode('utf-8'),
                    "dept": user_info.get(b'dept', b'').decode('utf-8')
                },
                "permissions": permissions,
                "exp": datetime.now(timezone.utc) + timedelta(hours=2)
            }
            token = jwt.encode(payload, secret, algorithm="HS256")
            return token
        except Exception as e:
            raise AuthenticationError(f"Failed to create JWT: {e}")
