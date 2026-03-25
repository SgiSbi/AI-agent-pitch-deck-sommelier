from __future__ import annotations

from typing import Any, List, Optional, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .interfaces import UserRepository, ReportRepository, UserStatsRepository, PresentationReportRepository
from ..db.models import User, Report


class SqlAlchemyUserRepository(UserRepository, UserStatsRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_login(self, login: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.login == login))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> List[User]:
        result = await self.db.execute(select(User).order_by(User.id))
        return list(result.scalars().all())

    async def create(self, login: str, hashed_password: str) -> User:
        user = User(login=login, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_active(self, user_id: int, is_active: bool) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.is_active = is_active
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_whitelisted(self, user_id: int, is_whitelisted: bool) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.is_whitelisted = is_whitelisted
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def add_token_stats(
        self,
        user_id: int,
        input_tokens: int,
        output_tokens: int,
        tavily_requests: int,
    ) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            return
        user.total_input_tokens += input_tokens
        user.total_output_tokens += output_tokens
        user.total_tavily_requests += tavily_requests
        await self.db.commit()

    async def add_run_stats(self, username: Optional[str], stats: Dict[str, int]) -> None:
        if not username:
            return
        result = await self.db.execute(select(User).where(User.login == username))
        user = result.scalar_one_or_none()
        if user is None:
            return
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
        input_tokens: int = 0,
        output_tokens: int = 0,
        tavily_requests: int = 0,
    ) -> Report:
        report = Report(
            presentation_dir=presentation_dir,
            user_id=user_id,
            pdf_path=pdf_path,
            docx_path=docx_path,
            report_log_path=report_log_path,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tavily_requests=tavily_requests,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_reports_by_user(self, user_id: int) -> List[Report]:
        result = await self.db.execute(
            select(Report).where(Report.user_id == user_id).order_by(Report.created_at.desc())
        )
        return list(result.scalars().all())

    async def save_paths_summary(self, presentation_dir: str, summary: Dict[str, Any]) -> None:
        result = await self.db.execute(
            select(Report).where(Report.presentation_dir == presentation_dir)
        )
        report = result.scalar_one_or_none()
        if report is None:
            return
        await self.db.commit()
