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
        Implements Cache-Aside pattern: Checks Redis first, falls back to Mongo.

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

        user_data = None
        
        # 1. Try Cache (Redis)
        if self.redis_client.exists(user_id):
            raw_data = self.redis_client.hgetall(user_id)
            # Convert Redis bytes to strings/appropriate types for consistent handling
            user_data = {
                "api_key_hash": raw_data.get(b'api_key_hash'),
                "role_id": raw_data.get(b'role_id', b'').decode('utf-8'),
                "role": raw_data.get(b'role', b'').decode('utf-8'),
                "name": raw_data.get(b'name', b'').decode('utf-8'),
                "dept": raw_data.get(b'dept', b'').decode('utf-8'),
            }

        # 2. Fallback to Database (Mongo)
        if not user_data:
            try:
                mongo_user = self.mongo_client.userdb.users.find_one({"user_id": user_id})
                if not mongo_user:
                    raise AuthenticationError(f"User '{user_id}' not found.")
                
                # Prepare data structure from Mongo document
                user_data = {
                    "api_key_hash": mongo_user["api_key_hash"],
                    "role_id": str(mongo_user["_id"]),
                    "role": mongo_user["role"],
                    "name": mongo_user["metadata"].get("name", ""),
                    "dept": mongo_user["metadata"].get("department", ""),
                }
                
                # 3. Self-Heal: Populate Redis for next time
                redis_mapping = {
                    "api_key_hash": user_data["api_key_hash"],
                    "role_id": user_data["role_id"],
                    "role": user_data["role"],
                    "name": user_data["name"],
                    "dept": user_data["dept"],
                }
                self.redis_client.hset(user_id, mapping=redis_mapping)
                
            except errors.PyMongoError as e:
                # If Mongo fails too, we are truly stuck
                raise DatabaseError(f"Authentication failed due to database error: {e}")

        # 4. Verify Password
        hashed_key = user_data.get('api_key_hash')
        if not hashed_key:
             # Should practically never happen if user exists, but good for safety
             raise AuthenticationError(f"User '{user_id}' has corrupted data (missing key hash).")

        if not verify_key(api_key, hashed_key):
            raise AuthenticationError("Invalid API key provided.")

        # 5. Get Permissions (Always from Mongo to ensure freshness of access rules)
        role_id = user_data.get('role_id')
        if not role_id:
             raise AuthenticationError(f"User '{user_id}' has no role ID assigned.")

        try:
            permissions = self.mongo_client.userdb.users.find_one(
                {"_id": ObjectId(role_id)},
                {"_id": 0, "read": 1, "write": 1, "user_management": 1}
            )
        except errors.PyMongoError as e:
            raise DatabaseError(f"Failed to fetch permissions for user '{user_id}': {e}")

        if not permissions:
            raise AuthenticationError(f"Could not find permissions for user '{user_id}'.")

        
        user_info_for_jwt = {
            b'role': user_data['role'].encode('utf-8'),
            b'name': user_data['name'].encode('utf-8'),
            b'dept': user_data['dept'].encode('utf-8')
        }

        token = self._create_jwt(user_id=user_id, user_info=user_info_for_jwt, permissions=permissions)

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
