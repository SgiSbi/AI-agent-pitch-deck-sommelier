from __future__ import annotations

from typing import Protocol, runtime_checkable, Dict, Any, Optional


@runtime_checkable
class UserStatsRepository(Protocol):
    def add_run_stats(self, username: Optional[str], stats: Dict[str, int]) -> None: ...
    def add_token_stats(self, user_id: int, input_tokens: int, output_tokens: int, tavily_requests: int) -> None: ...


@runtime_checkable
class PresentationReportRepository(Protocol):
    def save_paths_summary(self, presentation_dir: str, summary: Dict[str, Any]) -> None: ...


@runtime_checkable
class UserRepository(Protocol):
    def get_by_login(self, login: str) -> Any: ...
    def create(self, login: str, hashed_password: str) -> Any: ...


@runtime_checkable
class ReportRepository(Protocol):
    def create_report(
        self,
        presentation_dir: str,
        user_id: Optional[int],
        pdf_path: Optional[str],
        docx_path: Optional[str],
        report_log_path: Optional[str],
        input_tokens: int,
        output_tokens: int,
        tavily_requests: int,
    ) -> Any: ...
