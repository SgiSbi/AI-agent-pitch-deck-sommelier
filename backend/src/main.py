from pathlib import Path
import os

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from .routes import users, debug, pipeline, admin
from .db.session import get_db, async_engine, Base


app = FastAPI(title="Pitch Deck Analyzer API")

# Регистрация роутов из новой директории routes/
app.include_router(pipeline.router)
app.include_router(users.router)
app.include_router(admin.router)
#app.include_router(debug.router)


@app.on_event("startup")
async def on_startup() -> None:
    """
    Инициализация/сброс схемы БД при старте приложения.
    RESET_DB в .env.backend:
      - False (по умолчанию): только создаём недостающие таблицы.
      - True: полное удаление и пересоздание всех таблиц.
    """
    reset_flag = os.getenv("RESET_DB", "False").lower() == "true"
    async with async_engine.begin() as conn:
        if reset_flag:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


