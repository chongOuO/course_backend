from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- DB 設定 ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""          
    DB_NAME: str = "Course"

    # --- JWT 設定 ---
    JWT_SECRET: str = ""          
    JWT_ALGORITHM: str = "HS256"

    # --- 其他應用設定 (移入 class 內) ---
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # 設定檔配置
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  
        case_sensitive=True # 
    )

settings = Settings()