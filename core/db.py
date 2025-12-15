"""
Manages the database connection lifecycle for the application.
"""
from pymongo import MongoClient # type: ignore
import redis # type: ignore
from .config import settings


class DB:
    userdb_client: MongoClient | None = None
    data_client: MongoClient | None = None
    redis_client: redis.Redis | None = None


def connect_to_db():
    """
    Initializes all database clients and attaches them to the DB class.
    This function is called on application startup.
    """
    print("Connecting to UserDB, DataDB, and Redis...")
    DB.userdb_client = MongoClient(settings.USERDB_MONGO_URI)
    DB.data_client = MongoClient(settings.DATA_MONGO_URI)
    DB.redis_client = redis.from_url(settings.REDIS_URL)
    print("Database connections established.")


def close_db_connection():
    """
    Gracefully closes all active database connections.
    This function is called on application shutdown.
    """
    print("Closing database connections...")
    if DB.userdb_client:
        DB.userdb_client.close()
    if DB.data_client:
        DB.data_client.close()
    if DB.redis_client:
        DB.redis_client.close()
    print("Database connections closed.")



def get_userdb_client() -> MongoClient:
    if not DB.userdb_client:
        raise RuntimeError("UserDB MongoDB client has not been initialized.")
    return DB.userdb_client

def get_data_client() -> MongoClient:
    if not DB.data_client:
        raise RuntimeError("DataDB MongoDB client has not been initialized.")
    return DB.data_client

def get_redis_client() -> redis.Redis:
    if not DB.redis_client:
        raise RuntimeError("Redis client has not been initialized.")
    return DB.redis_client
