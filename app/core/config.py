from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional, List
import os

class Settings(BaseSettings):
    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "Data"
    
    # Specific paths
    DATABASE_DIR: Path = DATA_DIR / "database" / "formulary_chroma_db"
    PDF_DIR: Path = DATA_DIR / "pdfs"
    JSON_DIR: Path = DATA_DIR / "json"
    CHROMA_DB_PATH: str = str(DATABASE_DIR)
    DRUGS_DB: str = str(DATA_DIR / "drugs.db")
    
    # API Config
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Clinical Agent RAG API"
    
    # OpenAI Config
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "*"]
    
    # OAuth Config
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_CONF_URL: str = "https://accounts.google.com/.well-known/openid-configuration"
    
    # Session & Cookie Config
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", "super-session-secret-change-in-prod")
    COOKIE_SECURE: bool = os.getenv("ENVIRONMENT", "development") == "production"
    
    # Telemetry
    OTEL_ENDPOINT: str = os.getenv("OTEL_ENDPOINT", "http://10.20.35.23/otel")
    
    # Development/Production
    DEBUG: bool = False
    OTEL_SDK_DISABLED: bool = True
    ENVIRONMENT: str = "development"
    
    # Auth Config
    USERS_DB: str = str(DATA_DIR / "users.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-for-local-dev-change-in-prod")
    JWT_SECRET: str = os.getenv("JWT_SECRET", SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    
    # SMTP Config
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.mailtrap.io")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "2525"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() in ("1", "true", "yes")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@mediformulary.com")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        directories = [self.DATA_DIR, self.DATABASE_DIR, self.PDF_DIR, self.JSON_DIR]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

settings = Settings()
