from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    """Пользователь системы с логином и паролем."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(32), default="standard")
    plan: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Накопленная статистика токенов
    total_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tavily_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Report(Base):
    """Отчёт по презентации, с ссылками на артефакты и логи."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    presentation_dir: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    user: Mapped[Optional[User]] = relationship("User", back_populates="reports")

    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docx_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_log_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статистика по конкретному отчёту
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tavily_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
