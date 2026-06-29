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

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, login: str, hashed_password: str, email: Optional[str] = None) -> User:
        user = User(login=login, hashed_password=hashed_password, email=email)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_reset_otp(self, user_id: int, otp_hash: str, expires_at: Any) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.reset_otp_hash = otp_hash
        user.reset_otp_expires_at = expires_at
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def clear_reset_otp(self, user_id: int) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.reset_otp_hash = None
        user.reset_otp_expires_at = None
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_email(self, user_id: int, email: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.email = email
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def set_password_hash(self, user_id: int, hashed_password: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.hashed_password = hashed_password
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
        status: str = "processing",
        error_message: Optional[str] = None,
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
            status=status,
            error_message=error_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tavily_requests=tavily_requests,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, report_id: int) -> Optional[Report]:
        result = await self.db.execute(select(Report).where(Report.id == report_id))
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        report_id: int,
        docx_path: str,
        report_log_path: str,
        input_tokens: int,
        output_tokens: int,
        tavily_requests: int,
    ) -> Optional[Report]:
        report = await self.get_by_id(report_id)
        if report is None:
            return None
        report.docx_path = docx_path
        report.report_log_path = report_log_path
        report.status = "completed"
        report.error_message = None
        report.input_tokens = input_tokens
        report.output_tokens = output_tokens
        report.tavily_requests = tavily_requests

        if report.user_id is not None:
            user = await self.db.get(User, report.user_id)
            if user is not None:
                user.total_input_tokens += input_tokens
                user.total_output_tokens += output_tokens
                user.total_tavily_requests += tavily_requests

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def mark_failed(self, report_id: int, error_message: str) -> Optional[Report]:
        report = await self.get_by_id(report_id)
        if report is None:
            return None
        report.status = "failed"
        report.error_message = error_message
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
