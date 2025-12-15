"""
Pydantic models for logging.

These models provide a structured and type-safe way to represent log entries
before they are inserted into the database. A discriminated union on the 'outcome'
field ensures that each log entry conforms to either a Success or Failure schema.
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator # type: ignore


class RequestInfo(BaseModel):
    """Details of the HTTP request."""
    method: str
    path: str
    payload: Optional[Dict[str, Any]] = None


class BaseLog(BaseModel):
    """Base model containing fields common to all log entries."""
    ts: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(description="The specific business operation, e.g., 'find_one' or 'create_user'.")
    user_id: str
    role: str
    metadata: Dict[str, str]
    request: RequestInfo

    class Config:
        use_enum_values = True


class SuccessRequestLog(BaseLog):
    """Schema for a successful API request log."""
    outcome: Literal["Success"] = "Success"
    response: Dict[str, Any]
    latency_ms: float

    @field_validator('latency_ms')
    def round_latency(cls, v):
        return round(v, 2)


class FailureRequestLog(BaseLog):
    """Schema for a failed API request log."""
    outcome: Literal["Failure"] = "Failure"
    error: Dict[str, Any]


LogEntry = Union[SuccessRequestLog, FailureRequestLog]
