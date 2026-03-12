from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..repositories.sqlalchemy_repos import SqlAlchemyUserRepository


router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]

    class Config:
        from_attributes = True


@router.post("/", response_model=UserResponse)
async def create_or_update_user(payload: UserCreateRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    """
    Создать пользователя или обновить его username по telegram_id.
    Этот метод предполагается вызывать из Telegram‑бота,
    который уже знает telegram_id и username.
    """
    repo = SqlAlchemyUserRepository(db)
    try:
        user = await repo.get_or_create(telegram_id=payload.telegram_id, username=payload.username)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}") from e

    return UserResponse.model_validate(user)
