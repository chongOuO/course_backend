from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # DB
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""          
    DB_NAME: str = "Course"

    # JWT
    JWT_SECRET: str = ""          
    JWT_ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

RESET_TOKEN_EXPIRE_MINUTES: int = 30
FRONTEND_BASE_URL: str = "http://localhost:5173"  # 之後做 reset 頁面會用到

settings = Settings()
