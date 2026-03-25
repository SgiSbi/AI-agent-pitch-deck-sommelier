import os
from dotenv import load_dotenv
from pathlib import Path

# .env.backend лежит в директории backend, на уровень выше src
load_dotenv(Path(__file__).resolve().parents[2] / ".env.backend")

def _build_async_db_url() -> str:
    direct_url = os.getenv("DATABASE_URL")
    if direct_url:
        return direct_url

    # Иначе собираем URL из отдельных переменных окружения.
    user: str = os.getenv("DBUSER", "user")
    password: str = os.getenv("DBPASSWORD", "password")
    host: str = os.getenv("DBHOST", "database")
    port: str = os.getenv("DBPORT", "5432")
    name: str = os.getenv("DBNAME", "ai_agent")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


ASYNC_DATABASE_URL = _build_async_db_url()

