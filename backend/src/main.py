import os

from fastapi import FastAPI
from sqlalchemy import select

from .routes import users, debug, pipeline, admin
from .db.session import async_engine, Base, AsyncSessionLocal
from .db.models import User
from .modules.security import hash_password


app = FastAPI(title="Pitch Deck Analyzer API")

app.include_router(pipeline.router)
app.include_router(users.router)
app.include_router(admin.router)
#app.include_router(debug.router)


@app.on_event("startup")
async def on_startup() -> None:
    """
    Инициализация БД при старте.
    RESET_DB=True — полный сброс схемы.
    ADMIN_LOGIN + ADMIN_PASSWORD — создаёт admin-пользователя если не существует.
    """
    reset_flag = os.getenv("RESET_DB", "False").lower() == "true"
    async with async_engine.begin() as conn:
        if reset_flag:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    admin_login = os.getenv("ADMIN_LOGIN")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_login and admin_password:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.login == admin_login))
            existing = result.scalar_one_or_none()
            if existing is None:
                user = User(
                    login=admin_login,
                    hashed_password=hash_password(admin_password),
                    role="admin",
                    is_active=True,
                    is_whitelisted=True,
                )
                db.add(user)
                await db.commit()
                print(f"[startup] Admin user '{admin_login}' created.")
