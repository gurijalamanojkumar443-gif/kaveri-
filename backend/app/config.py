import os
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from dotenv import load_dotenv

# Explicitly load .env file
load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = Field(..., description="PostgreSQL Connection URL")
    SECRET_KEY: str = Field(..., description="JWT Master Secret Key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, description="Access token expiration in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration in days")
    ALGORITHM: str = Field(default="HS256", description="JWT Signing Algorithm")
    ENVIRONMENT: str = Field(default="development", description="Environment mode")

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or v.strip() == "" or v == "replace-me":
            raise ValueError("SECRET_KEY is missing or invalid! Server startup aborted.")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long for cryptographic security.")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("DATABASE_URL is missing! Server startup aborted.")
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}

# Instantiate settings. Will fail loudly at import time if SECRET_KEY or DATABASE_URL is missing.
settings = Settings()
