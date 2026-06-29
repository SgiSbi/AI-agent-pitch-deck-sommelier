from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import User
from ..modules.deps import get_current_user
from ..modules.security import hash_password, verify_password, create_access_token
from ..modules.email_sender import send_password_reset_otp
from ..repositories.sqlalchemy_repos import SqlAlchemyUserRepository, SqlAlchemyReportRepository
from ..schemas.report import ReportRead
from ..schemas.user import (
    UserRegister,
    UserLogin,
    UserRead,
    UserProfileRead,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetVerify,
    UserEmailUpdate,
    UserPasswordUpdate,
    UserPasswordOtpUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> UserRead:
    """Регистрация нового пользователя."""
    repo = SqlAlchemyUserRepository(db)
    existing = await repo.get_by_login(payload.login)
    if existing:
        raise HTTPException(status_code=400, detail="Логин уже занят")
    if payload.email:
        existing_email = await repo.get_by_email(payload.email)
        if existing_email:
            raise HTTPException(status_code=400, detail="Эта почта уже используется")
    user = await repo.create(
        login=payload.login,
        hashed_password=hash_password(payload.password),
        email=payload.email,
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


@router.patch("/me/email", response_model=UserRead)
async def update_my_email(
    payload: UserEmailUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Добавить/обновить email текущего пользователя."""
    repo = SqlAlchemyUserRepository(db)
    existing = await repo.get_by_email(str(payload.email))
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="Эта почта уже используется")
    user = await repo.set_email(current_user.id, str(payload.email))
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserRead.model_validate(user)


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Отправляет OTP на email, если пользователь существует.
    Всегда возвращает 200 для защиты от перебора email.
    """
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_email(str(payload.email))
    if user:
        otp = f"{secrets.randbelow(10**6):06d}"
        otp_hash = hash_password(otp)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        await repo.set_reset_otp(user.id, otp_hash, expires_at)
        try:
            send_password_reset_otp(str(payload.email), otp)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Не удалось отправить письмо: {e}") from e

    return {"detail": "Если email зарегистрирован, OTP отправлен"}


@router.post("/password-reset/verify", response_model=TokenResponse)
async def verify_password_reset_otp(payload: PasswordResetVerify, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Проверяет OTP и авторизует пользователя без пароля."""
    repo = SqlAlchemyUserRepository(db)
    user = await repo.get_by_email(str(payload.email))
    if not user or not user.reset_otp_hash or not user.reset_otp_expires_at:
        raise HTTPException(status_code=401, detail="Неверный OTP или email")

    if user.reset_otp_expires_at < datetime.now(timezone.utc):
        await repo.clear_reset_otp(user.id)
        raise HTTPException(status_code=401, detail="OTP истек")

    if not verify_password(payload.otp, user.reset_otp_hash):
        raise HTTPException(status_code=401, detail="Неверный OTP или email")

    return TokenResponse(
        access_token=create_access_token(subject=user.login),
        must_change_password=True,
    )


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_my_password(
    payload: UserPasswordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Смена пароля в профиле с проверкой старого пароля."""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Старый пароль указан неверно")
    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_password_hash(current_user.id, hash_password(payload.new_password))
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"detail": "Пароль успешно изменен"}


@router.patch("/me/password/otp", status_code=status.HTTP_200_OK)
async def change_password_after_otp(
    payload: UserPasswordOtpUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Смена пароля после OTP-входа (старый пароль не требуется)."""
    if not current_user.reset_otp_hash or not current_user.reset_otp_expires_at:
        raise HTTPException(status_code=403, detail="Операция доступна только после входа по OTP")
    if current_user.reset_otp_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Окно смены пароля после OTP истекло")

    repo = SqlAlchemyUserRepository(db)
    user = await repo.set_password_hash(current_user.id, hash_password(payload.new_password))
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    await repo.clear_reset_otp(current_user.id)
    return {"detail": "Пароль успешно изменен"}
