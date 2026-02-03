"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pbx_microservice"
    
    # Application
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    
    # AI Service Configuration
    AI_SERVICE_FAILURE_RATE: float = 0.25
    AI_SERVICE_MIN_LATENCY: float = 1.0
    AI_SERVICE_MAX_LATENCY: float = 3.0
    
    # Retry Configuration
    MAX_RETRY_ATTEMPTS: int = 5
    RETRY_INITIAL_WAIT: int = 1
    RETRY_MAX_WAIT: int = 60
    
    # Packet Validation
    PACKET_TIMEOUT_SECONDS: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()