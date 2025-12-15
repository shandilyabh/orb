"""
Main application entrypoint.

This file initializes the FastAPI application, sets up metadata, registers middlewares,
and includes the API routers.
"""
import time
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request # type: ignore
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint # type: ignore
from starlette.responses import Response, JSONResponse # type: ignore
from slowapi.errors import RateLimitExceeded # type: ignore

from core.db import DB, close_db_connection, connect_to_db
from core.limiter import limiter
from api.routers import auth, operations
from services.authn import Auth
from services.log_manager import LogManager
from services.exceptions import AuthenticationError
from models.pydantic_models import TokenData
from models.log_models import SuccessRequestLog, FailureRequestLog, RequestInfo

# Initialize services
logger = LogManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager to handle application startup and shutdown events.
    It connects to databases and sets up app state on startup.
    """
    print("--- Starting up application and connecting to databases ---")
    connect_to_db()
    # Make DB clients and limiter available to the app state for middleware/dependency access
    app.state.userdb_client = DB.userdb_client
    app.state.data_client = DB.data_client
    app.state.redis_client = DB.redis_client
    app.state.limiter = limiter
    yield
    print("--- Shutting down application and closing connections ---")
    close_db_connection()

app = FastAPI(
    title="Orb Data Access Layer",
    description="API for interacting with the Orb data service.",
    version="0.1.0",
    lifespan=lifespan
)

# --- Exception Handlers ---

@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom exception handler for RateLimitExceeded errors to return a
    standard 429 Too Many Requests response.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )

# --- Middlewares ---

class AuthContextMiddleware(BaseHTTPMiddleware):
    """
    Decodes a JWT from the request header and attaches user data to `request.state`.
    This makes user information available to all subsequent handlers.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.user = None
        auth_header = request.headers.get("authorization")
        
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                try:
                    auth_service = Auth(r=request.app.state.redis_client, client=request.app.state.userdb_client)
                    payload = auth_service.authorize_user(jwt_token=token)
                    request.state.user = TokenData(**payload)
                except AuthenticationError:
                    pass 
        
        response = await call_next(request)
        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Orchestrates logging for every request, creating a single, comprehensive log
    entry for either success or failure. It uses Pydantic models for type-safe
    log generation and reads context set by inner layers of the application.
    """
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.log_context = {}
        start_time = time.time()
        
        user_id = "anonymous"
        role = "anonymous"
        metadata = {}
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.user_id
            role = request.state.user.role
            metadata = request.state.user.metadata

        request_body_bytes = await request.body()
        request_payload = None
        if request_body_bytes:
            if "application/json" in request.headers.get("content-type", ""):
                try:
                    request_payload = json.loads(request_body_bytes)
                except json.JSONDecodeError:
                    request_payload = {"error": "Request body is not valid JSON"}
            else:
                request_payload = {"detail": "Payload not logged for non-JSON content type"}
        
        request_info = RequestInfo(method=request.method, path=request.url.path, payload=request_payload)

        try:
            response = await call_next(request)
            process_time_ms = (time.time() - start_time) * 1000

            if request.url.path == "/api/auth/token" and response.status_code < 400:
                return response

            log_data = SuccessRequestLog(
                user_id=user_id, role=role, metadata=metadata,
                action=request.state.log_context.get("action", "unknown_route"),
                request=request_info,
                response={"status_code": response.status_code},
                latency_ms=process_time_ms
            )
            try:
                if request.app.state.userdb_client:
                    logger.log(client=request.app.state.userdb_client, log_data=log_data)
            except Exception as e:
                print(f"--- CRITICAL: Logging failed on success path: {e} ---")
            
            return response

        except Exception as exc:
            # Re-raise if it's a rate limit exception so the handler can catch it
            if isinstance(exc, RateLimitExceeded):
                raise

            log_data = FailureRequestLog(
                user_id=user_id, role=role, metadata=metadata,
                action=request.state.log_context.get("action", "unknown_route"),
                request=request_info,
                error={"type": type(exc).__name__, "detail": str(exc)}
            )
            try:
                if request.app.state.userdb_client:
                    logger.log(client=request.app.state.userdb_client, log_data=log_data)
            except Exception as e:
                print(f"--- CRITICAL: Logging failed on exception path: {e} ---")
            
            raise

app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthContextMiddleware)

# --- Routers and Health Check ---

app.include_router(auth.router, prefix="/api")
app.include_router(operations.router, prefix="/api")

@app.get("/", tags=["Health Check"])
async def health_check():
    """
    Simple health check endpoint to confirm the API is running and responsive.
    """
    return {"status": "ok", "message": "Welcome to the Orb API!"}

