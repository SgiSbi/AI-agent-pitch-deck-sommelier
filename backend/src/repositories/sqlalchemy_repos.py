from __future__ import annotations

from typing import Any, Optional, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .interfaces import UserRepository, ReportRepository, UserStatsRepository, PresentationReportRepository
from ..db.models import User, Report


class SqlAlchemyUserRepository(UserRepository, UserStatsRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(self, telegram_id: int, username: Optional[str]) -> User:
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, username=username)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        else:
            # Обновляем username, если он изменился
            if username and user.username != username:
                user.username = username
                await self.db.commit()
        return user

    async def add_run_stats(self, username: Optional[str], stats: Dict[str, int]) -> None:
        # Заготовка: можно хранить агрегированную статистику по пользователям в отдельной таблице.
        # Пока реализуем минимально: при наличии username находим пользователя и
        # в дальнейшем сюда можно добавить обновление полей, связанных с квотами.
        if not username:
            return
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return
        # Здесь можно обновлять счётчики на модели User (например, total_tokens и т.п.).
        # Сейчас оставлено как заглушка.
        await self.db.commit()


class SqlAlchemyReportRepository(ReportRepository, PresentationReportRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_report(
        self,
        presentation_dir: str,
        user_id: Optional[int],
        pdf_path: Optional[str],
        docx_path: Optional[str],
        report_log_path: Optional[str],
    ) -> Report:
        report = Report(
            presentation_dir=presentation_dir,
            user_id=user_id,
            pdf_path=pdf_path,
            docx_path=docx_path,
            report_log_path=report_log_path,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def save_paths_summary(self, presentation_dir: str, summary: Dict[str, Any]) -> None:
        result = await self.db.execute(
            select(Report).where(Report.presentation_dir == presentation_dir)
        )
        report = result.scalar_one_or_none()
        if report is None:
            return
        # В зависимости от нужд можно сериализовать summary в JSON‑поле.
        # Пока просто убеждаемся, что запись существует.
        await self.db.commit()

