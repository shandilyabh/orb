"""
Pydantic models for request and response validation.

These models define the data shapes for the API, providing automatic
validation for incoming requests and serialization for outgoing responses.
"""
from typing import Any, Dict, List, Optional, Union, Literal, Tuple
from pydantic import BaseModel, ConfigDict, Field # type: ignore


class UserCreate(BaseModel):
    """
    Model representing the data required to create a new user.
    Used as the request body for the user creation endpoint.
    """
    user_id: str = Field(..., description="The unique identifier for the user.")
    policy: str = Field(..., description="The access policy/role to assign to the user (e.g., 'admin', 'senior_dev').")
    name: str = Field(..., description="The user's full name.")
    department: str = Field(..., description="The user's department.")
    read_permissions: Optional[Union[Dict[str, List[str]], Literal["all", "none"]]] = Field(
        None,
        alias="read",
        description="Read permissions, as a mapping of databases to collections or 'all'/'none'."
    )
    write_permissions: Optional[Union[Dict[str, List[str]], Literal["all", "none"]]] = Field(
        None,
        alias="write",
        description="Write permissions, as a mapping of databases to collections or 'all'/'none'."
    )

class UserUpdate(BaseModel):
    """
    Model for updating a user's policy or permissions.
    All fields are optional, as a client might only want to update one thing.
    """
    policy: Optional[str] = Field(None, description="The new policy to assign to the user.")
    permissions: Optional[Dict[str, Union[Dict[str, List[str]], Literal["all", "none"]]]] = Field(
        None,
        description="The new permissions to assign, e.g., {'read': {'db': ['coll']}} or {'write': 'all'}."
    )

class UserView(BaseModel):
    """
    A 'view' model representing a user in API responses.
    This model safely exposes only non-sensitive user data.
    """
    user_id: str
    metadata: Dict[str, str]
    role: str
    user_management: bool

    model_config = ConfigDict(from_attributes=True)


class UserCreateResponse(BaseModel):
    """
    Response model for a newly created user.
    Crucially, this includes the one-time API key.
    """
    message: str = "User created successfully. Please store this API key securely as it will not be shown again."
    user_id: str
    api_key: str
    status_code: int = 201



class Token(BaseModel):
    """Model for the JWT access token response, following OAuth2 standards."""
    access_token: str
    token_type: str = "bearer"
    status_code: int = 200


class TokenData(BaseModel):
    """
    Model representing the data stored within a JWT.
    Useful for type hinting when the token payload is decoded.
    """
    user_id: str
    role: str
    metadata: Dict[str, str]
    permissions: Dict[str, Any]


class UserMeResponse(TokenData):
    """
    Response model for the /users/me endpoint.
    Wraps the user data with a status code.
    """
    status_code: int = 200


class DataQuery(BaseModel):
    """Model for generic data read queries."""
    db: str = Field(..., description="The database to query.")
    collection: str = Field(..., description="The collection to query.")
    query: Dict[str, Any] = Field({}, description="The query filter (e.g., {'_id': '...'}).")
    projection: Optional[Dict[str, int]] = Field(None, description="Specifies the fields to return.")
    sort: Optional[List[Tuple[str, int]]] = Field(None, description="Specifies the sort order (e.g., [['field', 1]]).")
    limit: Optional[int] = Field(None, gt=0, description="The maximum number of documents to return.")
    offset: Optional[int] = Field(None, ge=0, description="The number of documents to skip.")
    batch_size: Optional[int] = Field(None, gt=0, description="Specifies the number of documents in each batch.")


class DataUpdate(DataQuery):
    """Model for generic data update operations."""
    update: Dict[str, Any] = Field(..., description="The update operation (e.g., {'$set': {'field': 'value'}}).")


class CountResponse(BaseModel):
    """A generic response model for returning a document count."""
    count: int
    status_code: int = 200


class StatusResponse(BaseModel):
    """A generic response model for returning a status message."""
    status: str = "ok"
    status_code: int = 200
    message: str
