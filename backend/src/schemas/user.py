from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class UserRegister(BaseModel):
    login: str
    password: str

    @field_validator("login")
    @classmethod
    def login_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Логин не может быть пустым")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v


class UserLogin(BaseModel):
    login: str
    password: str


class UserRead(BaseModel):
    id: int
    login: str
    role: str
    plan: Optional[str] = None
    is_active: bool
    is_whitelisted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserAdminRead(UserRead):
    """Расширенная схема для администратора — включает статистику."""
    total_input_tokens: int
    total_output_tokens: int
    total_tavily_requests: int
    reports_count: int = 0


class UserProfileRead(UserRead):
    """Схема профиля пользователя — включает статистику токенов."""
    total_input_tokens: int
    total_output_tokens: int
    total_tavily_requests: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
