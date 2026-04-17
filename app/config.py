"""
Config management - 12-Factor App Style.
All config from environment variables, NO hardcode.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Server
    PORT: int = Field(default=8000, description="HTTP server port")
    HOST: str = Field(default="0.0.0.0")
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)

    # App
    APP_NAME: str = Field(default="My Production Agent")
    APP_VERSION: str = Field(default="1.0.0")

    # LLM
    OPENAI_API_KEY: str = Field(default="")
    LLM_MODEL: str = Field(default="gpt-4o-mini")

    # Security
    AGENT_API_KEY: str = Field(default="dev-key-change-me")
    JWT_SECRET: str = Field(default="dev-jwt-secret")
    ALLOWED_ORIGINS: str = Field(default="*")

    # Rate limiting (10 req/min per user)
    RATE_LIMIT_PER_MINUTE: int = Field(default=10)

    # Cost guard ($10/month per user)
    MONTHLY_BUDGET_USD: float = Field(default=10.0)

    # Redis (stateless: state stored in Redis)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    # Conversation history
    MAX_HISTORY_MESSAGES: int = Field(default=20)
    HISTORY_TTL_SECONDS: int = Field(default=86400)  # 24 hours

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
