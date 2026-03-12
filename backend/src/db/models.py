from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    """Пользователь Telegram, расширяемый для платёжной системы."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)

    # Для будущей биллинговой системы
    role: Mapped[str] = mapped_column(String(32), default="standard")
    plan: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

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

    # Пути к файлам / логам. Пока храним как строки, дальше можно вынести в S3 и т.п.
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docx_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_log_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

