from __future__ import annotations

import shutil
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Report, User
from ..db.session import get_db
from ..modules.deps import require_admin
from ..modules.paths import TMP_DIR, ensure_dirs
from ..repositories.sqlalchemy_repos import SqlAlchemyUserRepository
from ..schemas.user import UserAdminRead, UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


async def _enrich(user: User, db: AsyncSession) -> UserAdminRead:
    """Добавляет количество отчётов к данным пользователя."""
    result = await db.execute(
        select(func.count()).where(Report.user_id == user.id)
    )
    reports_count = result.scalar_one() or 0
    data = UserAdminRead.model_validate(user)
    data.reports_count = reports_count
    return data


@router.get("/users", response_model=List[UserAdminRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> List[UserAdminRead]:
    """Список всех пользователей со статистикой."""
    repo = SqlAlchemyUserRepository(db)
    users = await repo.get_all()
    return [await _enrich(u, db) for u in users]


@router.get("/users/{user_id}", response_model=UserAdminRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserAdminRead:
    """Детальная информация о пользователе."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return await _enrich(user, db)


@router.patch("/users/{user_id}/block", response_model=UserRead)
async def block_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserRead:
    """Заблокировать пользователя."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать самого себя")
    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_active(user_id, is_active=False)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}/unblock", response_model=UserRead)
async def unblock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    """Разблокировать пользователя."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_active(user_id, is_active=True)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}/whitelist", response_model=UserRead)
async def add_to_whitelist(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    """Добавить пользователя в вайтлист."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_whitelisted(user_id, is_whitelisted=True)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserRead.model_validate(user)


@router.patch("/users/{user_id}/unwhitelist", response_model=UserRead)
async def remove_from_whitelist(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserRead:
    """Убрать пользователя из вайтлиста."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_whitelisted(user_id, is_whitelisted=False)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserRead.model_validate(user)


class TmpDirInfo(BaseModel):
    path: str
    size_bytes: int
    size_mb: float


def _calc_dir_size(path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


@router.get("/tmp/info", response_model=TmpDirInfo)
async def tmp_info(_: User = Depends(require_admin)) -> TmpDirInfo:
    """Размер директории tmp."""
    if not TMP_DIR.exists():
        return TmpDirInfo(path=str(TMP_DIR), size_bytes=0, size_mb=0.0)
    size = _calc_dir_size(TMP_DIR)
    return TmpDirInfo(path=str(TMP_DIR), size_bytes=size, size_mb=round(size / 1024 / 1024, 2))


@router.delete("/tmp/clear", status_code=status.HTTP_200_OK)
async def tmp_clear(_: User = Depends(require_admin)) -> dict:
    """Очистить директорию tmp (удаляет содержимое, сохраняет саму папку)."""
    if not TMP_DIR.exists():
        return {"detail": "Директория tmp не существует"}

    errors = []
    for item in TMP_DIR.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            errors.append(f"{item.name}: {e}")

    # Пересоздаём нужные поддиректории
    ensure_dirs()

    if errors:
        return {"detail": "Очищено с ошибками", "errors": errors}
    return {"detail": "Директория tmp успешно очищена"}
