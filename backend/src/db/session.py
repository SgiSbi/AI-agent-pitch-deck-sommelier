from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .db_config import ASYNC_DATABASE_URL


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей."""


async_engine = create_async_engine(ASYNC_DATABASE_URL, future=True)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость FastAPI: выдаёт AsyncSession и закрывает её после запроса.
    """
    async with AsyncSessionLocal() as session:
        yield session

