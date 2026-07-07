from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TwinBiz AI"
    # SQLite by default so the demo runs anywhere; point at PostgreSQL for production:
    # postgresql://user:pass@localhost:5432/twinbiz
    database_url: str = "sqlite:///./twinbiz.db"
    jwt_secret: str = "twinbiz-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60 * 24 * 7
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://twin-biz-ai.vercel.app"

    class Config:
        env_file = ".env"


settings = Settings()
