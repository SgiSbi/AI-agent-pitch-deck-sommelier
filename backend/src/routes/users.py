from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import User
from ..modules.deps import get_current_user
from ..modules.security import hash_password, verify_password, create_access_token
from ..repositories.sqlalchemy_repos import SqlAlchemyUserRepository, SqlAlchemyReportRepository
from ..schemas.report import ReportRead
from ..schemas.user import UserRegister, UserLogin, UserRead, UserProfileRead, TokenResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> UserRead:
    """Регистрация нового пользователя."""
    repo = SqlAlchemyUserRepository(db)
    existing = await repo.get_by_login(payload.login)
    if existing:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    user = await repo.create(
        login=payload.login,
        hashed_password=hash_password(payload.password),
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Авторизация через JSON: возвращает JWT access token."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_login(payload.login)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(subject=user.login))


@router.post("/login/form", response_model=TokenResponse, include_in_schema=False)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth2 form-логин для Swagger UI."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_login(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(subject=user.login))


@router.get("/me", response_model=UserProfileRead)
async def get_me(current_user: User = Depends(get_current_user)) -> UserProfileRead:
    """Информация о текущем авторизованном пользователе."""
    return UserProfileRead.model_validate(current_user)


@router.get("/me/reports", response_model=List[ReportRead])
async def get_my_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ReportRead]:
    """Список всех отчётов текущего пользователя."""
    repo = SqlAlchemyReportRepository(db)
    reports = await repo.get_reports_by_user(current_user.id)
    return [ReportRead.model_validate(r) for r in reports]
