"""
config.py — อ่านค่าจาก .env โดยใช้ python-dotenv โดยตรง
(ไม่ใช้ pydantic-settings เพราะต้องการ pydantic v2 ซึ่งมี Rust)
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DB_TYPE: str = os.getenv("DB_TYPE", "mysql")          # mysql | postgresql
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_NAME: str = os.getenv("DB_NAME", "hosxp")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASS: str = os.getenv("DB_PASS", "")

    APP_NAME: str = os.getenv("APP_NAME", "HOSxP API")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    API_KEY: str = os.getenv("API_KEY", "hosinfo_secret_token_2026")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "fallback_secret")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "mysql":
            return (
                f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASS}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
                f"?charset=utf8mb4"
            )
        else:
            # PostgreSQL: ต้องติดตั้ง psycopg[binary] ใน requirements.txt
            return (
                f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASS}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
