"""
Centralized configuration management for the application.
"""
from pydantic import ConfigDict # type: ignore
from pydantic_settings import BaseSettings # type: ignore


class Settings(BaseSettings):
    """
    Manages application settings loaded from the environment.
    
    Pydantic's BaseSettings will automatically try to load each field
    from an environment variable of the same name.
    """
    USERDB_MONGO_URI: str
    DATA_MONGO_URI: str
    REDIS_URL: str
    SERVER_SECRET: str

    # Pydantic v2 uses a model_config dictionary instead of a class Config
    model_config = ConfigDict(
        env_file=".env",
        extra="ignore" # Ignore extra fields from the env
    )


# Create a single, importable instance of the settings for use across the app
settings = Settings()
